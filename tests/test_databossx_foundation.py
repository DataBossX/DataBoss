from __future__ import annotations

from pathlib import Path

from databossx.config import DataBossConfig
from databossx.database import DataBossDatabase
from databossx.hashing import copy_file_to_vault, sha256_file
from databossx.intake import (
    create_project,
    inventory_source,
    register_source_connection,
    register_workbook_template,
)


def test_database_initialization_sets_wal_and_creates_core_tables(tmp_path):
    db = DataBossDatabase(tmp_path / "project.db")
    db.initialize()
    pragma_row = db.fetchone("PRAGMA journal_mode;")
    assert pragma_row[0].lower() == "wal"
    tables = {
        row["name"]
        for row in db.fetchall("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")
    }
    assert {"projects", "asset_versions", "audit_events", "workflow_definitions", "tasks"} <= tables


def test_copy_file_to_vault_uses_content_addressed_path(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("databossx", encoding="utf-8")
    stored = copy_file_to_vault(source, tmp_path / "vault" / "sha256")
    assert stored.vault_path.exists()
    assert stored.vault_path.name == sha256_file(source)
    assert stored.vault_path.parent.name == stored.sha256[:2]
    assert stored.vault_path.read_text(encoding="utf-8") == "databossx"


def test_project_intake_inventory_and_template_registration(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    config = DataBossConfig.from_repo_root(repo_root)

    source_root = tmp_path / "source_docs"
    source_root.mkdir()
    first = source_root / "deed.txt"
    second = source_root / "dup.txt"
    third = source_root / "lease.txt"
    first.write_text("same-bytes", encoding="utf-8")
    second.write_text("same-bytes", encoding="utf-8")
    third.write_text("different", encoding="utf-8")
    template = tmp_path / "template.xlsx"
    template.write_bytes(b"placeholder-xlsx")

    project = create_project(
        config,
        name="Section 32",
        jurisdiction_code="OK",
        project_id="proj123",
    )
    source = register_source_connection(config, project.project_id, source_root)
    inventory = inventory_source(config, project.project_id, source.source_connection_id)
    template_id = register_workbook_template(config, project.project_id, template)

    assert project.root_path == config.project_root("proj123")
    assert inventory.item_count == 3
    assert inventory.duplicate_count == 1
    assert (config.project_snapshots_root(project.project_id) / f"snapshot_{inventory.source_snapshot_id}.json").exists()
    assert template_id > 0

    db = DataBossDatabase(config.project_db_path(project.project_id))
    asset_versions = db.fetchall(
        "SELECT sha256, duplicate_of_asset_version_id, original_locator FROM asset_versions ORDER BY id"
    )
    assert len(asset_versions) == 4  # 3 source docs + 1 template
    duplicate_rows = [row for row in asset_versions if row["duplicate_of_asset_version_id"] is not None]
    assert len(duplicate_rows) == 1
    source_rows = [row for row in asset_versions if Path(row["original_locator"]).parent == source_root]
    assert len(source_rows) == 3
    template_row = db.fetchone(
        """
        SELECT tp.template_asset_version_id
          FROM title_projects tp
         WHERE tp.project_id = ?
        """,
        (project.project_id,),
    )
    assert template_row["template_asset_version_id"] is not None
    audit_count = db.fetchone("SELECT COUNT(*) FROM audit_events WHERE project_id = ?", (project.project_id,))
    assert audit_count[0] >= 4
