"""Source finder: extracts references, builds a missing-document queue, finds
local sources, and NEVER invents the contents of a document it cannot find."""

from config.settings import Settings
from sources.source_finder import SourceFinder, extract_references
from sources.source_cache import SourceCache
from core.run_manager import RunManager


def _settings(tmp_path):
    s = Settings()
    s.project_root = tmp_path
    s.outputs_dir = tmp_path / "outputs"
    s.extra_source_dirs = []
    return s


def test_extract_references_finds_book_page_and_instrument():
    text = ("Warranty deed recorded in Book 100 Page 200. See instrument no. "
            "1234567. Located in Sec 14 T2N R5W.")
    refs = extract_references(text)
    keys = {r["reference_key"] for r in refs}
    assert any("bk 100/pg 200" == k for k in keys)
    assert any("inst 1234567" == k for k in keys)
    assert any(k.startswith("s14-t2n-r5w") for k in keys)


def test_build_missing_queue_flags_missing(tmp_path):
    s = _settings(tmp_path)
    rm = RunManager(tmp_path / "outputs", timestamp="20260101_000000")
    cache = SourceCache(rm.run_dir / "sources")
    finder = SourceFinder(s, rm.run_dir, cache=cache)
    refs = extract_references("Book 100 Page 200 recorded.")
    queue = finder.build_missing_queue(refs)
    assert len(queue) == 1
    assert queue[0].status == "missing"


def test_build_missing_queue_finds_local(tmp_path):
    s = _settings(tmp_path)
    rm = RunManager(tmp_path / "outputs", timestamp="20260101_000001")
    cache = SourceCache(rm.run_dir / "sources")
    # Pre-place a cached doc that matches the reference key.
    cache.store_bytes("doc_bk_100_pg_200.pdf", b"%PDF-1.4 fixture")
    finder = SourceFinder(s, rm.run_dir, cache=cache)
    refs = extract_references("Book 100 Page 200 recorded.")
    queue = finder.build_missing_queue(refs)
    assert queue[0].status == "found_local"
    assert queue[0].source_origin == "local"


def test_dry_run_never_invents_documents(tmp_path):
    s = _settings(tmp_path)  # dry-run default; no okcounty client
    rm = RunManager(tmp_path / "outputs", timestamp="20260101_000002")
    cache = SourceCache(rm.run_dir / "sources")
    finder = SourceFinder(s, rm.run_dir, cache=cache, okcounty=None)
    refs = extract_references("instrument no. 999888")
    queue = finder.build_missing_queue(refs)
    queue = finder.attempt_live_retrieval(queue)
    item = queue[0]
    # It is queued/escalated, never fabricated.
    assert item.status == "queued"
    assert item.file_path is None
    assert item.sha256 is None
