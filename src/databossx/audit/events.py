"""Append-only audit event log backed by SQLite.

The Python API only ever exposes ``record`` (INSERT) and ``query``
(SELECT); there is no update/delete method. The underlying table also has
``BEFORE UPDATE``/``BEFORE DELETE`` triggers (see
``migrations/001_initial.sql``) that abort any attempt to mutate or remove
a row, so the immutability guarantee holds even if a caller bypasses this
module and talks to the database directly.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _new_id() -> str:
    return str(uuid.uuid4())


class AuditLog:
    """An append-only audit event log."""

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
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                actor TEXT,
                project_id TEXT,
                task_id TEXT,
                artifact_hash TEXT,
                payload_json TEXT,
                occurred_at TEXT NOT NULL
            );

            CREATE TRIGGER IF NOT EXISTS audit_events_no_update
            BEFORE UPDATE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit_events is append-only: UPDATE is forbidden');
            END;

            CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
            BEFORE DELETE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit_events is append-only: DELETE is forbidden');
            END;
            """
        )
        conn.commit()

    def record(
        self,
        event_type: str,
        actor: str | None = None,
        project_id: str | None = None,
        task_id: str | None = None,
        artifact_hash: str | None = None,
        payload: dict | None = None,
    ) -> str:
        """Insert an immutable audit event row; return the new event id."""
        event_id = _new_id()
        occurred_at = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload) if payload is not None else None
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO audit_events
                    (id, event_type, actor, project_id, task_id,
                     artifact_hash, payload_json, occurred_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    event_type,
                    actor,
                    project_id,
                    task_id,
                    artifact_hash,
                    payload_json,
                    occurred_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return event_id

    def query(
        self,
        project_id: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Return audit events matching the given filters, newest first."""
        clauses: list[str] = []
        params: list[object] = []
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if since is not None:
            clauses.append("occurred_at >= ?")
            params.append(since.isoformat())

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT * FROM audit_events {where} "
            "ORDER BY occurred_at DESC LIMIT ?"
        )
        params.append(limit)

        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
