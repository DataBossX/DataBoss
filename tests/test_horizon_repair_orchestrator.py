"""End-to-end tests for lxml repair, report I/O, and the improvement loop."""

import zipfile
from pathlib import Path

import pytest

from horizon.audit import AuditLog
from horizon.config import HorizonConfig
from horizon.models import ReportModel, TitleRow
from horizon.orchestrator import Orchestrator
from horizon.repair import (
    RepairRefused,
    _extract_template_formulas,
    _fix_worksheet_xml,
    _parse_worksheet_strict_or_prove_lossless,
    repair_workbook,
)
from horizon.report_io import read_report, write_report
from horizon.repair import _HAVE_LXML
from horizon.validation import Requirements

if _HAVE_LXML:
    from lxml import etree

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _make_xlsx_with_error_formula(path: Path):
    """Build a minimal .xlsx containing a cell with an errored formula and a
    media part, so we can prove repair never fabricates a literal but does
    preserve media."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "ok"
    ws["A2"] = "=#REF!"          # broken formula
    wb.save(path)
    # inject a fake media part to prove it survives repair untouched
    tmp = path.with_suffix(".tmp.xlsx")
    with zipfile.ZipFile(path, "r") as zin, \
            zipfile.ZipFile(tmp, "w") as zout:
        for item in zin.infolist():
            zout.writestr(item, zin.read(item.filename))
        zout.writestr("xl/media/plat1.png", b"\x89PNG\r\n\x1a\nFAKEPLATDATA")
    tmp.replace(path)


def _read_worksheet_xml(path: Path, part: str = "xl/worksheets/sheet1.xml") -> bytes:
    with zipfile.ZipFile(path) as zf:
        return zf.read(part)


def _write_worksheet_xml(
    path: Path, xml_bytes: bytes, part: str = "xl/worksheets/sheet1.xml"
) -> None:
    tmp = path.with_suffix(".tmp.xlsx")
    with zipfile.ZipFile(path, "r") as zin, zipfile.ZipFile(tmp, "w") as zout:
        for item in zin.infolist():
            data = xml_bytes if item.filename == part else zin.read(item.filename)
            zout.writestr(item, data)
    tmp.replace(path)


def _inject_error_cell(
    path: Path,
    cell_reference: str,
    formula_text: str = "SUM(#REF!)",
    cached_error: str = "#REF!",
    part: str = "xl/worksheets/sheet1.xml",
) -> None:
    """Rewrite one cell into the exact shape issue #94 calls out:
    ``<c t="e"><f>...</f><v>#REF!</v></c>``."""
    data = _read_worksheet_xml(path, part)
    root = etree.fromstring(data)
    cell = root.find(f".//{{{_MAIN_NS}}}c[@r={cell_reference!r}]")
    assert cell is not None, f"fixture must already contain cell {cell_reference}"
    for tag in ("f", "v"):
        existing = cell.find(f"{{{_MAIN_NS}}}{tag}")
        if existing is not None:
            cell.remove(existing)
    cell.set("t", "e")
    f = etree.SubElement(cell, f"{{{_MAIN_NS}}}f")
    f.text = formula_text
    v = etree.SubElement(cell, f"{{{_MAIN_NS}}}v")
    v.text = cached_error
    new_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    _write_worksheet_xml(path, new_xml, part)


def _make_xlsx_with_exact_error_cell(path: Path, cell_reference: str = "A2"):
    """Build a minimal .xlsx whose ``cell_reference`` is exactly
    ``<c t="e"><f>...</f><v>#REF!</v></c>`` plus a media part, matching the
    shape called out in issue #94's acceptance criterion 1."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "ok"
    ws[cell_reference] = "placeholder"
    wb.save(path)
    tmp = path.with_suffix(".tmp.xlsx")
    with zipfile.ZipFile(path, "r") as zin, zipfile.ZipFile(tmp, "w") as zout:
        for item in zin.infolist():
            zout.writestr(item, zin.read(item.filename))
        zout.writestr("xl/media/plat1.png", b"\x89PNG\r\n\x1a\nFAKEPLATDATA")
    tmp.replace(path)
    _inject_error_cell(path, cell_reference)


def _make_template_with_formula(path: Path, cell_reference: str, formula_text: str):
    """Build a minimal, approved-authority .xlsx with a real formula (no
    error) at ``cell_reference`` -- the Strategy-B restore source."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "ok"
    ws[cell_reference] = f"={formula_text}"
    wb.save(path)


def _make_template_with_shared_formula(path: Path, master_ref: str, follower_ref: str,
                                        formula_text: str, shared_index: str = "0"):
    """Build an approved-authority .xlsx whose ``master_ref``/``follower_ref``
    hold a real OOXML shared formula: the master's ``<f>`` carries the
    formula text plus ``t="shared" si=... ref=...``, and the follower's
    ``<f>`` carries ONLY ``t="shared" si=...`` -- no text at all. This is the
    exact shape `_extract_template_formulas` must not drop attributes from
    (master) or skip entirely (follower, since its <f> text is empty)."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "ok"
    ws[master_ref] = "placeholder"
    ws[follower_ref] = "placeholder"
    wb.save(path)

    data = _read_worksheet_xml(path)
    root = etree.fromstring(data)
    master_cell = root.find(f".//{{{_MAIN_NS}}}c[@r={master_ref!r}]")
    follower_cell = root.find(f".//{{{_MAIN_NS}}}c[@r={follower_ref!r}]")
    for cell, is_master in ((master_cell, True), (follower_cell, False)):
        for tag in ("f", "v"):
            existing = cell.find(f"{{{_MAIN_NS}}}{tag}")
            if existing is not None:
                cell.remove(existing)
        f = etree.SubElement(cell, f"{{{_MAIN_NS}}}f")
        f.set("t", "shared")
        f.set("si", shared_index)
        if is_master:
            f.set("ref", f"{master_ref}:{follower_ref}")
            f.text = formula_text
        # Follower: no ref, no text -- exactly what Excel writes for a
        # shared-formula follower cell.
    new_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    _write_worksheet_xml(path, new_xml)


@pytest.mark.skipif(not _HAVE_LXML, reason="lxml required for XML repair")
def test_repair_refuses_error_formula_without_template_authority(tmp_path):
    # NOTE: this replaces a test that used to assert the issue #94 bug --
    # that repair "fixed" an errored formula by stripping it and leaving the
    # stale cached value behind as a plain literal. That is exactly the
    # silent-error-downgrade defect Strategy B forbids: without an approved
    # template formula for the cell, repair must refuse, not fabricate.
    src = tmp_path / "report.xlsx"
    _make_xlsx_with_error_formula(src)
    dest = tmp_path / "report_v002.xlsx"
    result = repair_workbook(src, dest)

    assert result.repaired is False
    assert result.output is None
    assert result.error
    assert result.defects
    assert result.defects[0]["reason"] == "error_cell_no_template_authority"
    assert result.defects[0]["cell"] == "A2"
    # Nothing was promoted downstream -- no output artifact left behind.
    assert not dest.exists()
    # The source workbook was never modified.
    assert src.exists()


@pytest.mark.skipif(not _HAVE_LXML, reason="lxml required for XML repair")
def test_repair_restores_template_formula_and_flags_recalculation(tmp_path):
    src = tmp_path / "report.xlsx"
    _make_xlsx_with_exact_error_cell(src, "A2")
    template = tmp_path / "template.xlsx"
    _make_template_with_formula(template, "A2", "SUM(B1:B2)")
    dest = tmp_path / "report_v002.xlsx"

    result = repair_workbook(src, dest, template_path=template)

    assert result.repaired is True
    assert result.output == dest
    assert result.recalculation_required is True
    assert any("restored approved template formula" in f for f in result.fixes)
    assert result.media_preserved == 1
    with zipfile.ZipFile(dest) as zf:
        assert zf.read("xl/media/plat1.png") == b"\x89PNG\r\n\x1a\nFAKEPLATDATA"

    repaired_xml = _read_worksheet_xml(dest)
    repaired_root = etree.fromstring(repaired_xml)
    cell = repaired_root.find(f".//{{{_MAIN_NS}}}c[@r='A2']")
    assert cell.get("t") is None                       # no longer an error cell
    assert cell.find(f"{{{_MAIN_NS}}}v") is None        # no stale cached value
    formula = cell.find(f"{{{_MAIN_NS}}}f")
    assert formula is not None and formula.text == "SUM(B1:B2)"  # exact template text
    # The error can never resurface as a plain-looking literal.
    assert b"#REF!" not in repaired_xml


@pytest.mark.skipif(not _HAVE_LXML, reason="lxml required for XML repair")
def test_extract_template_formulas_keeps_shared_follower_with_no_text(tmp_path):
    """Regression (PR review finding): a shared-formula follower cell's <f>
    carries no text -- only t="shared" si=N -- so keying template authority
    on non-empty text silently dropped every follower. Both master and
    follower must be present in the extracted authority."""
    template = tmp_path / "template.xlsx"
    _make_template_with_shared_formula(template, "A2", "A3", "SUM(B1:B2)", shared_index="0")

    with zipfile.ZipFile(template) as archive:
        formulas = _extract_template_formulas(archive, "xl/worksheets/sheet1.xml")

    assert set(formulas) >= {"A2", "A3"}
    assert formulas["A2"].text == "SUM(B1:B2)"
    assert formulas["A2"].get("t") == "shared"
    assert formulas["A2"].get("si") == "0"
    assert formulas["A2"].get("ref") == "A2:A3"
    # The follower's <f> has no text at all -- it must still be kept, and
    # its shared-index attribute must survive.
    assert formulas["A3"].text is None
    assert formulas["A3"].get("t") == "shared"
    assert formulas["A3"].get("si") == "0"


@pytest.mark.skipif(not _HAVE_LXML, reason="lxml required for XML repair")
def test_repair_restores_shared_formula_master_and_follower_with_attributes(tmp_path):
    """Regression (PR review finding): restoring an error cell from a
    template must preserve the template <f>'s t/si/ref attributes (deep-copy
    the element), not just its text -- otherwise a restored shared-formula
    master leaves its follower cells referring to a shared index with no
    matching master."""
    src = tmp_path / "report.xlsx"
    _make_xlsx_with_exact_error_cell(src, "A2")  # base fixture cell, will add a second below
    # Give the source a second error cell at A3 (the would-be follower).
    wb_path = src
    data = _read_worksheet_xml(wb_path)
    root = etree.fromstring(data)
    # A3 doesn't exist yet in this minimal fixture; add it as another error cell.
    sheet_data = root.find(f"{{{_MAIN_NS}}}sheetData")
    row = sheet_data.find(f"{{{_MAIN_NS}}}row")
    a3 = etree.SubElement(row, f"{{{_MAIN_NS}}}c")
    a3.set("r", "A3")
    a3.set("t", "e")
    f = etree.SubElement(a3, f"{{{_MAIN_NS}}}f")
    f.text = "#REF!"
    v = etree.SubElement(a3, f"{{{_MAIN_NS}}}v")
    v.text = "#REF!"
    _write_worksheet_xml(wb_path, etree.tostring(root, xml_declaration=True,
                                                  encoding="UTF-8", standalone=True))

    template = tmp_path / "template.xlsx"
    _make_template_with_shared_formula(template, "A2", "A3", "SUM(B1:B2)", shared_index="0")
    dest = tmp_path / "report_v002.xlsx"

    result = repair_workbook(src, dest, template_path=template)
    assert result.repaired is True
    assert result.recalculation_required is True

    repaired_root = etree.fromstring(_read_worksheet_xml(dest))
    master = repaired_root.find(f".//{{{_MAIN_NS}}}c[@r='A2']").find(f"{{{_MAIN_NS}}}f")
    follower = repaired_root.find(f".//{{{_MAIN_NS}}}c[@r='A3']").find(f"{{{_MAIN_NS}}}f")

    assert master.get("t") == "shared" and master.get("si") == "0" and master.get("ref") == "A2:A3"
    assert master.text == "SUM(B1:B2)"
    # The follower must come back with its shared attributes intact -- a
    # plain-text-only reconstruction would produce a bare <f> with none of
    # this, orphaning it from its master.
    assert follower.get("t") == "shared" and follower.get("si") == "0"


@pytest.mark.skipif(not _HAVE_LXML, reason="lxml required for XML repair")
def test_error_cell_never_emerges_as_non_error_literal(tmp_path):
    """Regression test (issue #94 acceptance criterion 1): a cell shaped
    like ``<c t="e"><f>...</f><v>#REF!</v></c>`` cannot emerge from repair
    as a non-error literal, and cannot converge/promote to downstream
    output, whether or not template authority is available."""
    src = tmp_path / "report.xlsx"
    _make_xlsx_with_exact_error_cell(src, "A2")

    # Unit level: the fixer itself refuses rather than downgrading.
    xml_bytes = _read_worksheet_xml(src)
    fixes: list = []
    with pytest.raises(RepairRefused) as excinfo:
        _fix_worksheet_xml(xml_bytes, fixes, template_formulas=None)
    assert excinfo.value.defects[0]["cell"] == "A2"
    assert fixes == []  # no partial "fix" was recorded for the refused cell

    # End-to-end: repair_workbook never promotes a literal downgrade either.
    dest = tmp_path / "report_v002.xlsx"
    result = repair_workbook(src, dest)
    assert not result.repaired
    assert result.output is None
    assert not dest.exists()

    # And with template authority, the cell comes back as a formula (subject
    # to native recalculation), never as a bare "#REF!" literal.
    template = tmp_path / "template.xlsx"
    _make_template_with_formula(template, "A2", "SUM(B1:B2)")
    result_with_template = repair_workbook(src, dest, template_path=template)
    assert result_with_template.repaired
    assert result_with_template.recalculation_required
    repaired_xml = _read_worksheet_xml(dest)
    cell = etree.fromstring(repaired_xml).find(f".//{{{_MAIN_NS}}}c[@r='A2']")
    assert cell.get("t") != "e"
    assert cell.find(f"{{{_MAIN_NS}}}f") is not None
    assert b"#REF!" not in repaired_xml


@pytest.mark.skipif(not _HAVE_LXML, reason="lxml required for XML repair")
def test_malformed_worksheet_xml_is_a_hard_defect_with_zero_promotion(tmp_path):
    """Regression test (issue #94 acceptance criterion 2): malformed
    worksheet XML causes a hard defect result with zero output promotion --
    no row/cell loss is silently accepted."""
    # Trailing content after the worksheet root closes: three <row> elements
    # exist in the raw bytes, but a permissive recover=True parse (the old
    # behavior) keeps only the first and silently drops rows 2 and 3 -- real
    # row/cell loss with no indication anything went wrong.
    malformed = (
        b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        b'<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>v1</t></is></c></row>'
        b"</sheetData></worksheet>"
        b'<row r="2"><c r="A2" t="inlineStr"><is><t>v2</t></is></c></row>'
        b'<row r="3"><c r="A3" t="inlineStr"><is><t>v3</t></is></c></row>'
    )

    # Prove the contrast directly: naive recover=True silently loses rows...
    lossy_parser = etree.XMLParser(recover=True)
    lossy_root = etree.fromstring(malformed, parser=lossy_parser)
    lossy_rows = sum(1 for _ in lossy_root.iter(f"{{{_MAIN_NS}}}row"))
    assert lossy_rows == 1  # 2 of the 3 rows were silently dropped

    # ...while the strict-or-prove-lossless parser refuses instead.
    with pytest.raises(etree.XMLSyntaxError):
        _parse_worksheet_strict_or_prove_lossless(malformed)

    # End-to-end: repair_workbook turns that into a hard defect, not a crash
    # and not a silently-accepted lossy recovery.
    import openpyxl
    src = tmp_path / "report.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = "ok"
    wb.save(src)
    _write_worksheet_xml(src, malformed)

    dest = tmp_path / "report_v002.xlsx"
    result = repair_workbook(src, dest)
    assert result.repaired is False
    assert result.output is None
    assert result.error
    assert not dest.exists()


@pytest.mark.skipif(not _HAVE_LXML, reason="lxml required for XML repair")
def test_recoverable_xml_with_proven_zero_loss_is_still_accepted(tmp_path):
    """A strict-parse failure is not automatically fatal: if a recovering
    parse can be *proven* to have dropped zero rows/cells, repair may still
    proceed (it must not be needlessly over-conservative)."""
    # An embedded NUL byte (invalid in XML) fails strict parsing, but
    # libxml2's recovery mode reconstructs every row/cell faithfully here.
    recoverable = (
        b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        b'<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>v1</t></is></c></row>'
        b"\x00"
        b'<row r="2"><c r="A2" t="inlineStr"><is><t>v2</t></is></c></row>'
        b"</sheetData></worksheet>"
    )
    root = _parse_worksheet_strict_or_prove_lossless(recoverable)
    assert sum(1 for _ in root.iter(f"{{{_MAIN_NS}}}row")) == 2


def test_report_io_roundtrip(tmp_path):
    report = ReportModel(section="31-12N-24W", rows=[
        TitleRow(grantor="A", grantee="B", instrument_number="2019-001",
                 conveyed_interest="1/2", legal_description="NE/4 Sec 31"),
    ])
    out = tmp_path / "rpt_v001.xlsx"
    write_report(report, out)
    loaded = read_report(out, section="31-12N-24W")
    assert len(loaded.rows) == 1
    assert loaded.rows[0].grantor == "A"
    assert loaded.rows[0].instrument_number == "2019-001"


@pytest.fixture()
def cfg_audit(tmp_path):
    cfg = HorizonConfig(root=tmp_path / "Horizon")
    cfg.ensure_workspace()
    return cfg, AuditLog(path=None, echo=False)


def test_orchestrator_converges_on_clean_report(cfg_audit):
    cfg, audit = cfg_audit
    base = "31-12N-24W_report"
    # seed a v001 so ingest has something to read
    seed = ReportModel(section="31-12N-24W", rows=[
        TitleRow(grantor="A", grantee="B", instrument_number="100",
                 conveyed_interest="1/2", retained_interest="1/2"),
    ])
    write_report(seed, cfg.final_reports / f"{base}_v001.xlsx")

    orch = Orchestrator(cfg, audit)
    result = orch.run(seed, base, Requirements())
    assert result.converged
    assert result.loops_run == 1
    assert result.final_version.name == f"{base}_v002.xlsx"
    assert result.final_version.exists()


def test_orchestrator_escalates_when_unrepairable(cfg_audit):
    cfg, audit = cfg_audit
    base = "31-12N-24W_report"
    # A required instrument that is absent -> validation error with no workbook
    # to repair (no seed version) -> escalate and stop.
    report = ReportModel(section="31-12N-24W", rows=[
        TitleRow(grantor="A", grantee="B", instrument_number="100"),
    ])
    reqs = Requirements(required_instruments={"999"})
    orch = Orchestrator(cfg, audit)
    result = orch.run(report, base, reqs)
    assert not result.converged
    assert result.exhausted
    assert audit.count("ESCALATED") >= 1


def test_orchestrator_respects_max_loops(cfg_audit):
    cfg, audit = cfg_audit
    cfg.max_loops = 3
    base = "31-12N-24W_report"
    # seed a workbook so repair() has a source, but repair makes no fixes ->
    # repaired_path stays None -> loop escalates after first iteration.
    seed = ReportModel(section="31-12N-24W", rows=[
        TitleRow(grantor="A", grantee="B", instrument_number="100"),
    ])
    write_report(seed, cfg.final_reports / f"{base}_v001.xlsx")
    reqs = Requirements(required_instruments={"999"})
    orch = Orchestrator(cfg, audit)
    result = orch.run(seed, base, reqs)
    assert result.loops_run <= cfg.max_loops
    assert not result.converged
