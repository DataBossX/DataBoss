"""Bridge the Command Center run into the foundation's audit store.

The foundation layer (``databossx.database`` / ``databossx.intake``) provides a
SQLite-backed, FTS-searchable ``audit_events`` table and a content-addressed
vault. This bridge records each Command Center run there so the evidence trail is
durable and queryable, not just a flat log file -- unifying the two DataBossX
layers.

It is **best-effort and opt-in**: any failure (missing schema, locked DB, FK
edge case) is swallowed and reported as ``None`` so the audit store can never
break a run or block a deliverable. The flat ``databossx_audit.log`` and
``run_manifest.json`` remain the primary evidence trail.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def _slug(text: str) -> str:
    import re
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(text or "")).strip("_").lower()
    return s or "project"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def record_run(
    output_dir: Path,
    *,
    project_name: str,
    project_key: str,
    jurisdiction: str,
    rag: str,
    counts: Dict[str, int],
    defect_count: int,
    deliverables: Dict[str, object],
) -> Optional[str]:
    """Record this run in a foundation audit DB under ``output_dir/runtime``.

    Returns the DB path (str) on success, or ``None`` if the audit store could
    not be written (best-effort). The DB lives under ``runtime/`` inside the
    managed output folder, so it is git-ignored and never touches sources.
    """
    try:
        from .config import DataBossConfig
        from .database import DataBossDatabase
        from .hashing import sha256_file
        from .intake import create_project
    except Exception:
        return None

    try:
        config = DataBossConfig.from_repo_root(Path(output_dir))
        project_id = _slug(project_key)
        db_path = config.project_db_path(project_id)

        # Create the project (idempotently) so audit_events' FK is satisfied.
        if not db_path.exists():
            create_project(config, name=project_name,
                           jurisdiction_code=(jurisdiction or "NA"),
                           project_id=project_id)
        db = DataBossDatabase(db_path)

        run_id = _ts()
        db.audit(project_id, "run.completed", "run", run_id, json.dumps({
            "project": project_name, "rag": rag, "counts": counts,
            "defect_count": defect_count,
        }, sort_keys=True))

        # Record each produced deliverable with its content hash (evidence).
        for name, value in deliverables.items():
            paths = value if isinstance(value, list) else [value]
            for p in paths:
                fp = Path(p)
                if not fp.is_absolute():
                    fp = Path(output_dir) / fp
                if fp.exists() and fp.is_file():
                    try:
                        digest = sha256_file(fp)
                    except OSError:
                        continue
                    db.audit(project_id, "deliverable.produced", "artifact",
                             f"{run_id}:{name}", json.dumps({
                                 "name": name, "file": fp.name,
                                 "sha256": digest, "bytes": fp.stat().st_size,
                             }, sort_keys=True))
        return str(db_path)
    except Exception:
        return None


def read_audit_events(db_path: Path, project_key: str,
                      limit: int = 50) -> List[dict]:
    """Read recent audit events back (used by tests and inspection)."""
    from .database import DataBossDatabase

    db = DataBossDatabase(Path(db_path))
    rows = db.fetchall(
        "SELECT event_type, entity_type, entity_id, payload_json, created_at "
        "FROM audit_events WHERE project_id = ? ORDER BY id DESC LIMIT ?",
        (_slug(project_key), limit))
    return [dict(r) for r in rows]
