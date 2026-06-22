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
