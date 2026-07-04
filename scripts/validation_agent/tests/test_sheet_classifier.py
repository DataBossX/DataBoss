"""Sheet classifier detects known sheet types and escalates low confidence."""

from __future__ import annotations

from openpyxl import Workbook

from ingestion.sheet_classifier import classify_workbook
from ingestion.workbook_ingestor import ingest_workbook


def test_detects_known_sheets(valid_workbook):
    structure = ingest_workbook(valid_workbook)
    report = classify_workbook(structure)
    counts = report.category_counts()
    assert counts.get("tracts", 0) >= 1
    assert counts.get("ogl_register", 0) >= 1
    assert counts.get("working_interest", 0) >= 1


def test_low_confidence_sheet_escalates(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["alpha", "beta", "gamma"])
    ws.append([1, 2, 3])
    path = tmp_path / "ambiguous.xlsx"
    wb.save(path)

    structure = ingest_workbook(path)
    report = classify_workbook(structure)
    assert report.has_low_confidence()
    assert any(c.category == "unknown" and c.escalate for c in report.classifications)


def test_classification_confidence_bounded(valid_workbook):
    structure = ingest_workbook(valid_workbook)
    report = classify_workbook(structure)
    for c in report.classifications:
        assert 0.0 <= c.confidence <= 1.0
