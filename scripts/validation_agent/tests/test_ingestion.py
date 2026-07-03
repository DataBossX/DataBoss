"""Ingestion reads the workbook without mutating it; classifier identifies the
known core sheets."""

from core.run_manager import sha256_file
from ingestion.workbook_ingestor import WorkbookIngestor
from ingestion.sheet_classifier import classify_workbook
from tests.fixtures.make_fixtures import make_basic_workbook


def test_ingest_does_not_mutate_source(tmp_path):
    src = make_basic_workbook(tmp_path / "wb.xlsx")
    before = sha256_file(src)
    ing = WorkbookIngestor(src)
    manifest = ing.ingest()
    after = sha256_file(src)
    assert before == after  # read-only guarantee
    assert manifest.zip_valid
    assert manifest.sha256 == before
    assert len(manifest.sheets) == 3


def test_manifest_detects_formulas(tmp_path):
    src = make_basic_workbook(tmp_path / "wb.xlsx")
    manifest = WorkbookIngestor(src).ingest()
    tracts = next(s for s in manifest.sheets if s.name == "Tracts")
    assert tracts.formula_cells >= 1


def test_classifier_identifies_core_sheets(tmp_path):
    src = make_basic_workbook(tmp_path / "wb.xlsx")
    manifest = WorkbookIngestor(src).ingest()
    result = classify_workbook(manifest)
    found = result["found_categories"]
    assert "tracts" in found
    assert "ogl_register" in found
    assert "working_interest" in found
    assert result["missing_core"] == []


def test_classifier_flags_missing_core(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.title = "Random"
    wb.active.append(["foo", "bar"])
    p = tmp_path / "bad.xlsx"
    wb.save(p)
    manifest = WorkbookIngestor(p).ingest()
    result = classify_workbook(manifest)
    assert set(result["missing_core"]) == {"tracts", "ogl_register",
                                           "working_interest"}
