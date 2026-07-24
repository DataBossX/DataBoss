from __future__ import annotations

import json
import uuid
from pathlib import Path

from .config import DataBossConfig
from .database import DataBossDatabase
from .hashing import copy_file_to_vault, sha256_bytes
from .models import InventoryItem, InventoryResult, ProjectRecord, SourceConnectionRecord
from .orchestrator import seed_project_intake_run


SKIP_DIRS = {".git", ".pytest_cache", "__pycache__", "node_modules", "runtime", "output", ".venv", "venv"}


def _json(data: dict | list) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def create_project(
    config: DataBossConfig,
    *,
    name: str,
    jurisdiction_code: str,
    policy_profile: str = "default",
    project_id: str | None = None,
    source_roots: list[str] | None = None,
    template_path: str | Path | None = None,
) -> ProjectRecord:
    project_id = project_id or uuid.uuid4().hex[:12]
    config.ensure_runtime_dirs(project_id)
    db = DataBossDatabase(config.project_db_path(project_id))
    db.initialize()
    with db.connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO jurisdictions (code, name) VALUES (?, ?)",
            (jurisdiction_code, jurisdiction_code),
        )
        conn.execute(
            """
            INSERT INTO projects (id, name, jurisdiction_code, policy_version, status, root_path)
            VALUES (?, ?, ?, ?, 'DRAFT', ?)
            """,
            (
                project_id,
                name,
                jurisdiction_code,
                policy_profile,
                str(config.project_root(project_id)),
            ),
        )
        conn.execute(
            """
            INSERT INTO title_projects (project_id, report_type, release_state, notes)
            VALUES (?, 'title_report', 'DRAFT', '')
            """,
            (project_id,),
        )
        conn.commit()
    seed_project_intake_run(
        db,
        project_id,
        source_roots=source_roots,
        template_path=str(template_path) if template_path is not None else None,
    )
    db.audit(
        project_id,
        "project.created",
        "project",
        project_id,
        _json({"name": name, "jurisdiction_code": jurisdiction_code, "policy_profile": policy_profile}),
    )
    return ProjectRecord(
        project_id=project_id,
        name=name,
        jurisdiction_code=jurisdiction_code,
        policy_profile=policy_profile,
        root_path=config.project_root(project_id),
    )


def register_source_connection(
    config: DataBossConfig,
    project_id: str,
    root_path: str | Path,
    *,
    source_type: str = "local_disk",
    access_mode: str = "read_only",
) -> SourceConnectionRecord:
    root = Path(root_path).resolve()
    db = DataBossDatabase(config.project_db_path(project_id))
    source_connection_id = db.execute(
        """
        INSERT INTO source_connections (project_id, type, root_locator, access_mode, enabled)
        VALUES (?, ?, ?, ?, 1)
        """,
        (project_id, source_type, str(root), access_mode),
    )
    db.audit(
        project_id,
        "source.registered",
        "source_connection",
        str(source_connection_id),
        _json({"root_path": str(root), "source_type": source_type, "access_mode": access_mode}),
    )
    return SourceConnectionRecord(
        source_connection_id=source_connection_id,
        project_id=project_id,
        root_path=root,
        source_type=source_type,
        access_mode=access_mode,
    )


def _iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def inventory_source(
    config: DataBossConfig,
    project_id: str,
    source_connection_id: int,
) -> InventoryResult:
    db = DataBossDatabase(config.project_db_path(project_id))
    row = db.fetchone("SELECT root_locator FROM source_connections WHERE id = ?", (source_connection_id,))
    if row is None:
        raise ValueError(f"Unknown source connection: {source_connection_id}")
    root = Path(row["root_locator"])
    files = _iter_source_files(root)
    manifest_rows: list[dict] = []
    with db.connect() as conn:
        snapshot_id = conn.execute(
            """
            INSERT INTO source_snapshots (source_connection_id, provider_cursor, manifest_hash, scanned_at, completeness_status)
            VALUES (?, '', '', CURRENT_TIMESTAMP, 'PENDING')
            """,
            (source_connection_id,),
        ).lastrowid
        items: list[InventoryItem] = []
        sha_first_seen: dict[str, int] = {}
        for path in files:
            stored = copy_file_to_vault(path, config.project_vault_root(project_id))
            rel_path = str(path.relative_to(root))
            asset_id = conn.execute(
                """
                INSERT INTO assets (project_id, logical_key, asset_class, first_seen_at)
                VALUES (?, ?, 'source_document', CURRENT_TIMESTAMP)
                """,
                (project_id, rel_path),
            ).lastrowid
            duplicate_of = sha_first_seen.get(stored.sha256)
            asset_version_id = conn.execute(
                """
                INSERT INTO asset_versions (
                    asset_id, source_snapshot_id, sha256, mime_type, byte_size, original_locator,
                    vault_path, provider_version, duplicate_of_asset_version_id, created_at
                ) VALUES (?, ?, ?, '', ?, ?, ?, '', ?, CURRENT_TIMESTAMP)
                """,
                (
                    asset_id,
                    snapshot_id,
                    stored.sha256,
                    stored.byte_size,
                    str(path),
                    str(stored.vault_path),
                    duplicate_of,
                ),
            ).lastrowid
            sha_first_seen.setdefault(stored.sha256, asset_version_id)
            items.append(
                InventoryItem(
                    asset_id=asset_id,
                    asset_version_id=asset_version_id,
                    original_path=path,
                    sha256=stored.sha256,
                    duplicate_of_asset_version_id=duplicate_of,
                )
            )
            manifest_rows.append(
                {
                    "relative_path": rel_path,
                    "sha256": stored.sha256,
                    "byte_size": stored.byte_size,
                    "duplicate_of_asset_version_id": duplicate_of,
                }
            )
        manifest_hash = sha256_bytes(_json(manifest_rows).encode("utf-8"))
        conn.execute(
            """
            UPDATE source_snapshots
               SET manifest_hash = ?, completeness_status = 'COMPLETE'
             WHERE id = ?
            """,
            (manifest_hash, snapshot_id),
        )
        conn.commit()
    duplicate_count = sum(1 for item in items if item.duplicate_of_asset_version_id is not None)
    snapshot_path = config.project_snapshots_root(project_id) / f"snapshot_{snapshot_id}.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "project_id": project_id,
                "source_connection_id": source_connection_id,
                "manifest_hash": manifest_hash,
                "files": manifest_rows,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    db.audit(
        project_id,
        "source.inventory.completed",
        "source_snapshot",
        str(snapshot_id),
        _json({"manifest_hash": manifest_hash, "item_count": len(items), "duplicate_count": duplicate_count}),
    )
    return InventoryResult(
        source_snapshot_id=snapshot_id,
        manifest_hash=manifest_hash,
        item_count=len(items),
        duplicate_count=duplicate_count,
        items=items,
    )


def register_workbook_template(
    config: DataBossConfig,
    project_id: str,
    template_path: str | Path,
    *,
    template_name: str | None = None,
) -> int:
    template = Path(template_path).resolve()
    db = DataBossDatabase(config.project_db_path(project_id))
    stored = copy_file_to_vault(template, config.project_vault_root(project_id))
    with db.connect() as conn:
        asset_id = conn.execute(
            """
            INSERT INTO assets (project_id, logical_key, asset_class, first_seen_at)
            VALUES (?, ?, 'workbook_template', CURRENT_TIMESTAMP)
            """,
            (project_id, template.name),
        ).lastrowid
        asset_version_id = conn.execute(
            """
            INSERT INTO asset_versions (
                asset_id, source_snapshot_id, sha256, mime_type, byte_size, original_locator,
                vault_path, provider_version, duplicate_of_asset_version_id, created_at
            ) VALUES (?, NULL, ?, ?, ?, ?, ?, '', NULL, CURRENT_TIMESTAMP)
            """,
            (
                asset_id,
                stored.sha256,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                stored.byte_size,
                str(template),
                str(stored.vault_path),
            ),
        ).lastrowid
        workbook_template_id = conn.execute(
            """
            INSERT INTO workbook_templates (asset_version_id, template_name, approved_at, approved_by)
            VALUES (?, ?, CURRENT_TIMESTAMP, 'system')
            """,
            (asset_version_id, template_name or template.stem),
        ).lastrowid
        conn.execute(
            """
            UPDATE title_projects
               SET template_asset_version_id = ?
             WHERE project_id = ?
            """,
            (asset_version_id, project_id),
        )
        conn.commit()
    db.audit(
        project_id,
        "template.registered",
        "workbook_template",
        str(workbook_template_id),
        _json({"template_path": str(template), "asset_version_id": asset_version_id}),
    )
    return workbook_template_id
