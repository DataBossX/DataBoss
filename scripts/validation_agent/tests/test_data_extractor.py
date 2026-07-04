"""Data extractor turns classified sheets into a real validation context, and
never invents data it cannot confidently map."""

from ingestion.workbook_ingestor import WorkbookIngestor
from ingestion.sheet_classifier import classify_workbook
from ingestion.data_extractor import extract_context
from tests.fixtures.make_fixtures import make_full_workbook, make_basic_workbook


def _ctx(path):
    manifest = WorkbookIngestor(path).ingest()
    classification = classify_workbook(manifest)
    return extract_context(path, classification)


def test_extracts_acreage(tmp_path):
    ctx = _ctx(make_full_workbook(tmp_path / "full.xlsx"))
    assert "tract_acreages" in ctx
    assert len(ctx["tract_acreages"]) == 10
    assert abs(sum(ctx["tract_acreages"]) - 637.42) < 1e-6


def test_extracts_interest_and_chain(tmp_path):
    ctx = _ctx(make_full_workbook(tmp_path / "full.xlsx"))
    assert "interest_rows" in ctx and len(ctx["interest_rows"]) == 2
    row = ctx["interest_rows"][0]
    assert {"grantor_interest", "conveyed", "retained"} <= set(row)
    assert "chain_links" in ctx
    assert ctx["chain_links"][0]["grantor"] == "US"
    assert ctx["chain_links"][0]["vested_root"] is True


def test_extracts_ogl_and_wi(tmp_path):
    ctx = _ctx(make_full_workbook(tmp_path / "full.xlsx"))
    assert "ogl_records" in ctx
    assert ctx["ogl_records"][0]["lessor"] == "A Owner"
    assert "wi_assignments" in ctx
    assert ctx["wi_assignments"][0]["wi"] == "1.0"


def test_extracts_instrument_refs_and_known_sources(tmp_path):
    ctx = _ctx(make_full_workbook(tmp_path / "full.xlsx"))
    assert "instrument_references" in ctx
    keys = {r["reference_key"] for r in ctx["instrument_references"]}
    assert "bk 100/pg 200" in keys
    # The Sources sheet lists it, so it is a known source (audit will pass).
    assert "bk 100/pg 200" in set(ctx["known_source_keys"])


def test_conservative_no_interest_columns(tmp_path):
    # The basic workbook has no interest/chain columns -> those keys are absent
    # (the validators will escalate rather than the extractor inventing data).
    ctx = _ctx(make_basic_workbook(tmp_path / "basic.xlsx"))
    assert "interest_rows" not in ctx
    assert "chain_links" not in ctx
    # But acreage IS present.
    assert "tract_acreages" in ctx
