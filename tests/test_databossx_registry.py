"""Tests for the DataBossX registry builder (databossx/build_registry.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from databossx import build_registry as br

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("registry")
    written = br.build_all(REPO_ROOT, out_dir=out, qa_summary="unit-test run",
                           timestamp="2026-07-11T00:00:00+00:00")
    return out, written


REQUIRED_FILES = [
    "MASTER_INVENTORY.jsonl", "CAPABILITY_REGISTRY.json", "PROJECT_GRAPH.json",
    "KNOWLEDGE_GRAPH.json", "MASTER_BUILD_QUEUE.json", "TOOLS.json",
    "PROMPTS.json", "REPORTS.json", "CLIENTS.json", "QA_REPORT.json", "CHANGELOG.md",
]


def test_all_required_outputs_written(built):
    out, written = built
    for name in REQUIRED_FILES:
        assert name in written and (out / name).exists(), f"missing {name}"


def test_inventory_is_valid_jsonl_with_required_fields(built):
    out, _ = built
    lines = (out / "MASTER_INVENTORY.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) > 50  # repo has far more than 50 assets
    for line in lines:
        rec = json.loads(line)
        assert rec["asset"] and rec["store"] in ("repo", "drive")
        assert isinstance(rec["capabilities"], list) and rec["capabilities"]


def test_repo_records_have_hashes(built):
    out, _ = built
    recs = [json.loads(l) for l in
            (out / "MASTER_INVENTORY.jsonl").read_text(encoding="utf-8").splitlines()]
    repo_recs = [r for r in recs if r["store"] == "repo"]
    assert repo_recs
    for r in repo_recs:
        assert len(r["sha256"]) == 64
        assert r["size_bytes"] >= 0


def test_known_assets_classified_to_expected_capabilities(built):
    out, _ = built
    caps = json.loads((out / "CAPABILITY_REGISTRY.json").read_text(encoding="utf-8"))["capabilities"]
    assert "horizon/interest.py" in caps["CAP_WI"]
    assert "grocery_report_pipeline.py" in caps["CAP_OCR"]
    assert "automation/roger_mills_title_report_builder.py" in caps["CAP_WORKBOOK"]
    assert "databossx/build_registry.py" in caps["CAP_SELF_BUILDER"]


def test_knowledge_graph_edges_reference_existing_nodes(built):
    out, _ = built
    kg = json.loads((out / "KNOWLEDGE_GRAPH.json").read_text(encoding="utf-8"))
    node_ids = {n["id"] for n in kg["nodes"]}
    assert len(node_ids) == len(kg["nodes"]), "duplicate node ids"
    for e in kg["edges"]:
        assert e["from"] in node_ids, f"dangling edge source {e['from']}"
        assert e["to"] in node_ids, f"dangling edge target {e['to']}"


def test_canonical_report_recorded_with_sha256(built):
    out, _ = built
    reports = json.loads((out / "REPORTS.json").read_text(encoding="utf-8"))["reports"]
    canonical = [r for r in reports if "CANONICAL" in r["role"]]
    assert len(canonical) == 1
    assert canonical[0]["sha256"].lower().startswith("308947")


def test_build_queue_ranked_and_open_items_prioritized(built):
    out, _ = built
    q = json.loads((out / "MASTER_BUILD_QUEUE.json").read_text(encoding="utf-8"))
    ranks = [item["rank"] for item in q["queue"]]
    assert ranks == sorted(ranks) and len(set(ranks)) == len(ranks)
    assert all(oi["priority"] >= 1 for oi in q["open_items"])
    # The evidence gate must outrank every tool build.
    assert q["queue"][0]["type"] == "evidence"


def test_no_fabricated_ownership_values(built):
    """The registry must never state WI/NRI/ownership decimals for the project."""
    out, _ = built
    graph = (out / "PROJECT_GRAPH.json").read_text(encoding="utf-8")
    proj = json.loads(graph)["projects"][0]
    assert "OWNERSHIP NOT ESTABLISHED" in proj["status"].upper()


def test_rerun_is_idempotent_except_changelog(built, tmp_path):
    out1 = tmp_path / "a"
    out2 = tmp_path / "b"
    br.build_all(REPO_ROOT, out_dir=out1, timestamp="2026-07-11T00:00:00+00:00")
    br.build_all(REPO_ROOT, out_dir=out2, timestamp="2026-07-11T00:00:00+00:00")
    for name in REQUIRED_FILES:
        if name == "CHANGELOG.md":
            continue
        a = (out1 / name).read_bytes()
        b = (out2 / name).read_bytes()
        assert a == b, f"{name} not deterministic"
