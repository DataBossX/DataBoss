"""Coverage for util parsers, source cache, manifest builder, audit reads."""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

from ingestion.manifest_builder import build_manifest, write_manifest
from ingestion.sheet_classifier import classify_workbook
from ingestion.workbook_ingestor import ingest_workbook
from sources.source_cache import SourceCache
from validators.util import column_index, non_empty, parse_decimal, parse_fraction


# ---- util parsers -------------------------------------------------------- #
def test_parse_decimal_variants():
    assert parse_decimal("1,234.50") == Decimal("1234.50")
    assert parse_decimal("$40.00") == Decimal("40.00")
    assert parse_decimal(637.42) == Decimal("637.42")
    assert parse_decimal(None) is None
    assert parse_decimal("") is None
    assert parse_decimal("=SUM(A1:A2)") is None  # never mine digits from a formula
    assert parse_decimal(True) is None  # bools are not numbers here


def test_parse_fraction_variants():
    assert parse_fraction("1/2") == Fraction(1, 2)
    assert parse_fraction("50%") == Fraction(1, 2)
    assert parse_fraction("0.25") == Fraction(1, 4)
    assert parse_fraction(1) == Fraction(1)
    assert parse_fraction("=A1/A2") is None
    assert parse_fraction("not a number") is None
    assert parse_fraction("1/0") is None  # division by zero handled


def test_column_index_alias_and_fuzzy():
    headers = ["Grantor Name", "Net Acres", "OGL #"]
    assert column_index(headers, "grantor") == 0
    assert column_index(headers, "net acres", "acres") == 1
    assert column_index(headers, "ogl") == 2
    assert column_index(headers, "nonexistent") is None


def test_non_empty():
    assert non_empty("x") is True
    assert non_empty(0) is True
    assert non_empty(None) is False
    assert non_empty("   ") is False


# ---- source cache -------------------------------------------------------- #
def test_source_cache_persists_and_reloads(tmp_path):
    doc = tmp_path / "deed.pdf"
    doc.write_bytes(b"%PDF real")
    cache_path = tmp_path / "cache.json"
    cache = SourceCache(cache_path)
    entry = cache.add("book_1_page_1", "book_page", doc)
    assert len(entry.sha256) == 64
    assert cache.get("book_1_page_1") is not None

    # a fresh instance reads the persisted metadata
    reloaded = SourceCache(cache_path)
    got = reloaded.get("book_1_page_1")
    assert got is not None
    assert got.sha256 == entry.sha256
    assert len(reloaded.all()) == 1


def test_source_cache_tolerates_corrupt_file(tmp_path):
    cache_path = tmp_path / "bad.json"
    cache_path.write_text("{not valid json", encoding="utf-8")
    cache = SourceCache(cache_path)  # must not raise
    assert cache.all() == []


# ---- manifest builder ---------------------------------------------------- #
def test_manifest_built_hashed_and_not_overwritten(tmp_path, valid_workbook):
    structure = ingest_workbook(valid_workbook)
    classification = classify_workbook(structure)
    manifest = build_manifest(structure, classification, "run_z",
                              generated_at="2026-07-04T00:00:00Z")
    assert manifest["run_id"] == "run_z"
    assert manifest["workbook"]["sha256"]

    dest = tmp_path / "audit"
    meta1 = write_manifest(manifest, dest)
    assert len(meta1["sha256"]) == 64
    assert (dest / "manifest.json").exists()

    # writing again must NOT overwrite the first manifest.json
    meta2 = write_manifest(manifest, dest)
    assert meta2["path"] != meta1["path"]


# ---- audit logger reads -------------------------------------------------- #
def test_cumulative_spend_and_open_escalations(db, audit):
    audit.log_spend("ALLOWED", Decimal("10.00"), Decimal("10.00"),
                    "COMMITTED", "d", run_id="r1")
    audit.log_spend("ALLOWED", Decimal("5.50"), Decimal("5.50"),
                    "COMMITTED", "d", run_id="r1")
    assert audit.cumulative_spend("r1") == Decimal("15.50")
    assert audit.cumulative_spend() == Decimal("15.50")

    from validators.base_validator import Escalation

    audit.log_escalation("r1", Escalation(failed_gate="G", subject="s"))
    assert audit.open_escalations("r1")
    assert audit.open_escalations()  # global view
