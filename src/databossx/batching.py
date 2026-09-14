"""Batch task claiming and parallel source hashing."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .database import DataBossDatabase
from .hashing import StoredAsset, copy_file_to_vault
from .receipts import canonical_dumps


def utc_stamp(moment: datetime | None = None) -> str:
    current = moment or datetime.now(timezone.utc)
    return current.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class ClaimedTask:
    task_id: int
    run_id: int
    task_type: str
    priority: int
    payload_json: str
    lease_id: int
    attempt_id: int
    worker_id: str
    expires_at: str


def hash_files_parallel(
    paths: Sequence[Path],
    vault_root: str | Path,
    *,
    max_workers: int = 8,
) -> list[tuple[Path, StoredAsset]]:
    """Hash and vault files concurrently; return results in input order."""
    if not paths:
        return []
    workers = max(1, min(max_workers, len(paths)))

    def _store(path: Path) -> tuple[Path, StoredAsset]:
        return path, copy_file_to_vault(path, vault_root)

    if workers == 1:
        return [_store(path) for path in paths]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_store, paths))


def claim_ready_tasks(
    db: DataBossDatabase,
    *,
    worker_id: str,
    capabilities: Sequence[str],
    limit: int = 8,
    lease_seconds: int = 60,
) -> list[ClaimedTask]:
    """Atomically lease a batch of READY tasks that match worker capabilities."""
    if limit <= 0 or not capabilities:
        return []
    now = datetime.now(timezone.utc)
    leased_at = utc_stamp(now)
    expires_at = utc_stamp(now + timedelta(seconds=lease_seconds))
    placeholders = ",".join("?" * len(capabilities))
    claimed: list[ClaimedTask] = []
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            f"""
            SELECT t.id, t.run_id, t.task_type, t.priority, t.payload_json
              FROM tasks t
             WHERE t.state = 'READY'
               AND t.task_type IN ({placeholders})
               AND NOT EXISTS (
                   SELECT 1 FROM task_leases l
                    WHERE l.task_id = t.id
                      AND l.expires_at > ?
               )
             ORDER BY t.priority ASC, t.id ASC
             LIMIT ?
            """,
            (*capabilities, leased_at, limit),
        ).fetchall()
        for row in rows:
            conn.execute("UPDATE tasks SET state = 'LEASED' WHERE id = ?", (row["id"],))
            lease_id = conn.execute(
                """
                INSERT INTO task_leases (task_id, worker_id, leased_at, expires_at, heartbeat_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (row["id"], worker_id, leased_at, expires_at, leased_at),
            ).lastrowid
            attempt_id = conn.execute(
                """
                INSERT INTO task_attempts (task_id, worker_name, status)
                VALUES (?, ?, 'RUNNING')
                """,
                (row["id"], worker_id),
            ).lastrowid
            claimed.append(
                ClaimedTask(
                    task_id=int(row["id"]),
                    run_id=int(row["run_id"]),
                    task_type=str(row["task_type"]),
                    priority=int(row["priority"]),
                    payload_json=str(row["payload_json"]),
                    lease_id=int(lease_id),
                    attempt_id=int(attempt_id),
                    worker_id=worker_id,
                    expires_at=expires_at,
                )
            )
        conn.commit()
    return claimed


def complete_task(
    db: DataBossDatabase,
    claimed: ClaimedTask,
    *,
    status: str,
    error_code: str | None = None,
) -> None:
    task_state = "SUCCEEDED" if status == "SUCCEEDED" else "FAILED_TERMINAL"
    with db.connect() as conn:
        conn.execute("UPDATE tasks SET state = ? WHERE id = ?", (task_state, claimed.task_id))
        conn.execute(
            """
            UPDATE task_attempts
               SET completed_at = CURRENT_TIMESTAMP, status = ?, error_code = ?
             WHERE id = ?
            """,
            (status, error_code, claimed.attempt_id),
        )
        conn.commit()


def persist_receipt_row(
    conn,
    project_id: str,
    kind: str,
    status: str,
    sealed: Mapping[str, Any],
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO engine_receipts (
            receipt_sha256, project_id, kind, status, body_json
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            sealed["receipt_sha256"],
            project_id,
            kind,
            status,
            canonical_dumps(sealed),
        ),
    )


def persist_comparison_row(
    conn,
    project_id: str,
    subject_key: str,
    result_json: str,
    conflict_count: int,
    receipt_sha256: str,
) -> None:
    conn.execute(
        """
        INSERT INTO candidate_comparisons (
            project_id, subject_key, result_json, conflict_count, receipt_sha256
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (project_id, subject_key, result_json, conflict_count, receipt_sha256),
    )


def persist_cache_row(
    conn,
    project_id: str,
    cache_key: str,
    recipe_version: str,
    input_manifest_hash: str,
    output_hash: str,
    payload_json: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO derived_cache (
            cache_key, project_id, recipe_version, input_manifest_hash, output_hash, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (cache_key, project_id, recipe_version, input_manifest_hash, output_hash, payload_json),
    )
