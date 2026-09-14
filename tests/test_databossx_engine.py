from __future__ import annotations

import json
from pathlib import Path

import pytest

from databossx.batching import claim_ready_tasks, complete_task
from databossx.cache import DerivedWorkCache, make_cache_key
from databossx.candidates import Candidate, compare_candidates
from databossx.config import DataBossConfig
from databossx.database import DataBossDatabase
from databossx.engine import execute_capability, execute_claimed_batch
from databossx.hashing import copy_file_to_vault, sha256_file
from databossx.intake import create_project, inventory_source, register_source_connection
from databossx.orchestrator import seed_project_intake_run
from databossx.receipts import ReceiptError, build_engine_receipt, seal_receipt, verify_receipt
from databossx.routing import DEFAULT_CATALOG, RoutePolicy, RouteRequest, policy_from_profile, route
from horizon.receipts import verify_receipt as verify_horizon_receipt


def test_copy_file_to_vault_single_pass_dedupes_identical_bytes(tmp_path):
    vault = tmp_path / "vault" / "sha256"
    first = tmp_path / "a.bin"
    second = tmp_path / "b.bin"
    first.write_bytes(b"same-payload")
    second.write_bytes(b"same-payload")

    stored_a = copy_file_to_vault(first, vault)
    stored_b = copy_file_to_vault(second, vault)

    assert stored_a.sha256 == stored_b.sha256 == sha256_file(first)
    assert stored_a.vault_path == stored_b.vault_path
    assert stored_a.vault_path.read_bytes() == b"same-payload"
    assert stored_a.byte_size == len(b"same-payload")
    leftover = list((vault / ".tmp").glob("*")) if (vault / ".tmp").exists() else []
    assert leftover == []


def test_initialize_applies_engine_migrations(tmp_path):
    db = DataBossDatabase(tmp_path / "project.db")
    db.initialize()
    tables = {
        row["name"]
        for row in db.fetchall("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")
    }
    assert {
        "schema_migrations",
        "model_route_decisions",
        "derived_cache",
        "engine_receipts",
        "candidate_comparisons",
    } <= tables
    applied = {row["filename"] for row in db.fetchall("SELECT filename FROM schema_migrations")}
    assert "001_initial_schema.sql" in applied
    assert "002_engine_tables.sql" in applied
    db.initialize()
    assert db.fetchone("SELECT COUNT(*) AS n FROM schema_migrations")["n"] == len(applied)


def test_router_local_only_blocks_remote_and_records_reasons():
    decision = route(
        RouteRequest(
            capability="ocr",
            input_hash="a" * 64,
            policy=policy_from_profile("local_only"),
            modality="image",
        )
    )
    assert decision.selected_worker_id == "local.ocr.v1"
    assert decision.selected_provider == "local_ocr"
    remote = [item for item in decision.rejected if item.worker_id == "remote.ocr.cloud.v1"]
    assert remote and remote[0].reason == "local_only_blocks_remote"
    assert decision.decision_hash


def test_router_deterministic_capability_never_selects_llm():
    catalog = DEFAULT_CATALOG + (
        type(DEFAULT_CATALOG[0])(
            worker_id="remote.title_math.llm.v1",
            capabilities=("title_math",),
            provider="llm",
            requires_network=True,
            quality=0.99,
            expected_cost=1.0,
            latency_ms=10,
        ),
    )
    decision = route(
        RouteRequest(
            capability="title_math",
            input_hash="b" * 64,
            policy=RoutePolicy(profile="remote_allowed", local_only=False, allow_egress=True),
        ),
        catalog=catalog,
    )
    assert decision.selected_worker_id == "local.title_math.v1"
    llm_reject = [item for item in decision.rejected if item.worker_id == "remote.title_math.llm.v1"]
    assert llm_reject
    assert llm_reject[0].reason == "deterministic_capability_rejects_llm"


def test_router_blocks_when_only_remote_workers_exist_under_local_policy():
    remote_only = (
        type(DEFAULT_CATALOG[0])(
            worker_id="remote.research.llm.v1",
            capabilities=("research",),
            provider="llm",
            requires_network=True,
            quality=0.9,
            expected_cost=20.0,
            latency_ms=900,
        ),
    )
    decision = route(
        RouteRequest(
            capability="research",
            input_hash="c" * 64,
            policy=policy_from_profile("default"),
        ),
        catalog=remote_only,
    )
    assert decision.blocked
    assert decision.selected_worker_id is None
    assert decision.blocked_reason == "local_only_no_eligible_worker"


def test_cache_hit_skips_recompute_and_param_change_misses(tmp_path):
    cache = DerivedWorkCache(tmp_path / "cache")
    inputs = ["aa" * 32, "bb" * 32]
    first = cache.put(
        recipe_version="extract.v1",
        input_hashes=inputs,
        payload={"text": "grantor"},
        params={"capability": "extract"},
    )
    hit = cache.get(first.cache_key)
    assert hit is not None
    assert hit.payload == {"text": "grantor"}
    assert cache.get(make_cache_key("extract.v1", inputs, {"capability": "extract"})) == hit
    miss_key = make_cache_key("extract.v1", inputs, {"capability": "extract", "page": 2})
    assert cache.get(miss_key) is None


def test_candidate_comparison_keeps_conflicts_and_rejects_majority_as_evidence():
    report = compare_candidates(
        "mineral_owner",
        [
            Candidate(
                "a",
                "local.extract.rules.v1",
                {"owner": "Ada Cole", "interest": "1/2"},
                {"owner": ["sha-a"], "interest": ["sha-a"]},
            ),
            Candidate(
                "b",
                "remote.extract.llm.v1",
                {"owner": "Ada Cole", "interest": "1/4"},
                {"owner": ["sha-b"], "interest": ["sha-b"]},
            ),
            Candidate(
                "c",
                "remote.extract.llm.v2",
                {"owner": "Ada Cole", "interest": "1/4"},
                {"owner": ["sha-c"], "interest": ["sha-c"]},
            ),
        ],
    )
    by_field = {item.field: item for item in report.fields}
    assert by_field["owner"].status == "AGREE"
    assert by_field["interest"].status == "CONFLICT"
    assert report.winner_candidate_id is None
    assert set(by_field["interest"].distinct_supported_values) == {"1/2", "1/4"}


def test_candidate_comparison_marks_agreement_without_evidence_unsupported():
    report = compare_candidates(
        "bonus",
        [
            Candidate("a", "llm-a", {"bonus": "10000"}, {}),
            Candidate("b", "llm-b", {"bonus": "10000"}, {}),
        ],
    )
    assert report.fields[0].status == "UNSUPPORTED"
    assert report.winner_candidate_id is None


def test_receipt_tamper_is_detected_and_failures_still_bind_inputs():
    receipt = build_engine_receipt(
        kind="capability",
        status="failed",
        input_hashes=["ab" * 32],
        extra={"error": "hash mismatch"},
    )
    sealed = seal_receipt(receipt.body)
    verify_receipt(sealed)
    tampered = dict(sealed)
    tampered["status"] = "succeeded"
    with pytest.raises(ReceiptError, match="hash mismatch"):
        verify_receipt(tampered)
    missing = dict(sealed)
    missing.pop("receipt_sha256")
    with pytest.raises(ReceiptError):
        verify_receipt(missing)
    assert sealed["input_hashes"] == ["ab" * 32]


def test_execute_capability_routes_caches_and_seals_receipt(tmp_path):
    cache = DerivedWorkCache(tmp_path / "cache")
    payload = {
        "subject_key": "grantor",
        "input_hashes": ["11" * 32, "22" * 32],
        "candidates": [
            {
                "candidate_id": "left",
                "producer": "local.extract.rules.v1",
                "values": {"grantor": "Ada Cole"},
                "evidence_hashes": {"grantor": ["11" * 32]},
            },
            {
                "candidate_id": "right",
                "producer": "local.extract.rules.v1",
                "values": {"grantor": "Ida Cole"},
                "evidence_hashes": {"grantor": ["22" * 32]},
            },
        ],
    }
    first = execute_capability(
        "candidate_compare",
        payload,
        project_id="proj-engine",
        cache=cache,
        receipt_path=tmp_path / "receipts" / "first.json",
    )
    second = execute_capability(
        "candidate_compare",
        payload,
        project_id="proj-engine",
        cache=cache,
        receipt_path=tmp_path / "receipts" / "second.json",
    )
    verify_receipt(first.receipt)
    verify_receipt(second.receipt)
    assert first.status == "computed"
    assert second.status == "cache_hit"
    assert second.cache_hit is True
    assert first.output["conflict_count"] == 1
    assert first.output["winner_candidate_id"] is None
    assert first.route.selected_worker_id == "local.compare.v1"
    assert first.receipt["input_hashes"] == payload["input_hashes"]
    assert second.receipt["cache"]["hit"] is True


def test_local_only_policy_blocks_remote_research_execution(tmp_path):
    result = execute_capability(
        "research",
        {"query": "bonus clause", "input_hashes": ["dd" * 32]},
        policy_profile="local_only",
        receipt_path=tmp_path / "blocked.json",
    )
    assert result.status == "blocked"
    assert result.receipt["input_hashes"] == ["dd" * 32]
    verify_receipt(result.receipt)


def test_batch_claim_is_exclusive_and_engine_persists_route_receipt(tmp_path):
    repo_root = tmp_path / "repo"
    config = DataBossConfig.from_repo_root(repo_root)
    project = create_project(config, name="Engine", jurisdiction_code="ZZ", project_id="eng1")
    db = DataBossDatabase(config.project_db_path(project.project_id))

    first = claim_ready_tasks(
        db,
        worker_id="worker-a",
        capabilities=("REGISTER_SOURCES", "INVENTORY_AND_LOCK", "REGISTER_TEMPLATE"),
        limit=2,
    )
    assert len(first) == 2
    second = claim_ready_tasks(
        db,
        worker_id="worker-b",
        capabilities=("REGISTER_SOURCES", "INVENTORY_AND_LOCK", "REGISTER_TEMPLATE"),
        limit=8,
    )
    assert {item.task_id for item in first}.isdisjoint({item.task_id for item in second})
    assert len(first) + len(second) == 3
    complete_task(db, first[0], status="SUCCEEDED")
    row = db.fetchone("SELECT state FROM tasks WHERE id = ?", (first[0].task_id,))
    assert row["state"] == "SUCCEEDED"

    extra_run, extra_tasks = seed_project_intake_run(db, project.project_id)
    assert extra_run > 0 and extra_tasks
    cache = DerivedWorkCache(tmp_path / "derived")
    results = execute_claimed_batch(
        db,
        project_id=project.project_id,
        worker_id="worker-c",
        capabilities=("REGISTER_SOURCES", "INVENTORY_AND_LOCK", "REGISTER_TEMPLATE"),
        cache=cache,
        receipts_root=tmp_path / "task-receipts",
    )
    assert results
    assert all(item.status in {"computed", "cache_hit"} for item in results)
    stored = db.fetchall("SELECT * FROM engine_receipts WHERE project_id = ?", (project.project_id,))
    assert len(stored) == len(results)
    routes = db.fetchall("SELECT * FROM model_route_decisions WHERE project_id = ?", (project.project_id,))
    assert len(routes) == len(results)


def test_inventory_parallel_hash_preserves_duplicate_semantics(tmp_path):
    config = DataBossConfig.from_repo_root(tmp_path / "repo")
    source_root = tmp_path / "docs"
    source_root.mkdir()
    (source_root / "one.txt").write_text("same-bytes", encoding="utf-8")
    (source_root / "two.txt").write_text("same-bytes", encoding="utf-8")
    (source_root / "three.txt").write_text("other", encoding="utf-8")
    project = create_project(config, name="Inv", jurisdiction_code="ZZ", project_id="inv1")
    source = register_source_connection(config, project.project_id, source_root)
    inventory = inventory_source(config, project.project_id, source.source_connection_id, max_workers=4)
    assert inventory.item_count == 3
    assert inventory.duplicate_count == 1
    vault_files = [path for path in config.project_vault_root(project.project_id).rglob("*") if path.is_file()]
    assert len(vault_files) == 2


def test_horizon_failed_receipt_is_sealed_and_binds_input_hash(tmp_path):
    from horizon.controlled_loop import ControlledWorkbookLoop
    from tests.test_horizon_controlled_loop import _make_workbook, _write_controls

    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate)
    _make_workbook(template)
    manifest_path, work_order_path, _ = _write_controls(
        tmp_path,
        candidate,
        template,
        candidate_hash="0" * 64,
    )
    result = ControlledWorkbookLoop.from_files(manifest_path, work_order_path).run()
    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert result.status == "failed"
    assert receipt["input"]["expected_sha256"] == "0" * 64
    assert receipt["input"]["actual_sha256"] == sha256_file(candidate)
    verify_horizon_receipt(receipt)


def test_horizon_success_receipt_seal_survives_reload(tmp_path):
    from horizon.controlled_loop import ControlledWorkbookLoop
    from tests.test_horizon_controlled_loop import _make_workbook, _write_controls

    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate)
    _make_workbook(template)
    manifest_path, work_order_path, _ = _write_controls(tmp_path, candidate, template)
    result = ControlledWorkbookLoop.from_files(manifest_path, work_order_path).run()
    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    verify_horizon_receipt(receipt)
    assert receipt["promotion_executed"] is False
