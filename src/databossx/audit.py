from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

GENESIS_HASH = "0" * 64


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class AuditWriter:
    def append(
        self,
        connection: sqlite3.Connection,
        *,
        action: str,
        object_type: str,
        object_id: str,
        project_id: str | None = None,
        run_id: str | None = None,
        details: dict | None = None,
        actor: str = "local-operator",
    ) -> str:
        previous = connection.execute(
            "SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else GENESIS_HASH
        event = {
            "event_id": uuid4().hex,
            "occurred_at": utc_now(),
            "project_id": project_id,
            "run_id": run_id,
            "actor": actor,
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "details": details or {},
            "previous_hash": previous_hash,
        }
        event_hash = hashlib.sha256(
            (previous_hash + _canonical(event)).encode("utf-8")
        ).hexdigest()
        connection.execute(
            """
            INSERT INTO audit_events(
                event_id, occurred_at, project_id, run_id, actor, action,
                object_type, object_id, details_json, previous_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["occurred_at"],
                project_id,
                run_id,
                actor,
                action,
                object_type,
                object_id,
                _canonical(event["details"]),
                previous_hash,
                event_hash,
            ),
        )
        return event_hash

    def verify(self, connection: sqlite3.Connection) -> tuple[bool, str]:
        expected_previous = GENESIS_HASH
        for row in connection.execute("SELECT * FROM audit_events ORDER BY sequence"):
            event = {
                "event_id": row["event_id"],
                "occurred_at": row["occurred_at"],
                "project_id": row["project_id"],
                "run_id": row["run_id"],
                "actor": row["actor"],
                "action": row["action"],
                "object_type": row["object_type"],
                "object_id": row["object_id"],
                "details": json.loads(row["details_json"]),
                "previous_hash": row["previous_hash"],
            }
            actual = hashlib.sha256(
                (expected_previous + _canonical(event)).encode("utf-8")
            ).hexdigest()
            if row["previous_hash"] != expected_previous or row["event_hash"] != actual:
                return False, f"Audit chain failed at sequence {row['sequence']}"
            expected_previous = actual
        return True, expected_previous
