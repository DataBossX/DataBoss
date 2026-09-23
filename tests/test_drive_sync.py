from __future__ import annotations

from pathlib import Path

from databossx.cli import main
from databossx.config import DataBossConfig
from databossx.connectors.drive import DriveConnection, DriveWriteRefused, GoogleDriveConnector
from databossx.connectors.local import LocalFolderConnector
from databossx.connectors.sync import apply_vault_ingest, plan_sync
from databossx.hashing import sha256_file
from databossx.intake import create_project
from databossx.policy import PolicyEngine


def test_drive_scan_is_read_only_and_incremental(tmp_path):
    mirror = tmp_path / "drive"
    (mirror / "source").mkdir(parents=True)
    doc = mirror / "source" / "deed.txt"
    doc.write_text("SYNTHETIC", encoding="utf-8")
    connector = GoogleDriveConnector(DriveConnection(root_locator=str(mirror)))
    dry = connector.scan(dry_run=True)
    hashed = connector.scan(dry_run=False, cursor="page-1")
    assert dry.write_attempted is False
    assert hashed.write_attempted is False
    assert dry.cursor
    assert hashed.items[0].checksum == sha256_file(doc)
    denied = connector.refuse_write()
    assert denied.allowed is False


def test_google_api_backend_uses_injected_list_only():
    def fake_list(cursor: str):
        return [
            {
                "id": "file1",
                "name": "synthetic.txt",
                "mimeType": "text/plain",
                "size": 4,
                "md5Checksum": "abc",
                "nextPageToken": "google:complete",
            }
        ]

    connector = GoogleDriveConnector(
        DriveConnection(root_locator="selected", backend="google_api", credential_ref="env:DRIVE_TOKEN"),
        api_list=fake_list,
    )
    scan = connector.scan(dry_run=True, cursor="")
    assert scan.items[0].provider_id == "file1"
    assert scan.write_attempted is False


def test_sync_plan_copies_to_vault_never_provider(tmp_path):
    left_root = tmp_path / "pc"
    right_root = tmp_path / "drive_export"
    left_root.mkdir()
    right_root.mkdir()
    (left_root / "a.txt").write_text("alpha", encoding="utf-8")
    (right_root / "b.txt").write_text("beta", encoding="utf-8")
    (left_root / "same.txt").write_text("same", encoding="utf-8")
    (right_root / "same.txt").write_text("same", encoding="utf-8")
    left = LocalFolderConnector(left_root).scan(dry_run=False).items
    right = LocalFolderConnector(right_root).scan(dry_run=False).items
    plan = plan_sync(left, right)
    assert plan.write_to_provider is False
    actions = {a.relative_path: a.action for a in plan.actions}
    assert actions["a.txt"] == "copy_to_vault"
    assert actions["b.txt"] == "copy_to_vault"
    assert actions["same.txt"] == "identical"

    config = DataBossConfig.from_repo_root(tmp_path / "repo")
    project = create_project(config, name="Sync", jurisdiction_code="OK", project_id="sync1")
    ingested = apply_vault_ingest(config, project.project_id, plan)
    assert len(ingested) == 2
    assert (left_root / "a.txt").read_text(encoding="utf-8") == "alpha"
    plan.write_to_provider = True
    try:
        apply_vault_ingest(config, project.project_id, plan)
        assert False, "provider write must be refused"
    except DriveWriteRefused:
        pass


def test_cli_health_and_drive_scan(tmp_path, capsys):
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    (mirror / "note.txt").write_text("synthetic", encoding="utf-8")
    assert main(["health"]) == 0
    assert main(["drive-scan", "--root", str(mirror), "--hash"]) == 0
    out = capsys.readouterr().out
    assert "external_write" in out or "note.txt" in out
