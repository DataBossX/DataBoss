"""Workbook ingestion reads structure without mutating the file."""

from __future__ import annotations

import pytest

from core.hashing import sha256_file
from ingestion.workbook_ingestor import IngestionError, ingest_workbook


def test_ingest_reads_sheets_and_headers(valid_workbook):
    structure = ingest_workbook(valid_workbook)
    names = {s.name for s in structure.sheets}
    assert "Tracts" in names
    assert "OGL Register" in names
    tracts = next(s for s in structure.sheets if s.name == "Tracts")
    assert "Net Acres" in tracts.headers
    assert tracts.max_row >= 11


def test_ingest_is_nondestructive(valid_workbook):
    before = sha256_file(valid_workbook)
    ingest_workbook(valid_workbook)
    ingest_workbook(valid_workbook)
    after = sha256_file(valid_workbook)
    assert before == after


def test_ingest_reports_zip_structure(valid_workbook):
    structure = ingest_workbook(valid_workbook)
    assert structure.zip_valid is True
    assert "[Content_Types].xml" in structure.zip_entries
    assert "xl/workbook.xml" in structure.zip_entries
    assert structure.has_vba is False


def test_ingest_rejects_non_workbook(tmp_path):
    bogus = tmp_path / "not_a_workbook.xlsx"
    bogus.write_text("this is not a zip", encoding="utf-8")
    with pytest.raises(IngestionError):
        ingest_workbook(bogus)


def test_ingest_missing_file(tmp_path):
    with pytest.raises(IngestionError):
        ingest_workbook(tmp_path / "nope.xlsx")
