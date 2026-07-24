"""Idempotent-retry and fail-closed validation for the intake workers.

Covers the release-readiness findings: an at-least-once retry that reruns a
committed side effect must resume cleanly (no UNIQUE IntegrityError, no
duplicate logical rows), and an invalid/empty source must fail closed rather
than record a falsely-COMPLETE inventory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from databossx import (
    DataBossConfig,
    DataBossDatabase,
    Orchestrator,
    WorkerRegistry,
    create_project,
    inventory_source,
    register_intake_workers,
    register_source_connection,
    register_workbook_template,
)
from databossx.__main__ import main as cli_main
from databossx.intake import SourceValidationError


class FakeClock:
    from datetime import datetime, timedelta, timezone

    def __init__(self):
        from datetime import datetime, timezone

        self.now = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        from datetime import timedelta

        self.now = self.now + timedelta(seconds=seconds)


def _source(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    root.mkdir()
    (root / "deed.txt").write_text("same", encoding="utf-8")
    (root / "dup.txt").write_text("same", encoding="utf-8")
    (root / "lease.txt").write_text("other", encoding="utf-8")
    return root


def _cfg(tmp_path: Path) -> DataBossConfig:
    return DataBossConfig.from_repo_root(tmp_path / "repo")


def _project(config: DataBossConfig, source_root: Path | None = None, template: Path | None = None):
    return create_project(
        config,
        name="Idem",
        jurisdiction_code="OK",
        project_id="proj_idem",
        source_roots=[str(source_root)] if source_root else None,
        template_path=template,
    )


# --- direct idempotency ----------------------------------------------------

def test_register_source_connection_is_idempotent(tmp_path):
    config = _cfg(tmp_path)
    root = _source(tmp_path)
    project = _project(config, root)
    a = register_source_connection(config, project.project_id, root)
    b = register_source_connection(config, project.project_id, root)
    assert a.source_connection_id == b.source_connection_id
    db = DataBossDatabase(config.project_db_path(project.project_id))
    assert db.fetchone("SELECT COUNT(*) AS n FROM source_connections")["n"] == 1


def test_inventory_source_is_idempotent_and_resumes(tmp_path):
    config = _cfg(tmp_path)
    root = _source(tmp_path)
    project = _project(config, root)
    conn = register_source_connection(config, project.project_id, root)
    r1 = inventory_source(config, project.project_id, conn.source_connection_id)
    r2 = inventory_source(config, project.project_id, conn.source_connection_id)

    # Resume returns the SAME snapshot, not a duplicate inventory.
    assert r2.source_snapshot_id == r1.source_snapshot_id
    assert r2.item_count == 3
    assert r2.duplicate_count == 1
    db = DataBossDatabase(config.project_db_path(project.project_id))
    # One logical asset per path; no duplicate asset_versions.
    assert db.fetchone(
        "SELECT COUNT(*) AS n FROM assets WHERE asset_class = 'source_document'"
    )["n"] == 3
    assert db.fetchone("SELECT COUNT(*) AS n FROM asset_versions")["n"] == 3


def test_register_workbook_template_is_idempotent(tmp_path):
    config = _cfg(tmp_path)
    root = _source(tmp_path)
    template = tmp_path / "control.xlsx"
    template.write_bytes(b"xlsx-bytes")
    project = _project(config, root)
    t1 = register_workbook_template(config, project.project_id, template)
    t2 = register_workbook_template(config, project.project_id, template)
    assert t1 == t2
    db = DataBossDatabase(config.project_db_path(project.project_id))
    assert db.fetchone("SELECT COUNT(*) AS n FROM workbook_templates")["n"] == 1
    assert db.fetchone(
        "SELECT COUNT(*) AS n FROM assets WHERE asset_class = 'workbook_template'"
    )["n"] == 1


# --- post-side-effect crash / retry through the engine ---------------------

def test_retry_after_committed_side_effect_completes_without_duplication(tmp_path):
    """Reviewer's exact scenario: a handler commits its side effect, the lease
    is lost before _finalize, the task is recovered, and the retry completes
    with one logical connection, one asset per path, and one template binding."""
    config = _cfg(tmp_path)
    root = _source(tmp_path)
    template = tmp_path / "control.xlsx"
    template.write_bytes(b"xlsx-bytes")
    project = _project(config, root, template)
    db = DataBossDatabase(config.project_db_path(project.project_id))
    registry = register_intake_workers(WorkerRegistry(), config)
    run_id = int(db.fetchone("SELECT id FROM runs WHERE project_id = ?", (project.project_id,))["id"])

    clock = FakeClock()
    orch = Orchestrator(db, registry, lease_seconds=60, max_attempts=3, clock=clock)

    # Claim REGISTER_SOURCES and run ONLY its handler body (side effect commits),
    # simulating a crash before _finalize.
    ctx = None
    while True:
        c = orch.claim_next_task(run_id)
        if c.task_type == "REGISTER_SOURCES":
            ctx = c
            break
        orch.execute_task(c)  # dispatch the healthy sibling(s) normally
    handler = registry.get("REGISTER_SOURCES")
    result = handler(ctx)  # commits the source_connection row
    assert result.success
    assert db.fetchone("SELECT COUNT(*) AS n FROM source_connections")["n"] == 1

    # Lease is lost; recovery requeues the task. Then drain normally.
    clock.advance(120)
    assert orch.recover_expired_leases(run_id) == [ctx.task_id]
    summary = orch.run_until_idle(run_id)

    assert summary.run_status == "COMPLETED"
    # No duplication despite the side effect running twice.
    assert db.fetchone("SELECT COUNT(*) AS n FROM source_connections")["n"] == 1
    assert db.fetchone(
        "SELECT COUNT(*) AS n FROM assets WHERE asset_class = 'source_document'"
    )["n"] == 3
    assert db.fetchone("SELECT COUNT(*) AS n FROM source_snapshots WHERE completeness_status = 'COMPLETE'")["n"] == 1
    assert db.fetchone("SELECT COUNT(*) AS n FROM workbook_templates")["n"] == 1
    # Every task ended DONE.
    states = {r["state"] for r in db.fetchall("SELECT state FROM tasks")}
    assert states == {"DONE"}


# --- fail-closed validation ------------------------------------------------

def test_register_source_connection_rejects_missing_dir(tmp_path):
    config = _cfg(tmp_path)
    root = _source(tmp_path)
    project = _project(config, root)
    with pytest.raises(SourceValidationError, match="does not exist"):
        register_source_connection(config, project.project_id, tmp_path / "nope")


def test_register_source_connection_rejects_file_not_dir(tmp_path):
    config = _cfg(tmp_path)
    root = _source(tmp_path)
    project = _project(config, root)
    a_file = tmp_path / "afile.txt"
    a_file.write_text("x", encoding="utf-8")
    with pytest.raises(SourceValidationError, match="not a directory"):
        register_source_connection(config, project.project_id, a_file)


def test_inventory_source_fails_closed_on_empty_source(tmp_path):
    config = _cfg(tmp_path)
    root = _source(tmp_path)
    project = _project(config, root)
    empty = tmp_path / "empty"
    empty.mkdir()
    conn = register_source_connection(config, project.project_id, empty)
    with pytest.raises(SourceValidationError, match="no inventoryable files"):
        inventory_source(config, project.project_id, conn.source_connection_id)


def test_inventory_source_allow_empty_records_explicit_empty(tmp_path):
    config = _cfg(tmp_path)
    root = _source(tmp_path)
    project = _project(config, root)
    empty = tmp_path / "empty"
    empty.mkdir()
    conn = register_source_connection(config, project.project_id, empty)
    result = inventory_source(config, project.project_id, conn.source_connection_id, allow_empty=True)
    assert result.item_count == 0


def test_register_workbook_template_rejects_missing_file(tmp_path):
    config = _cfg(tmp_path)
    root = _source(tmp_path)
    project = _project(config, root)
    with pytest.raises(SourceValidationError, match="does not exist"):
        register_workbook_template(config, project.project_id, tmp_path / "missing.xlsx")


def test_cli_fails_closed_and_exits_nonzero_on_missing_source(tmp_path, capsys):
    missing = tmp_path / "does_not_exist"
    code = cli_main(
        [
            "run-intake",
            "--repo-root",
            str(tmp_path / "repo"),
            "--name",
            "Bad",
            "--jurisdiction",
            "OK",
            "--source",
            str(missing),
            "--project-id",
            "proj_bad",
        ]
    )
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["run_status"] != "COMPLETED"
    assert out["tasks_failed"] >= 1


# --- heartbeat -------------------------------------------------------------

def test_heartbeat_extends_lease_and_prevents_recovery(tmp_path):
    config = _cfg(tmp_path)
    root = _source(tmp_path)
    project = _project(config, root)
    db = DataBossDatabase(config.project_db_path(project.project_id))
    run_id = int(db.fetchone("SELECT id FROM runs WHERE project_id = ?", (project.project_id,))["id"])
    clock = FakeClock()
    orch = Orchestrator(db, WorkerRegistry(), lease_seconds=60, clock=clock)

    ctx = orch.claim_next_task(run_id)
    # Advance past the original expiry but heartbeat first: lease is extended,
    # so recovery must not reclaim the still-running task.
    clock.advance(50)
    assert orch.heartbeat(ctx.task_id) is True
    clock.advance(50)  # 100s since claim, but only 50s since heartbeat
    assert orch.recover_expired_leases(run_id) == []
    assert db.fetchone("SELECT state FROM tasks WHERE id = ?", (ctx.task_id,))["state"] == "LEASED"

    # After the extended lease also lapses, recovery reclaims it.
    clock.advance(60)
    assert orch.recover_expired_leases(run_id) == [ctx.task_id]
    # Heartbeat on a no-longer-leased task reports False.
    assert orch.heartbeat(ctx.task_id) is False
