from __future__ import annotations

from pathlib import Path

import pytest

from databossx.config import DataBossConfig
from databossx.database import DataBossDatabase
from databossx.evidence import add_claim, add_evidence_span, cannot_promote_inferred, open_conflict
from databossx.intake import create_project
from databossx.policy import ApprovalRecord, PolicyEngine
from databossx.tasks import IllegalTaskTransition, complete_task, lease_task, seed_ready_task, transition
from databossx.titlemath import FULL, conservation_holds, parse_interest, reconcile, sum_interests


def test_policy_denies_external_writes_and_stale_approvals():
    engine = PolicyEngine()
    denied = engine.decide("drive.write", write=True)
    assert denied.allowed is False
    stale = engine.allow_external_write(
        ApprovalRecord(
            approval_id="a1",
            artifact_hash="abc",
            destination="gdrive://folder",
            expires_at="2000-01-01T00:00:00Z",
            approver_id="examiner",
        ),
        payload_hash="abc",
        destination="gdrive://folder",
    )
    assert stale.allowed is False
    assert "expired" in stale.reason


def test_material_conflicts_require_human():
    engine = PolicyEngine()
    assert engine.require_human_for_conflicts(["c1"]).allowed is False
    assert engine.require_human_for_conflicts([]).allowed is True


def test_task_state_machine_and_idempotent_seed(tmp_path):
    db = DataBossDatabase(tmp_path / "project.db")
    db.initialize()
    config = DataBossConfig.from_repo_root(tmp_path / "repo")
    project = create_project(config, name="Kernel", jurisdiction_code="OK", project_id="k1")
    project_db = DataBossDatabase(config.project_db_path(project.project_id))
    run = project_db.fetchone("SELECT id FROM runs WHERE project_id = ?", (project.project_id,))
    first = seed_ready_task(project_db, int(run["id"]), "INVENTORY_AND_LOCK", {"stage": "B"})
    second = seed_ready_task(project_db, int(run["id"]), "INVENTORY_AND_LOCK", {"stage": "B"})
    assert first == second
    lease_task(project_db, first, "worker-1")
    assert complete_task(project_db, first, success=True, outcome={"ok": True}) == "SUCCEEDED"
    with pytest.raises(IllegalTaskTransition):
        transition(project_db, first, "READY")


def test_evidence_claims_and_inferred_cannot_promote(tmp_path):
    config = DataBossConfig.from_repo_root(tmp_path / "repo")
    project = create_project(config, name="Evidence", jurisdiction_code="OK", project_id="e1")
    db = DataBossDatabase(config.project_db_path(project.project_id))
    source = tmp_path / "deed.txt"
    source.write_text("Grantor: Synthetic Party", encoding="utf-8")
    # Minimal asset version row for FK
    asset_id = db.execute(
        "INSERT INTO assets (project_id, logical_key, asset_class, first_seen_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        (project.project_id, "deed.txt", "source_document"),
    )
    version_id = db.execute(
        """
        INSERT INTO asset_versions (
            asset_id, source_snapshot_id, sha256, mime_type, byte_size, original_locator,
            vault_path, provider_version, duplicate_of_asset_version_id, created_at
        ) VALUES (?, NULL, 'abc', 'text/plain', 10, ?, ?, '', NULL, CURRENT_TIMESTAMP)
        """,
        (asset_id, str(source), str(source)),
    )
    span = add_evidence_span(db, project.project_id, version_id, snippet="Grantor: Synthetic Party", page="1")
    known = add_claim(db, project.project_id, subject="instrument", predicate="grantor", value_text="Synthetic Party", value_state="known")
    inferred = add_claim(db, project.project_id, subject="instrument", predicate="recording_date", value_state="inferred")
    assert span.evidence_span_id > 0
    assert known.value_state == "known"
    assert cannot_promote_inferred(inferred.value_state)
    conflict_id = open_conflict(db, project.project_id, known.claim_id, inferred.claim_id)
    assert conflict_id > 0


def test_titlemath_conservation_and_review():
    assert parse_interest("1/2") + parse_interest("1/2") == FULL
    assert conservation_holds(["0.5", "0.5"])
    assert conservation_holds(["0.5"]) is False
    result = reconcile("1/2", "1")
    assert result.status == "over_conveyance"
    assert sum_interests(["1/4", "1/4", "1/2"]) == FULL


def test_migrations_apply_kernel_tables(tmp_path):
    db = DataBossDatabase(tmp_path / "project.db")
    applied = db.apply_migrations()
    assert "001_initial_schema.sql" in applied
    assert "002_kernel_and_connectors.sql" in applied
    tables = {row["name"] for row in db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"claims", "evidence_spans", "conflicts", "task_manifests", "connector_cursors"} <= tables
    assert db.apply_migrations() == []
