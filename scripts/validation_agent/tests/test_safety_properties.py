"""Explicit proofs of two 'never' safety properties."""
from pathlib import Path
from repair.repair_planner import plan_repairs
from repair.failure_classifier import classify
from sources.source_cache import SourceCache
from validators.base_validator import make_result


def test_repair_planner_never_guesses_unknown_formula():
    # A repairable formula defect whose intended formula is NOT known must be
    # escalated, never planned (no guessing).
    r = make_result("Formula Integrity Gate", "FAIL", repairable=True,
                    affected_sheet="Tract 1", affected_cell_or_range="Z9",
                    failure_class="Formula Defect")
    out = plan_repairs([r], known_formulas={})   # nothing known
    assert out["plans"] == []
    assert len(out["escalate"]) == 1
    assert "escalated" in out["escalate"][0]["reason"].lower()


def test_legal_failure_never_routes_to_repair():
    for fclass in ("Title Chain Gap", "HBP Unsupported", "Missing Source",
                   "Source/Legal Mismatch", "Unsafe Legal Inference"):
        r = make_result("G", "FAIL", repairable=True, failure_class=fclass)
        assert r["repairable"] is False              # forced off at construction
        assert classify(r)["route"] == "escalate"    # and routed to human


def test_source_cache_content_addressed_no_overwrite(tmp_path):
    cache = SourceCache(tmp_path / "cache")
    a = cache.store_bytes("doc.pdf", b"hello")
    b = cache.store_bytes("doc.pdf", b"hello")     # identical content
    assert a["sha256"] == b["sha256"] and a["path"] == b["path"]  # dedup, same file
    c = cache.store_bytes("doc.pdf", b"different")  # different content
    assert c["sha256"] != a["sha256"] and c["path"] != a["path"]  # new file, no overwrite
    assert Path(a["path"]).read_bytes() == b"hello"  # original untouched
