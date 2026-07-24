from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from .config import DataBossConfig
from .database import DataBossDatabase
from .hashing import copy_file_to_vault, sha256_bytes, vault_path
from .models import InventoryItem, InventoryResult, ProjectRecord, SourceConnectionRecord
from .orchestrator import seed_project_intake_run


SKIP_DIRS = {".git", ".pytest_cache", "__pycache__", "node_modules", "runtime", "output", ".venv", "venv"}


class SourceValidationError(ValueError):
    """A source root or template failed a fail-closed pre-flight check.

    Raised (rather than silently recording an empty/incomplete inventory) when a
    local source root is missing, is not a directory, is unreadable, or is empty
    without an explicit opt-in. Surfacing this as a task failure keeps a run from
    reporting COMPLETED when no source evidence was actually available.
    """


def _json(data: dict | list) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _require_readable_dir(root: Path) -> None:
    if not root.exists():
        raise SourceValidationError(f"Source root does not exist: {root}")
    if not root.is_dir():
        raise SourceValidationError(f"Source root is not a directory: {root}")
    if not os.access(root, os.R_OK | os.X_OK):
        raise SourceValidationError(f"Source root is not readable: {root}")


def _require_readable_file(path: Path) -> None:
    if not path.exists():
        raise SourceValidationError(f"File does not exist: {path}")
    if not path.is_file():
        raise SourceValidationError(f"Path is not a file: {path}")
    if not os.access(path, os.R_OK):
        raise SourceValidationError(f"File is not readable: {path}")


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
    if source_type == "local_disk":
        _require_readable_dir(root)
    db = DataBossDatabase(config.project_db_path(project_id))
    # Idempotent: a retry after a committed registration returns the existing
    # connection rather than inserting a duplicate row.
    existing = db.fetchone(
        """
        SELECT id FROM source_connections
         WHERE project_id = ? AND type = ? AND root_locator = ? AND access_mode = ?
         ORDER BY id LIMIT 1
        """,
        (project_id, source_type, str(root), access_mode),
    )
    if existing is not None:
        return SourceConnectionRecord(
            source_connection_id=int(existing["id"]),
            project_id=project_id,
            root_path=root,
            source_type=source_type,
            access_mode=access_mode,
        )
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


def _load_snapshot_items(conn, snapshot_id: int) -> list[InventoryItem]:
    """Rebuild the inventory item list for an already-committed snapshot."""
    rows = conn.execute(
        """
        SELECT av.id AS asset_version_id, av.asset_id AS asset_id, av.sha256 AS sha256,
               av.original_locator AS original_locator, av.duplicate_of_asset_version_id AS dup
          FROM asset_versions av
         WHERE av.source_snapshot_id = ?
         ORDER BY av.id
        """,
        (snapshot_id,),
    ).fetchall()
    return [
        InventoryItem(
            asset_id=int(row["asset_id"]),
            asset_version_id=int(row["asset_version_id"]),
            original_path=Path(row["original_locator"]),
            sha256=row["sha256"],
            duplicate_of_asset_version_id=row["dup"],
        )
        for row in rows
    ]


def inventory_source(
    config: DataBossConfig,
    project_id: str,
    source_connection_id: int,
    *,
    allow_empty: bool = False,
) -> InventoryResult:
    """Inventory one source connection into the content-addressed vault.

    Idempotent and resumable: the manifest hash is derived only from stable
    content (relative path, sha256, byte size), so a retry after a committed
    inventory finds the existing COMPLETE snapshot and returns it instead of
    re-inserting rows and hitting ``UNIQUE`` constraints. A partially-applied
    prior attempt is completed with select-or-insert / ``INSERT OR IGNORE``
    semantics.

    Fails closed: a missing/unreadable source directory raises, and an empty
    source raises unless ``allow_empty`` is explicitly set.
    """
    db = DataBossDatabase(config.project_db_path(project_id))
    row = db.fetchone("SELECT root_locator FROM source_connections WHERE id = ?", (source_connection_id,))
    if row is None:
        raise ValueError(f"Unknown source connection: {source_connection_id}")
    root = Path(row["root_locator"])
    _require_readable_dir(root)
    files = _iter_source_files(root)
    if not files and not allow_empty:
        raise SourceValidationError(
            f"Source root has no inventoryable files: {root} "
            "(pass allow_empty=True to record an intentional empty snapshot)"
        )

    # Copy bytes into the vault (idempotent, content-addressed) and build a
    # content-stable manifest that does not depend on database ids.
    scanned: list[tuple[Path, str, str, int]] = []  # (path, rel_path, sha256, byte_size)
    manifest_rows: list[dict] = []
    for path in files:
        stored = copy_file_to_vault(path, config.project_vault_root(project_id))
        rel_path = str(path.relative_to(root))
        scanned.append((path, rel_path, stored.sha256, stored.byte_size))
        manifest_rows.append(
            {"relative_path": rel_path, "sha256": stored.sha256, "byte_size": stored.byte_size}
        )
    manifest_rows.sort(key=lambda r: r["relative_path"])
    manifest_hash = sha256_bytes(_json(manifest_rows).encode("utf-8"))

    with db.connect() as conn:
        # Resume: a completed inventory for this exact manifest already exists.
        existing_snapshot = conn.execute(
            """
            SELECT id FROM source_snapshots
             WHERE source_connection_id = ? AND manifest_hash = ? AND completeness_status = 'COMPLETE'
             ORDER BY id LIMIT 1
            """,
            (source_connection_id, manifest_hash),
        ).fetchone()
        if existing_snapshot is not None:
            snapshot_id = int(existing_snapshot["id"])
            items = _load_snapshot_items(conn, snapshot_id)
            duplicate_count = sum(1 for it in items if it.duplicate_of_asset_version_id is not None)
            conn.commit()
            return InventoryResult(
                source_snapshot_id=snapshot_id,
                manifest_hash=manifest_hash,
                item_count=len(items),
                duplicate_count=duplicate_count,
                items=items,
            )

        snapshot_id = conn.execute(
            """
            INSERT INTO source_snapshots (source_connection_id, provider_cursor, manifest_hash, scanned_at, completeness_status)
            VALUES (?, '', ?, CURRENT_TIMESTAMP, 'PENDING')
            """,
            (source_connection_id, manifest_hash),
        ).lastrowid
        items = []
        sha_first_seen: dict[str, int] = {}
        for path, rel_path, sha256, byte_size in scanned:
            # Select-or-insert the asset by its natural key so a retry reuses it
            # instead of violating UNIQUE(project_id, logical_key, asset_class).
            asset_row = conn.execute(
                "SELECT id FROM assets WHERE project_id = ? AND logical_key = ? AND asset_class = 'source_document'",
                (project_id, rel_path),
            ).fetchone()
            if asset_row is None:
                asset_id = conn.execute(
                    """
                    INSERT INTO assets (project_id, logical_key, asset_class, first_seen_at)
                    VALUES (?, ?, 'source_document', CURRENT_TIMESTAMP)
                    """,
                    (project_id, rel_path),
                ).lastrowid
            else:
                asset_id = int(asset_row["id"])
            duplicate_of = sha_first_seen.get(sha256)
            conn.execute(
                """
                INSERT OR IGNORE INTO asset_versions (
                    asset_id, source_snapshot_id, sha256, mime_type, byte_size, original_locator,
                    vault_path, provider_version, duplicate_of_asset_version_id, created_at
                ) VALUES (?, ?, ?, '', ?, ?, ?, '', ?, CURRENT_TIMESTAMP)
                """,
                (
                    asset_id,
                    snapshot_id,
                    sha256,
                    byte_size,
                    str(path),
                    str(vault_path(config.project_vault_root(project_id), sha256)),
                    duplicate_of,
                ),
            )
            asset_version_id = int(
                conn.execute(
                    "SELECT id FROM asset_versions WHERE asset_id = ? AND sha256 = ?",
                    (asset_id, sha256),
                ).fetchone()["id"]
            )
            sha_first_seen.setdefault(sha256, asset_version_id)
            items.append(
                InventoryItem(
                    asset_id=asset_id,
                    asset_version_id=asset_version_id,
                    original_path=path,
                    sha256=sha256,
                    duplicate_of_asset_version_id=duplicate_of,
                )
            )
        conn.execute(
            "UPDATE source_snapshots SET completeness_status = 'COMPLETE' WHERE id = ?",
            (snapshot_id,),
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
    _require_readable_file(template)
    db = DataBossDatabase(config.project_db_path(project_id))
    stored = copy_file_to_vault(template, config.project_vault_root(project_id))
    resolved_name = template_name or template.stem
    with db.connect() as conn:
        # Select-or-insert the template asset by natural key so a retry does not
        # violate UNIQUE(project_id, logical_key, asset_class).
        asset_row = conn.execute(
            "SELECT id FROM assets WHERE project_id = ? AND logical_key = ? AND asset_class = 'workbook_template'",
            (project_id, template.name),
        ).fetchone()
        if asset_row is None:
            asset_id = conn.execute(
                """
                INSERT INTO assets (project_id, logical_key, asset_class, first_seen_at)
                VALUES (?, ?, 'workbook_template', CURRENT_TIMESTAMP)
                """,
                (project_id, template.name),
            ).lastrowid
        else:
            asset_id = int(asset_row["id"])
        conn.execute(
            """
            INSERT OR IGNORE INTO asset_versions (
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
        )
        asset_version_id = int(
            conn.execute(
                "SELECT id FROM asset_versions WHERE asset_id = ? AND sha256 = ?",
                (asset_id, stored.sha256),
            ).fetchone()["id"]
        )
        # Select-or-insert the template binding for this asset version + name.
        binding = conn.execute(
            "SELECT id FROM workbook_templates WHERE asset_version_id = ? AND template_name = ?",
            (asset_version_id, resolved_name),
        ).fetchone()
        if binding is None:
            workbook_template_id = conn.execute(
                """
                INSERT INTO workbook_templates (asset_version_id, template_name, approved_at, approved_by)
                VALUES (?, ?, CURRENT_TIMESTAMP, 'system')
                """,
                (asset_version_id, resolved_name),
            ).lastrowid
        else:
            workbook_template_id = int(binding["id"])
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
