from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from databossx.config import KernelConfig
from databossx.service import KernelService
from databossx.vault import VaultError, sha256_file


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
