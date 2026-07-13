"""Durable database-backed task graph with leases and dependency promotion.

Tasks move through the state machine defined in the build plan:
``PLANNED -> READY -> LEASED -> RUNNING -> SUCCEEDED`` (or
``FAILED_RETRYABLE`` / ``FAILED_TERMINAL`` on failure). All state
transitions are performed inside a single SQLite transaction so concurrent
workers never observe a partially-updated task.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


class TaskGraph:
    """A durable task graph backed by a SQLite database."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        conn = self._connect()
        try:
            self._ensure_schema(conn)
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        # Minimal, self-contained schema so TaskGraph can be used without
        # first running the full migration set (e.g. in isolated tests).
        # Column shapes are kept consistent with migrations/001_initial.sql.
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                worker_type TEXT NOT NULL,
                input_json TEXT NOT NULL,
                output_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                lease_expires_at TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS task_dependencies (
                upstream_task_id TEXT NOT NULL,
                downstream_task_id TEXT NOT NULL,
                PRIMARY KEY (upstream_task_id, downstream_task_id)
            );
            CREATE TABLE IF NOT EXISTS task_leases (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                heartbeat_at TEXT,
                duration_seconds INTEGER NOT NULL,
                released INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS task_attempts (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                outcome TEXT,
                error_message TEXT
            );
            """
        )
        conn.commit()

    def add_task(
        self,
        run_id: str,
        name: str,
        worker_type: str,
        input_json: str,
        depends_on: list[str] | None = None,
    ) -> str:
        """Insert a PLANNED task, wire up its dependencies, return its id."""
        depends_on = depends_on or []
        task_id = _new_id()
        now = _now_iso()
        conn = self._connect()
        try:
            conn.execute("BEGIN")
            conn.execute(
                """
                INSERT INTO tasks
                    (id, run_id, name, status, worker_type, input_json,
                     output_json, created_at, updated_at, lease_expires_at,
                     attempt_count)
                VALUES (?, ?, ?, 'PLANNED', ?, ?, NULL, ?, ?, NULL, 0)
                """,
                (task_id, run_id, name, worker_type, input_json, now, now),
            )
            for upstream_id in depends_on:
                conn.execute(
                    "INSERT OR IGNORE INTO task_dependencies "
                    "(upstream_task_id, downstream_task_id) VALUES (?, ?)",
                    (upstream_id, task_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return task_id

    def ready_tasks(self, run_id: str) -> list[dict]:
        """Return tasks currently in the READY state for a run."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE run_id = ? AND status = 'READY' "
                "ORDER BY created_at",
                (run_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def promote_ready(self, run_id: str) -> int:
        """Move PLANNED -> READY for tasks whose dependencies all SUCCEEDED."""
        conn = self._connect()
        try:
            conn.execute("BEGIN")
            planned = conn.execute(
                "SELECT id FROM tasks WHERE run_id = ? AND status = 'PLANNED'",
                (run_id,),
            ).fetchall()
            promoted = 0
            now = _now_iso()
            for row in planned:
                task_id = row["id"]
                deps = conn.execute(
                    "SELECT upstream_task_id FROM task_dependencies "
                    "WHERE downstream_task_id = ?",
                    (task_id,),
                ).fetchall()
                if not deps:
                    all_done = True
                else:
                    upstream_ids = [d["upstream_task_id"] for d in deps]
                    placeholders = ",".join("?" for _ in upstream_ids)
                    statuses = conn.execute(
                        f"SELECT status FROM tasks WHERE id IN ({placeholders})",
                        upstream_ids,
                    ).fetchall()
                    all_done = len(statuses) == len(upstream_ids) and all(
                        s["status"] == "SUCCEEDED" for s in statuses
                    )
                if all_done:
                    conn.execute(
                        "UPDATE tasks SET status = 'READY', updated_at = ? WHERE id = ?",
                        (now, task_id),
                    )
                    promoted += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return promoted

    def acquire_lease(
        self, task_id: str, worker_id: str, duration_seconds: int = 300
    ) -> str | None:
        """Atomically move a READY task to LEASED and grant a lease."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row is None or row["status"] != "READY":
                conn.rollback()
                return None

            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=duration_seconds)
            lease_id = _new_id()
            conn.execute(
                """
                INSERT INTO task_leases
                    (id, task_id, worker_id, granted_at, expires_at,
                     heartbeat_at, duration_seconds, released)
                VALUES (?, ?, ?, ?, ?, NULL, ?, 0)
                """,
                (
                    lease_id,
                    task_id,
                    worker_id,
                    now.isoformat(),
                    expires_at.isoformat(),
                    duration_seconds,
                ),
            )
            conn.execute(
                "UPDATE tasks SET status = 'LEASED', lease_expires_at = ?, "
                "updated_at = ?, attempt_count = attempt_count + 1 WHERE id = ?",
                (expires_at.isoformat(), now.isoformat(), task_id),
            )
            attempt_id = _new_id()
            conn.execute(
                "INSERT INTO task_attempts (id, task_id, started_at) VALUES (?, ?, ?)",
                (attempt_id, task_id, now.isoformat()),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return lease_id

    def heartbeat(self, lease_id: str) -> bool:
        """Extend a lease's expiry by its original duration."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT task_id, duration_seconds, released FROM task_leases WHERE id = ?",
                (lease_id,),
            ).fetchone()
            if row is None or row["released"]:
                conn.rollback()
                return False

            now = datetime.now(timezone.utc)
            new_expiry = now + timedelta(seconds=row["duration_seconds"])
            conn.execute(
                "UPDATE task_leases SET heartbeat_at = ?, expires_at = ? WHERE id = ?",
                (now.isoformat(), new_expiry.isoformat(), lease_id),
            )
            conn.execute(
                "UPDATE tasks SET lease_expires_at = ?, updated_at = ? WHERE id = ?",
                (new_expiry.isoformat(), now.isoformat(), row["task_id"]),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return True

    def complete_task(self, lease_id: str, output_json: str) -> None:
        """Mark a task SUCCEEDED, release its lease, unblock downstream tasks."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            lease_row = conn.execute(
                "SELECT task_id FROM task_leases WHERE id = ?", (lease_id,)
            ).fetchone()
            if lease_row is None:
                raise KeyError(f"no such lease: {lease_id!r}")
            task_id = lease_row["task_id"]
            now = _now_iso()

            conn.execute(
                "UPDATE tasks SET status = 'SUCCEEDED', output_json = ?, "
                "lease_expires_at = NULL, updated_at = ? WHERE id = ?",
                (output_json, now, task_id),
            )
            conn.execute(
                "UPDATE task_leases SET released = 1 WHERE id = ?", (lease_id,)
            )
            conn.execute(
                "UPDATE task_attempts SET completed_at = ?, outcome = 'SUCCEEDED' "
                "WHERE task_id = ? AND completed_at IS NULL",
                (now, task_id),
            )

            run_row = conn.execute(
                "SELECT run_id FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            run_id = run_row["run_id"]

            downstream = conn.execute(
                "SELECT downstream_task_id FROM task_dependencies "
                "WHERE upstream_task_id = ?",
                (task_id,),
            ).fetchall()
            for row in downstream:
                downstream_id = row["downstream_task_id"]
                deps = conn.execute(
                    "SELECT upstream_task_id FROM task_dependencies "
                    "WHERE downstream_task_id = ?",
                    (downstream_id,),
                ).fetchall()
                upstream_ids = [d["upstream_task_id"] for d in deps]
                placeholders = ",".join("?" for _ in upstream_ids)
                statuses = conn.execute(
                    f"SELECT status FROM tasks WHERE id IN ({placeholders})",
                    upstream_ids,
                ).fetchall()
                all_done = len(statuses) == len(upstream_ids) and all(
                    s["status"] == "SUCCEEDED" for s in statuses
                )
                if all_done:
                    down_status = conn.execute(
                        "SELECT status FROM tasks WHERE id = ?", (downstream_id,)
                    ).fetchone()
                    if down_status and down_status["status"] == "PLANNED":
                        conn.execute(
                            "UPDATE tasks SET status = 'READY', updated_at = ? "
                            "WHERE id = ?",
                            (now, downstream_id),
                        )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def fail_task(self, lease_id: str, error: str, retryable: bool = True) -> None:
        """Mark a task FAILED_RETRYABLE or FAILED_TERMINAL and release its lease."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            lease_row = conn.execute(
                "SELECT task_id FROM task_leases WHERE id = ?", (lease_id,)
            ).fetchone()
            if lease_row is None:
                raise KeyError(f"no such lease: {lease_id!r}")
            task_id = lease_row["task_id"]
            now = _now_iso()
            new_status = "FAILED_RETRYABLE" if retryable else "FAILED_TERMINAL"

            conn.execute(
                "UPDATE tasks SET status = ?, lease_expires_at = NULL, "
                "updated_at = ? WHERE id = ?",
                (new_status, now, task_id),
            )
            conn.execute(
                "UPDATE task_leases SET released = 1 WHERE id = ?", (lease_id,)
            )
            conn.execute(
                "UPDATE task_attempts SET completed_at = ?, outcome = ?, "
                "error_message = ? WHERE task_id = ? AND completed_at IS NULL",
                (now, new_status, error, task_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def expire_leases(self) -> int:
        """Recover tasks whose lease has expired: LEASED -> READY."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()
            expired = conn.execute(
                """
                SELECT tl.id AS lease_id, tl.task_id AS task_id
                FROM task_leases tl
                JOIN tasks t ON t.id = tl.task_id
                WHERE tl.released = 0
                  AND t.status = 'LEASED'
                  AND tl.expires_at < ?
                """,
                (now_iso,),
            ).fetchall()
            recovered = 0
            for row in expired:
                conn.execute(
                    "UPDATE task_leases SET released = 1 WHERE id = ?",
                    (row["lease_id"],),
                )
                conn.execute(
                    "UPDATE tasks SET status = 'READY', lease_expires_at = NULL, "
                    "updated_at = ? WHERE id = ?",
                    (now_iso, row["task_id"]),
                )
                recovered += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return recovered
