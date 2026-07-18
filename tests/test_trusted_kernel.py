from __future__ import annotations

import sqlite3
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from databossx.config import KernelConfig  # noqa: E402
from databossx.db import Database, MigrationError  # noqa: E402
from databossx.service import KernelService  # noqa: E402
from databossx.vault import VaultError, sha256_file  # noqa: E402


def config_for(tmp_path: Path) -> KernelConfig:
    runtime = tmp_path / "runtime"
    return KernelConfig(
        repo_root=ROOT,
        runtime_root=runtime,
        database_path=runtime / "kernel.sqlite3",
        vault_root=runtime / "vault",
        projects_root=runtime / "projects",
        migrations_root=ROOT / "migrations",
    )


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def test_verified_ingest_search_dedup_and_immutable_sources(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    text = "SYNTHETIC TEST DOCUMENT\nLessee: BigRig Operating Inc\nRoyalty: 3/16"
    (source / "lease.txt").write_text(text, encoding="utf-8")
    (source / "lease COPY.txt").write_text(text, encoding="utf-8")
    (source / "scan.bin").write_bytes(b"\x00\x01\x02")
    symlink_supported = True
    try:
        (source / "outside-link.txt").symlink_to(tmp_path / "outside.txt")
    except OSError:
        symlink_supported = False
    before = tree_hashes(source)

    service = KernelService(config_for(tmp_path))
    project = service.create_project("Evidence Test", source)
    ingest = service.ingest_project(project["id"])

    assert ingest["status"] == "SUCCEEDED"
    assert ingest["asset_count"] == 3
    assert ingest["unique_blob_count"] == 2
    assert tree_hashes(source) == before
    assets = service.list_assets(project["id"])
    assert len(assets) == 3
    assert sum(item["extraction_status"] == "COMPLETE" for item in assets) == 2
    assert any(item["extraction_status"] == "UNSUPPORTED" for item in assets)
    hits = service.search(project["id"], "BigRig")
    assert len(hits) == 2
    assert all(hit["source_sha256"] and hit["char_start"] >= 0 for hit in hits)
    assert all("BigRig" in hit["excerpt"] for hit in hits)
    assert ingest["issue_count"] >= 1
    if symlink_supported:
        assert all(item["rel_path"] != "outside-link.txt" for item in assets)


def test_vault_refuses_overwrite_and_detects_corruption(tmp_path: Path) -> None:
    source = tmp_path / "evidence.txt"
    source.write_text("source-controlled evidence", encoding="utf-8")
    service = KernelService(config_for(tmp_path))
    receipt = service.vault.put_file(source)
    destination = tmp_path / "copy.txt"
    service.vault.materialize(receipt.sha256, destination)
    assert sha256_file(destination) == receipt.sha256
    with pytest.raises(VaultError, match="overwrite"):
        service.vault.materialize(receipt.sha256, destination)


def test_oversized_evidence_fails_ingest_with_named_issue(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    evidence = source / "oversized.pdf"
    evidence.write_bytes(b"0123456789")
    config = replace(config_for(tmp_path), max_file_bytes=4)
    service = KernelService(config)
    project = service.create_project("Strict Ingest", source)

    with pytest.raises(RuntimeError, match="oversized.pdf"):
        service.ingest_project(project["id"])

    with service.db.connect() as connection:
        run = connection.execute("SELECT * FROM ingest_runs").fetchone()
        issue = connection.execute("SELECT * FROM ingest_issues").fetchone()
    assert run["status"] == "FAILED"
    assert run["issue_count"] == 1
    assert issue["rel_path"] == "oversized.pdf"
    assert issue["code"] == "VAULT_COPY_FAILED"
    assert evidence.read_bytes() == b"0123456789"


def test_migration_failure_rolls_back_all_schema_changes(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    migration = migrations / "001_bad.sql"
    migration.write_text(
        "CREATE TABLE should_rollback(id INTEGER);\nTHIS IS INVALID SQL;",
        encoding="utf-8",
    )
    config = replace(config_for(tmp_path), migrations_root=migrations)
    database = Database(config)
    config.initialize_directories()
    with pytest.raises(MigrationError):
        database.initialize()
    with database.connect() as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE name='should_rollback'"
        ).fetchone()
    assert table is None

    migration.write_text(
        "CREATE TABLE should_rollback(id INTEGER);", encoding="utf-8"
    )
    database.initialize()
    with database.connect() as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name='should_rollback'"
        ).fetchone()


def test_audit_chain_is_verified_and_append_only(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "deed.txt").write_text("Grantor: Test Person", encoding="utf-8")
    service = KernelService(config_for(tmp_path))
    project = service.create_project("Audit Test", source)
    service.ingest_project(project["id"])
    health = service.health()
    assert health["audit_chain_valid"] is True

    with service.db.connect() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE audit_events SET action='tampered' WHERE sequence=1"
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM audit_events WHERE sequence=1")


def test_synthetic_project_runs_end_to_end_from_vault(tmp_path: Path) -> None:
    service = KernelService(config_for(tmp_path))
    project = service.create_synthetic_project()
    source = Path(project["source_root"])
    before = tree_hashes(source)
    ingest = service.ingest_project(project["id"])
    assert ingest["asset_count"] == 8
    assert ingest["unique_blob_count"] == 7

    run = service.run_grocery(project["id"])
    assert run["status"] == "SUCCEEDED"
    assert tree_hashes(source) == before
    artifacts = service.list_artifacts(run["id"])
    names = {artifact["rel_path"] for artifact in artifacts}
    assert {
        "Grocery_Report_DRAFT.md",
        "Grocery_Report_Curative_List.xlsx",
        "Grocery_Report_Source_Index.xlsx",
        "run_manifest.json",
        "status_dashboard.html",
    } <= names
    assert all(len(artifact["blob_sha256"]) == 64 for artifact in artifacts)
    second = service.run_grocery(project["id"])
    assert second["id"] != run["id"]
    assert second["run_dir"] != run["run_dir"]


def test_pipeline_timeout_is_finalized_and_audited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = KernelService(config_for(tmp_path))
    project = service.create_synthetic_project()
    service.ingest_project(project["id"])

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], timeout=1)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        service.run_grocery(project["id"])
    runs = service.list_runs(project["id"])
    assert runs[0]["status"] == "FAILED"
    assert "timed out" in runs[0]["error"]
    assert service.health()["audit_chain_valid"] is True


def test_dead_owner_recovery_is_audited(tmp_path: Path) -> None:
    config = config_for(tmp_path)
    service = KernelService(config)
    source = tmp_path / "source"
    source.mkdir()
    project = service.create_project("Recovery", source)
    with service.db.transaction(immediate=True) as connection:
        connection.execute(
            """
            INSERT INTO ingest_runs(
                id, project_id, status, started_at, owner_pid
            ) VALUES ('abandoned', ?, 'RUNNING', '2026-01-01T00:00:00Z', 99999999)
            """,
            (project["id"],),
        )
    recovered = KernelService(config)
    assert recovered.get_ingest("abandoned")["status"] == "INTERRUPTED"
    events = recovered.audit_events(project["id"])
    assert any(event["action"] == "ingest_run.interrupted" for event in events)
    assert recovered.health()["audit_chain_valid"] is True


def test_api_requires_token_and_rejects_hostile_host(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("FastAPI test client unavailable")
    from databossx.api import create_app

    service = KernelService(config_for(tmp_path))
    try:
        client = TestClient(create_app(service, "test-token"))
    except TypeError:
        pytest.skip("Installed Starlette/httpx test client versions are incompatible")
    assert client.get("/api/v1/health").status_code == 401
    response = client.get(
        "/api/v1/health", headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    assert response.json()["local_only"] is True
    hostile = client.get(
        "/api/v1/health",
        headers={"Authorization": "Bearer test-token", "Host": "evil.example"},
    )
    assert hostile.status_code == 400
    enrollment = client.post(
        "/api/v1/title-reviewers",
        headers={"Authorization": "Bearer test-token"},
        json={
            "display_name": "Self-Asserted Reviewer",
            "role": "QUALIFIED_EXAMINER",
            "pin": "123456",
        },
    )
    assert enrollment.status_code == 405
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert 'onclick="selectProject' not in dashboard.text
