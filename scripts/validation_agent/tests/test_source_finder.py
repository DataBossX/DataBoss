"""Source finder never invents missing docs; finds real local docs; logs all."""

from __future__ import annotations

from pathlib import Path

from ingestion.sheet_classifier import classify_workbook
from ingestion.workbook_ingestor import ingest_workbook
from sources.source_cache import SourceCache
from sources.source_finder import SourceFinder, build_reference_queue


def _refs(workbook: Path):
    structure = ingest_workbook(workbook)
    classification = classify_workbook(structure)
    return build_reference_queue(structure, classification)


def test_missing_docs_reported_not_invented(settings, audit, valid_workbook, tmp_path):
    refs = _refs(valid_workbook)
    assert refs, "fixture should yield references"
    cache = SourceCache(tmp_path / "cache.json")
    finder = SourceFinder(settings, audit, cache, run_id="r1",
                          run_sources_dir=tmp_path / "empty_sources")
    (tmp_path / "empty_sources").mkdir()
    index = finder.find(refs)
    d = index.to_dict()
    # nothing found, everything missing — never fabricated
    assert d["found"] == []
    assert len(d["missing"]) == len(refs)
    # each missing ref logged
    rows = audit.db.query("SELECT * FROM source_documents WHERE status='missing'")
    assert len(rows) == len(refs)


def test_finds_matching_local_document(settings, audit, valid_workbook, tmp_path):
    refs = _refs(valid_workbook)
    target = next(r for r in refs if r.reference_type == "book_page")
    # create a file whose name contains both tokens
    src_dir = tmp_path / "docs"
    src_dir.mkdir()
    fname = target.reference_key + "_deed.pdf"
    (src_dir / fname).write_bytes(b"%PDF-1.4 fake but real file")
    object.__setattr__(settings, "extra_source_dirs", [src_dir])

    cache = SourceCache(tmp_path / "cache2.json")
    finder = SourceFinder(settings, audit, cache, run_id="r2")
    index = finder.find([target])
    d = index.to_dict()
    assert len(d["found"]) == 1
    assert d["found"][0]["reference_key"] == target.reference_key
    assert len(d["found"][0]["sha256"]) == 64
