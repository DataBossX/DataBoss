"""Ingestion reads without mutation; classifier identifies known sheets."""
from ingestion.workbook_ingestor import ingest, sha256_file
from ingestion.sheet_classifier import classify_sheets, core_gate


def test_ingest_does_not_mutate_source(sample_wb):
    before = sha256_file(sample_wb)
    manifest = ingest(sample_wb)
    after = sha256_file(sample_wb)
    assert before == after
    assert manifest.zip_valid is True
    assert "Title " in manifest.sheet_names
    assert manifest.file_sha256 == before


def test_ingest_detects_formulas_and_hardcoded(sample_wb):
    manifest = ingest(sample_wb)
    title = next(s for s in manifest.sheets if s["name"] == "Title ")
    # Tract 1 has a hard-coded total; Tract 2 has formulas.
    assert title["formula_cells"] >= 1
    assert title["hardcoded_numeric_cells"] >= 1


def test_classifier_identifies_core_sheets(sample_wb):
    manifest = ingest(sample_wb)
    cls = classify_sheets(manifest.sheets)
    gate = core_gate(cls)
    assert gate["tracts_found"] >= 10
    # OGL and WI present -> not fatal
    assert gate["fatal"] is False


def test_classifier_flags_low_confidence():
    fake = [{"name": "ZZZ Mystery", "header_row": ["foo", "bar"]}]
    cls = classify_sheets(fake)
    assert cls[0].escalate is True
