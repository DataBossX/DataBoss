"""Durable single-writer job state and append-only audit history."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .contracts import canonical_hash, utc_now
from .security import redact


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    content_sha256 TEXT NOT NULL UNIQUE,
    operation TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN
      ('inbox','claimed','running','completed','failed','rejected','quarantine','cancelled')),
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    claimed_at TEXT,
    heartbeat_at TEXT,
    completed_at TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS task_state (
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    task_key TEXT NOT NULL,
    state TEXT NOT NULL,
    result_json TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(job_id, task_key)
);
CREATE TABLE IF NOT EXISTS audit_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update
BEFORE UPDATE ON audit_events BEGIN
  SELECT RAISE(ABORT, 'audit history is append-only');
END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete
BEFORE DELETE ON audit_events BEGIN
  SELECT RAISE(ABORT, 'audit history is append-only');
END;
"""


class DuplicateJob(ValueError):
    pass


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def append_audit(self, job_id: Optional[str], event_type: str, payload: Any) -> str:
        safe_payload = redact(payload)
        payload_json = json.dumps(safe_payload, sort_keys=True, separators=(",", ":"))
        row = self.connection.execute(
            "SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = row["event_hash"] if row else "0" * 64
        created_at = utc_now()
        event_hash = hashlib.sha256(
            f"{previous_hash}|{job_id or ''}|{event_type}|{payload_json}|{created_at}".encode()
        ).hexdigest()
        self.connection.execute(
            """INSERT INTO audit_events
               (job_id,event_type,payload_json,previous_hash,event_hash,created_at)
               VALUES (?,?,?,?,?,?)""",
            (job_id, event_type, payload_json, previous_hash, event_hash, created_at),
        )
        return event_hash

    def submit(self, payload: Dict[str, Any]) -> str:
        job_id = str(payload["job_id"])
        content_hash = canonical_hash(
            {
                "operation": payload["operation"],
                "project_id": payload.get("project_id"),
                "parameters": payload.get("parameters", {}),
                "input_artifacts": payload.get("input_artifacts", []),
            }
        )
        payload_json = json.dumps(redact(payload), sort_keys=True)
        try:
            with self.transaction():
                self.connection.execute(
                    """INSERT INTO jobs
                       (job_id,content_sha256,operation,state,payload_json,created_at)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        job_id,
                        content_hash,
                        payload["operation"],
                        "inbox",
                        payload_json,
                        utc_now(),
                    ),
                )
                self.append_audit(job_id, "JOB_ACCEPTED", {"content_sha256": content_hash})
        except sqlite3.IntegrityError as exc:
            raise DuplicateJob("duplicate job id or duplicate content") from exc
        return job_id

    def transition(self, job_id: str, expected: str, target: str, **fields: Any) -> None:
        allowed = {
            "inbox": {"claimed", "rejected", "quarantine", "cancelled"},
            "claimed": {"running", "failed", "cancelled"},
            "running": {"completed", "failed", "cancelled"},
        }
        if target not in allowed.get(expected, set()):
            raise ValueError(f"illegal job transition {expected} -> {target}")
        assignments = ["state=?"]
        values: list[Any] = [target]
        for key, value in fields.items():
            if key not in {"claimed_at", "heartbeat_at", "completed_at", "error"}:
                raise ValueError(f"unsupported state field: {key}")
            assignments.append(f"{key}=?")
            values.append(value)
        values.extend([job_id, expected])
        with self.transaction():
            cursor = self.connection.execute(
                f"UPDATE jobs SET {', '.join(assignments)} WHERE job_id=? AND state=?",
                values,
            )
            if cursor.rowcount != 1:
                raise ValueError("job state changed or job does not exist")
            self.append_audit(job_id, f"JOB_{target.upper()}", fields)

    def heartbeat(self, job_id: str) -> None:
        now = utc_now()
        with self.transaction():
            cursor = self.connection.execute(
                "UPDATE jobs SET heartbeat_at=? WHERE job_id=? AND state='running'",
                (now, job_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("heartbeat requires a running job")
            self.append_audit(job_id, "HEARTBEAT", {"at": now})

    def get(self, job_id: str) -> Dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return dict(row)
