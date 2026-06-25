"""Runnable tests for the pure-python + openpyxl parts (no browser, no API).

Set CTA_TEST_WORKBOOK to a real Section 31 workbook to run the round-trip test:
    CTA_TEST_WORKBOOK=/path/to/31-...xlsx pytest cursory_title_app/tests
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from cursory_title_app.runsheet.columns import (
    FORMULA_COLUMNS, WRITABLE_COLUMNS, assert_writable, column_for_field,
)
from cursory_title_app.runsheet.doctypes import normalize
from cursory_title_app.schemas import DocExtraction
from cursory_title_app.qa.engine import qa_extraction
from cursory_title_app.pipeline import to_runsheet_write


def test_formula_columns_are_protected():
    assert FORMULA_COLUMNS == ["O", "P", "Q", "R", "S"]
    for col in FORMULA_COLUMNS:
        with pytest.raises(PermissionError):
            assert_writable(col)
    for col in WRITABLE_COLUMNS:
        assert_writable(col)  # must not raise


def test_field_to_column_maps_known_fields():
    assert column_for_field("grantor") == "G"
    assert column_for_field("document_link") == "K"
    assert column_for_field("need_action") == "U"


def test_doctype_normalize_keeps_original():
    assert normalize("O/L") == ("Oil and Gas Lease", "O/L")
    assert normalize("WD") == ("Warranty Deed", "WD")
    assert normalize("???") == (None, "???")  # unknown -> no guess


def test_low_confidence_forces_review():
    ext = DocExtraction(confidence=0.3, legal_description="Lot 1 of 31-12N-24W",
                        grantor="A", grantee="B")
    qa = qa_extraction(ext)
    assert not qa["pass"]
    assert "VERIFY: OCR uncertain" in qa["review"]


def test_pipeline_never_targets_formula_columns():
    ext = DocExtraction(confidence=0.95, grantor="A", grantee="B",
                        legal_description="Lots 1, 2 of 31-12N-24W",
                        doc_type_original="WD", document_link="http://x")
    rw, _qa = to_runsheet_write(ext, row=10)
    for field in rw.values:
        col = column_for_field(field)
        assert col not in FORMULA_COLUMNS


def test_legal_authorities_load_and_are_oklahoma():
    from cursory_title_app.legal import authorities as law
    assert law.disclaimer()
    # known categories resolve to authorities with verifiable URLs
    wild = law.for_category("wild-deed")
    assert any("Bennett v. Whitehouse" in (a.get("cite") or "") for a in wild)
    for cat in ("wild-deed", "probate", "ogl-hbp"):
        for a in law.for_category(cat):
            if a.get("url"):
                assert a["url"].startswith("https://")
    # entity-succession is honestly empty of on-point authority (no fabrication)
    ent = law.for_category("entity-succession")
    assert all("note" in a for a in ent)


def test_entity_resolution_matches_variants_not_strangers():
    from cursory_title_app.chain.entities import persons, any_match, is_sovereign
    assert any_match(persons("Marvin G. Mitchell and Carrie Lou"), persons("M. G. Mitchell"))
    assert any_match(persons("Louis E. Jaques"), persons("L. E. Jacques"))  # 1-edit surname
    assert not any_match(persons("John Smith"), persons("M. G. Mitchell"))
    assert is_sovereign("United States of America")
    assert is_sovereign("General Land Office")
    assert not is_sovereign("Marvin G. Mitchell")


@pytest.mark.skipif(not os.getenv("CTA_TEST_WORKBOOK"),
                    reason="set CTA_TEST_WORKBOOK to run chain")
def test_chain_reconstruction_is_low_noise(tmp_path, monkeypatch):
    monkeypatch.setenv("CTA_DATA_DIR", str(tmp_path))
    from cursory_title_app.chain import reconstruct
    rep = reconstruct.reconstruct(Path(os.environ["CTA_TEST_WORKBOOK"]))
    # section-wide check must be far less noisy than the event count
    assert rep["total_defects"] < rep["total_mineral_events"] * 0.30
    assert all(t["has_root"] for t in rep["tracts"])  # every tract has a root grant
    assert set(rep["defects_by_category"]) <= {"wild-deed", "probate", "entity-succession"}


@pytest.mark.skipif(not os.getenv("CTA_TEST_WORKBOOK"),
                    reason="set CTA_TEST_WORKBOOK to run reimport")
def test_reimport_appends_row_with_live_formulas(tmp_path, monkeypatch):
    monkeypatch.setenv("CTA_DATA_DIR", str(tmp_path))
    import csv
    import openpyxl
    from cursory_title_app.reports import reimport
    from cursory_title_app.db import store
    store.init()

    src = Path(os.environ["CTA_TEST_WORKBOOK"])
    approved = tmp_path / "approved.csv"
    with open(approved, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=reimport.CSV_COLUMNS)
        w.writeheader()
        row = {c: "" for c in reimport.CSV_COLUMNS}
        row.update(action="add", approve="yes", instrument_number="TEST-1",
                   doc_type="Mineral Deed", book_page="9999/1", grantor="G",
                   grantee="H", legal_description="NE/4 of 31-12N-24W", tracts="3",
                   conveyance_type="Mineral", conveyance_amount_dec="0.5",
                   document_link="https://example.com/x")
        w.writerow(row)
    res = reimport.apply_csv(src, approved, out_dir=tmp_path, prefer="openpyxl")
    assert res["verify_ok"], res["verify"]["errors"]
    assert len(res["rows_added"]) == 1
    nr = res["rows_added"][0]
    wb = openpyxl.load_workbook(res["output"], keep_links=True)
    o = wb["Runsheet"][f"O{nr}"].value
    assert isinstance(o, str) and o.startswith("=") and str(nr) in o  # formula copied down


@pytest.mark.skipif(not os.getenv("CTA_TEST_WORKBOOK"),
                    reason="set CTA_TEST_WORKBOOK to run round-trip")
def test_roundtrip_preserves_workbook(tmp_path):
    from cursory_title_app.excel.writer import OpenpyxlWriter
    from cursory_title_app.excel.verify import verify_workbook
    from cursory_title_app.schemas import RunsheetWrite

    src = Path(os.environ["CTA_TEST_WORKBOOK"])
    out = tmp_path / "out.xlsx"
    writes = [RunsheetWrite(row=900, values={"notes": "test-only marker"},
                            document_link_url="https://example.com",
                            document_link_label="L")]
    OpenpyxlWriter(src).write(writes, out)
    res = verify_workbook(out, src)
    assert res["ok"], res["errors"]
