from __future__ import annotations

import json
from pathlib import Path

from databossx import (
    DataBossConfig,
    DataBossDatabase,
    Orchestrator,
    WorkerRegistry,
    register_intake_workers,
    run_project_intake,
)
from databossx.__main__ import main as cli_main
from databossx.hashing import sha256_file


def _make_source(tmp_path: Path) -> Path:
    root = tmp_path / "source_docs"
    root.mkdir()
    (root / "deed.txt").write_text("same-bytes", encoding="utf-8")
    (root / "dup.txt").write_text("same-bytes", encoding="utf-8")  # byte-identical duplicate
    (root / "lease.txt").write_text("different", encoding="utf-8")
    return root


def test_run_project_intake_executes_real_work_end_to_end(tmp_path):
    config = DataBossConfig.from_repo_root(tmp_path / "repo")
    source_root = _make_source(tmp_path)
    template = tmp_path / "control.xlsx"
    template.write_bytes(b"placeholder-xlsx")

    project, summary = run_project_intake(
        config,
        name="Section 32",
        jurisdiction_code="OK",
        source_roots=[str(source_root)],
        template_path=str(template),
        project_id="proj_e2e",
    )

    # The whole seeded graph ran to completion.
    assert summary.run_status == "COMPLETED"
    assert summary.processed == 3
    assert summary.failed == 0
    assert summary.remaining == 0

    db = DataBossDatabase(config.project_db_path(project.project_id))

    # REGISTER_SOURCES really registered the source connection.
    conns = db.fetchall("SELECT id FROM source_connections WHERE project_id = ?", (project.project_id,))
    assert len(conns) == 1

    # INVENTORY_AND_LOCK really hashed the three files into the vault, flagging
    # the byte-identical duplicate.
    source_versions = db.fetchall(
        "SELECT sha256, duplicate_of_asset_version_id FROM asset_versions av "
        "JOIN assets a ON a.id = av.asset_id WHERE a.asset_class = 'source_document'"
    )
    assert len(source_versions) == 3
    assert sum(1 for r in source_versions if r["duplicate_of_asset_version_id"] is not None) == 1

    # Content-addressed vault holds the real bytes at their sha256 path.
    vault_root = config.project_vault_root(project.project_id)
    deed_hash = sha256_file(source_root / "deed.txt")
    assert (vault_root / deed_hash[:2] / deed_hash).read_text(encoding="utf-8") == "same-bytes"

    # REGISTER_TEMPLATE bound the approved template.
    tp = db.fetchone(
        "SELECT template_asset_version_id FROM title_projects WHERE project_id = ?",
        (project.project_id,),
    )
    assert tp["template_asset_version_id"] is not None

    # Every task recorded exactly one succeeded attempt.
    succeeded = db.fetchone(
        "SELECT COUNT(*) AS n FROM task_attempts WHERE status = 'SUCCEEDED'"
    )["n"]
    assert succeeded == 3
    # Success events landed on the outbox for downstream delivery.
    assert (
        db.fetchone(
            "SELECT COUNT(*) AS n FROM outbox_events WHERE event_type = 'task.succeeded'"
        )["n"]
        == 3
    )


def test_intake_run_respects_dependency_order(tmp_path):
    config = DataBossConfig.from_repo_root(tmp_path / "repo")
    source_root = _make_source(tmp_path)

    # Register workers but drive the engine manually to observe ordering.
    from databossx import create_project

    project = create_project(
        config,
        name="Order",
        jurisdiction_code="OK",
        project_id="proj_order",
        source_roots=[str(source_root)],
    )
    db = DataBossDatabase(config.project_db_path(project.project_id))
    registry = register_intake_workers(WorkerRegistry(), config)
    run_id = int(db.fetchone("SELECT id FROM runs WHERE project_id = ?", (project.project_id,))["id"])
    orch = Orchestrator(db, registry)

    # Before REGISTER_SOURCES runs, INVENTORY_AND_LOCK must not be claimable.
    first = orch.claim_next_task(run_id)
    assert first.task_type in {"REGISTER_SOURCES", "REGISTER_TEMPLATE"}
    assert first.task_type != "INVENTORY_AND_LOCK"
    orch.execute_task(first)

    summary = orch.run_until_idle(run_id)
    assert summary.run_status == "COMPLETED"
    # INVENTORY_AND_LOCK ran and produced a snapshot.
    assert db.fetchone("SELECT COUNT(*) AS n FROM source_snapshots")["n"] == 1


def test_cli_run_intake_completes_and_exits_zero(tmp_path, capsys):
    source_root = _make_source(tmp_path)
    repo_root = tmp_path / "repo"
    code = cli_main(
        [
            "run-intake",
            "--repo-root",
            str(repo_root),
            "--name",
            "CLI Section",
            "--jurisdiction",
            "OK",
            "--source",
            str(source_root),
            "--project-id",
            "proj_cli",
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["run_status"] == "COMPLETED"
    assert out["tasks_succeeded"] == 3
    assert out["project_id"] == "proj_cli"
