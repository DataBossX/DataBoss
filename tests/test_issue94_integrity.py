from __future__ import annotations

import csv
import zipfile
from pathlib import Path

import pytest

import grocery_report_pipeline as grp
from horizon.repair import RepairDefect, _HAVE_LXML, _fix_worksheet_xml, repair_workbook


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _sheet_xml(inner: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{NS}"><sheetData><row r="1">{inner}</row></sheetData></worksheet>'
    ).encode("utf-8")


def _write_xlsx(path: Path, worksheet_xml: bytes, media: bytes | None = b"\x89PNG\r\n\x1a\nFAKE") -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("xl/worksheets/sheet1.xml", worksheet_xml)
        if media is not None:
            zf.writestr("xl/media/plat1.png", media)


@pytest.mark.skipif(not _HAVE_LXML, reason="lxml required")
def test_error_formula_is_not_downgraded_or_promoted(tmp_path):
    src = tmp_path / "broken.xlsx"
    dest = tmp_path / "out.xlsx"
    _write_xlsx(src, _sheet_xml(f'<c r="A2" t="e"><f>#REF!</f><v>#REF!</v></c>'))
    result = repair_workbook(src, dest)
    assert result.output is None
    assert result.promoted is False
    assert result.defect_code == "ERROR_FORMULA_DOWNGRADE_REFUSED"
    assert not dest.exists()
    with pytest.raises(RepairDefect) as exc:
        _fix_worksheet_xml(_sheet_xml(f'<c r="A2" t="e"><f>#REF!</f><v>#REF!</v></c>'), [])
    assert exc.value.code == "ERROR_FORMULA_DOWNGRADE_REFUSED"
    # Source bytes stay an error cell, never a bare literal.
    with zipfile.ZipFile(src) as zf:
        xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert 't="e"' in xml and "#REF!" in xml


@pytest.mark.skipif(not _HAVE_LXML, reason="lxml required")
def test_malformed_worksheet_xml_is_hard_defect(tmp_path):
    src = tmp_path / "bad.xlsx"
    dest = tmp_path / "out.xlsx"
    _write_xlsx(src, b"<worksheet><sheetData><row>")
    result = repair_workbook(src, dest)
    assert result.output is None
    assert result.promoted is False
    assert result.defect_code == "MALFORMED_WORKSHEET_XML"
    assert not dest.exists()


@pytest.mark.skipif(not _HAVE_LXML, reason="lxml required")
def test_clean_workbook_copies_media_without_formula_rewrite(tmp_path):
    src = tmp_path / "clean.xlsx"
    dest = tmp_path / "copy.xlsx"
    media = b"\x89PNG\r\n\x1a\nPLAT"
    _write_xlsx(src, _sheet_xml('<c r="A1"><v>1</v></c>'), media)
    result = repair_workbook(src, dest)
    assert result.promoted is True
    assert result.repaired is False
    with zipfile.ZipFile(dest) as zf:
        assert zf.read("xl/media/plat1.png") == media


def _facts_from_text(tmp_path: Path, name: str, body: str):
    corpus = tmp_path / f"c_{name.replace('.', '_')}"
    corpus.mkdir()
    (corpus / name).write_text(body, encoding="utf-8")
    recs = grp.inventory(corpus, tmp_path / "out", grp.BuildLog())
    texts = grp.extract_text(recs, tmp_path / "out", grp.BuildLog())
    classes = {r.path: ["ownership spreadsheet"] if "ownership" in body.lower() else ["mineral deed"] for r in recs}
    return grp.extract_facts(recs, texts, classes, tmp_path / "out", grp.BuildLog())


def test_unlabeled_date_is_not_recording_date(tmp_path):
    facts = _facts_from_text(
        tmp_path,
        "deed.txt",
        "SYNTHETIC TEST DOCUMENT\nMINERAL DEED\n"
        "Grantor: Foo\nGrantee: Bar\nEffective Date: 2019-03-15\n"
        "Legal: Section 12, T7N, R63W\n",
    )
    assert facts
    assert facts[0].values.get("recording_date") in (None, "")
    assert "missing-recording-date-label" in facts[0].review_flags
    assert "2019-03-15" in facts[0].values.get("effective_date", "")


def test_ordinary_decimals_parse_and_incomplete_set_does_not_sum(tmp_path):
    complete = _facts_from_text(
        tmp_path,
        "owners.txt",
        "SYNTHETIC TEST DOCUMENT\nOWNERSHIP / mineral owner decimal interest schedule\n"
        "Owner A decimal interest 0.5\nOwner B decimal interest 0.5\n"
        "Legal: Section 12, T7N, R63W\n",
    )
    assert complete[0].all_decimals == [0.5, 0.5]
    assert complete[0].owner_set_complete is True
    recon = grp.reconcile(complete, tmp_path / "out", grp.BuildLog())
    assert recon["conflicts"] == []

    incomplete = _facts_from_text(
        tmp_path,
        "partial.txt",
        "SYNTHETIC TEST DOCUMENT\nMINERAL DEED\nGrantor: Foo\nGrantee: Bar\n"
        "decimal interest 0.25\nLegal: Section 12, T7N, R63W\n",
    )
    assert 0.25 in incomplete[0].all_decimals
    assert incomplete[0].owner_set_complete is False
    recon_incomplete = grp.reconcile(incomplete, tmp_path / "out", grp.BuildLog())
    assert recon_incomplete["conflicts"] == []


def test_existing_synthetic_decimal_sum_still_flagged(tmp_path):
    corpus = tmp_path / "corpus"
    grp.make_synthetic_corpus(corpus)
    out = tmp_path / "output"
    grp.run_pipeline(corpus, out, "Grocery_Report", apply_quar=False, log=grp.BuildLog())
    rows = list(csv.DictReader((out / "review_required.csv").open(encoding="utf-8-sig")))
    dec = [row for row in rows if row["rule"] == "decimal-sum"]
    assert dec and "0.95" in dec[0]["detail"]
