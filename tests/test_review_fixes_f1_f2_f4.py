"""Regression tests for CODE_REVIEW findings F1, F2, F4.

Each test fails against the pre-fix code and passes after the fix, and is tagged
with the source finding for provenance (CODE_REVIEW.md / FINDINGS_LEDGER.md).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import grocery_report_pipeline as grp  # noqa: E402

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _read_csv(path: Path):
    with path.open(encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _run(corpus: Path, out: Path):
    log = grp.BuildLog()
    return grp.run_pipeline(corpus, out, "Grocery_Report", apply_quar=False, log=log)


# --------------------------------------------------------------------------- F1
def test_f1_errored_cell_stays_flagged_not_downgraded(tmp_path):
    """A cached Excel error (t="e", value "#REF!") must remain a recognizable
    error after repair -- never be silently downgraded to a plain value."""
    pytest.importorskip("lxml")
    from lxml import etree  # noqa: E402
    from horizon.repair import _fix_worksheet_xml

    xml = (
        f'<worksheet xmlns="{_MAIN_NS}"><sheetData><row r="1">'
        f'<c r="A1" t="e"><f>VLOOKUP(1,X,1)</f><v>#REF!</v></c>'
        f"</row></sheetData></worksheet>"
    ).encode()

    fixes: list[str] = []
    out = _fix_worksheet_xml(xml, fixes)
    root = etree.fromstring(out)
    cell = root.find(f".//{{{_MAIN_NS}}}c")

    # The error MARKER must survive: the cell is still an Excel error, not a
    # default-typed cell whose value is the literal string "#REF!".
    assert cell.get("t") == "e", "error marker t='e' was stripped (F1 regression)"
    # The dangling formula element is removed (that part of the repair is fine).
    assert cell.find(f"{{{_MAIN_NS}}}f") is None
    assert any("errored formula" in f for f in fixes)


# --------------------------------------------------------------------------- F2
def test_f2_no_recording_date_fabrication(tmp_path):
    """A doc with an effective date but no recording label must leave
    recording_date blank and raise the missing-recording-data flag."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "deed_no_recording.txt").write_text(
        "WARRANTY DEED\n"
        "Effective Date: 2019-03-15\n"
        "Grantor John Q. Sample to Grantee Acme Minerals LLC\n"
        "Legal: Section 12, T7N, R63W\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    _run(corpus, out)

    facts = {f["source_file"]: f for f in _read_csv(out / "extracted_facts.csv")}
    row = facts["deed_no_recording.txt"]
    assert row["recording_date"] == "", (
        f"recording_date was fabricated from an unrelated date: {row['recording_date']!r}"
    )
    rr = _read_csv(out / "review_required.csv")
    assert any(
        r["rule"] == "missing-recording-data" and r["subject"] == "deed_no_recording.txt"
        for r in rr
    ), "missing-recording-data flag did not fire for an unlabeled deed"


# --------------------------------------------------------------------------- F4
def test_f4_two_digit_decimals_reconcile_without_false_conflict(tmp_path):
    """Owners at 0.5 + 0.5 (two-digit decimals) must reconcile to 1.0 with NO
    false decimal-sum conflict; 0.5 + 0.3 must still be flagged."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "owners_balanced.txt").write_text(
        "OWNERSHIP schedule\n"
        "Owner Alpha LLC decimal interest 0.5\n"
        "Owner Beta Trust decimal interest 0.5\n"
        "Legal: Section 7, T7N, R63W\n",
        encoding="utf-8",
    )
    (corpus / "owners_short.txt").write_text(
        "OWNERSHIP schedule\n"
        "Owner Gamma LLC decimal interest 0.5\n"
        "Owner Delta Trust decimal interest 0.3\n"
        "Legal: Section 8, T7N, R63W\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    _run(corpus, out)

    rr = _read_csv(out / "review_required.csv")
    # decimal-sum conflicts are grouped by tract; the subject is the legal
    # description (uppercased), e.g. "SECTION 8, T7N, R63W".
    dec_subjects = {r["subject"].upper() for r in rr if r["rule"] == "decimal-sum"}
    assert not any("SECTION 7" in s for s in dec_subjects), (
        "balanced 0.5 + 0.5 raised a FALSE decimal-sum conflict (F4 regression)"
    )
    assert any("SECTION 8" in s for s in dec_subjects), (
        "real 0.5 + 0.3 imbalance was missed (two-digit decimals not captured)"
    )
