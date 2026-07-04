from core.run_manager import sha256_file
from ingestion.workbook_ingestor import ingest_workbook
from ingestion.manifest_builder import build_manifest

def test_ingest_does_not_mutate(sample_workbook):
    before = sha256_file(sample_workbook)
    ingest_workbook(sample_workbook)
    assert sha256_file(sample_workbook) == before

def test_manifest_detects_sheets_and_media(sample_workbook):
    m = build_manifest(sample_workbook)
    names = [s["name"] for s in m["ingestion"]["sheets"]]
    assert "Tract 1" in names and "OGL" in names
    assert m["ingestion"]["zip"]["has_media"] is True
    assert m["manifest_sha256"]

def test_classifier_identifies_known_sheets(sample_workbook):
    m = build_manifest(sample_workbook)
    cats = m["classification"]["by_category"]
    assert "ogl" in cats or "working_interest" in cats
