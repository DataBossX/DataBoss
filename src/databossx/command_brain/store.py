"""Persistence for the Command Brain.

Wraps :class:`~databossx.database.DataBossDatabase` and adds the hash-chained,
append-only ledger. The chain means a receipt cannot be quietly edited after the
fact: every entry commits to its predecessor, so :meth:`verify_ledger` detects
any rewrite even though SQLite triggers already refuse UPDATE and DELETE.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..database import DataBossDatabase
from .redaction import contains_secret, redact
from .util import Clock, IdFactory, canonical_hash, canonical_json

GENESIS_HASH = "0" * 64

MIGRATIONS = ("001_initial_schema.sql", "002_command_brain.sql")


def migrations_root() -> Path:
    return Path(__file__).resolve().parents[3] / "migrations"


class CommandBrainStore:
    """All Command Brain reads and writes go through here."""

    def __init__(self, db_path, clock: Clock | None = None, ids: IdFactory | None = None):
        self.db = DataBossDatabase(db_path)
        self.clock = clock or Clock()
        self.ids = ids or IdFactory()

    # -- lifecycle --------------------------------------------------------
    def initialize(self) -> None:
        root = migrations_root()
        for name in MIGRATIONS:
            self.db.executescript((root / name).read_text(encoding="utf-8"))

    def connect(self) -> sqlite3.Connection:
        return self.db.connect()

    def execute(self, query: str, params: tuple = ()):
        return self.db.execute(query, params)

    def fetchone(self, query: str, params: tuple = ()):
        return self.db.fetchone(query, params)

    def fetchall(self, query: str, params: tuple = ()):
        return self.db.fetchall(query, params)

    def now(self) -> str:
        return self.clock.now_iso()

    def new_id(self, prefix: str) -> str:
        return self.ids.new(prefix)

    # -- append-only ledger ----------------------------------------------
    def _head_hash(self, conn: sqlite3.Connection) -> str:
        row = conn.execute(
            "SELECT entry_hash FROM cb_audit_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row["entry_hash"] if row else GENESIS_HASH

    def audit(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        payload: dict | None = None,
        *,
        project_id: str | None = None,
        actor_type: str = "system",
        actor_id: str = "command_brain",
    ) -> dict:
        """Append one immutable, redacted, hash-chained audit event."""
        safe_payload = redact(payload or {})
        if contains_secret(safe_payload):
            # Belt and braces: never write an event we cannot prove is clean.
            safe_payload = {"note": "payload withheld: failed secret scan"}
        created_at = self.now()
        with self.connect() as conn:
            prev_hash = self._head_hash(conn)
            entry = {
                "project_id": project_id,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "event_type": event_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "payload": safe_payload,
                "prev_hash": prev_hash,
                "created_at": created_at,
            }
            entry_hash = canonical_hash(entry)
            cursor = conn.execute(
                """
                INSERT INTO cb_audit_events (
                    project_id, actor_type, actor_id, event_type, entity_type,
                    entity_id, payload_json, prev_hash, entry_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    actor_type,
                    actor_id,
                    event_type,
                    entity_type,
                    entity_id,
                    canonical_json(safe_payload),
                    prev_hash,
                    entry_hash,
                    created_at,
                ),
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "event_type": event_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entry_hash": entry_hash,
                "prev_hash": prev_hash,
                "created_at": created_at,
                "payload": safe_payload,
            }

    def verify_ledger(self) -> dict:
        """Recompute the chain. Returns ``{"valid": bool, "broken_at": id|None}``."""
        rows = self.fetchall(
            """
            SELECT id, project_id, actor_type, actor_id, event_type, entity_type,
                   entity_id, payload_json, prev_hash, entry_hash, created_at
              FROM cb_audit_events ORDER BY id
            """
        )
        prev = GENESIS_HASH
        for row in rows:
            entry = {
                "project_id": row["project_id"],
                "actor_type": row["actor_type"],
                "actor_id": row["actor_id"],
                "event_type": row["event_type"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "payload": json.loads(row["payload_json"]),
                "prev_hash": row["prev_hash"],
                "created_at": row["created_at"],
            }
            if row["prev_hash"] != prev or canonical_hash(entry) != row["entry_hash"]:
                return {"valid": False, "broken_at": row["id"], "entries": len(rows)}
            prev = row["entry_hash"]
        return {"valid": True, "broken_at": None, "entries": len(rows)}

    def audit_events(self, limit: int = 200, entity_id: str | None = None) -> list[dict]:
        if entity_id:
            rows = self.fetchall(
                """
                SELECT * FROM cb_audit_events WHERE entity_id = ? ORDER BY id DESC LIMIT ?
                """,
                (entity_id, limit),
            )
        else:
            rows = self.fetchall("SELECT * FROM cb_audit_events ORDER BY id DESC LIMIT ?", (limit,))
        events = []
        for row in rows:
            event = dict(row)
            event["payload"] = json.loads(event.pop("payload_json"))
            events.append(event)
        return events

    # -- receipts ---------------------------------------------------------
    def write_receipt(
        self,
        subject_type: str,
        subject_id: str,
        payload: dict,
        *,
        project_id: str | None = None,
    ) -> dict:
        safe_payload = redact(payload)
        receipt_id = self.new_id("rcpt")
        payload_hash = canonical_hash(safe_payload)
        created_at = self.now()
        self.execute(
            """
            INSERT INTO cb_receipts (
                receipt_id, project_id, subject_type, subject_id,
                payload_json, payload_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                project_id,
                subject_type,
                subject_id,
                canonical_json(safe_payload),
                payload_hash,
                created_at,
            ),
        )
        self.audit(
            "receipt.written",
            subject_type,
            subject_id,
            {"receipt_id": receipt_id, "payload_hash": payload_hash},
            project_id=project_id,
        )
        return {
            "receipt_id": receipt_id,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "payload": safe_payload,
            "payload_hash": payload_hash,
            "created_at": created_at,
        }

    def get_receipt(self, receipt_id: str) -> dict | None:
        row = self.fetchone("SELECT * FROM cb_receipts WHERE receipt_id = ?", (receipt_id,))
        if row is None:
            return None
        receipt = dict(row)
        receipt["payload"] = json.loads(receipt.pop("payload_json"))
        return receipt

    def receipts_for(self, subject_id: str) -> list[dict]:
        rows = self.fetchall(
            "SELECT * FROM cb_receipts WHERE subject_id = ? ORDER BY created_at, receipt_id",
            (subject_id,),
        )
        out = []
        for row in rows:
            receipt = dict(row)
            receipt["payload"] = json.loads(receipt.pop("payload_json"))
            out.append(receipt)
        return out

    # -- quarantine -------------------------------------------------------
    def quarantine(self, subject_type: str, subject_id: str, reason: str) -> str:
        entry_id = self.new_id("qtn")
        self.execute(
            """
            INSERT INTO cb_quarantine (id, subject_type, subject_id, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (entry_id, subject_type, subject_id, reason, self.now()),
        )
        self.audit("quarantine.recorded", subject_type, subject_id, {"reason": reason})
        return entry_id

    def is_quarantined(self, subject_id: str) -> bool:
        row = self.fetchone(
            "SELECT 1 FROM cb_quarantine WHERE subject_id = ? LIMIT 1", (subject_id,)
        )
        return row is not None

    # -- human review -----------------------------------------------------
    def queue_human_review(
        self,
        subject_type: str,
        subject_id: str | None,
        question: str,
        context: dict | None = None,
        *,
        project_id: str | None = None,
    ) -> str:
        item_id = self.new_id("hrq")
        self.execute(
            """
            INSERT INTO cb_human_review_queue (
                item_id, project_id, subject_type, subject_id, question,
                context_json, state, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?)
            """,
            (
                item_id,
                project_id,
                subject_type,
                subject_id,
                question,
                canonical_json(redact(context or {})),
                self.now(),
            ),
        )
        self.audit(
            "human_review.queued",
            subject_type,
            subject_id or item_id,
            {"item_id": item_id, "question": question},
            project_id=project_id,
        )
        return item_id

    def open_human_reviews(self, project_id: str | None = None) -> list[dict]:
        if project_id:
            rows = self.fetchall(
                "SELECT * FROM cb_human_review_queue WHERE state='OPEN' AND project_id = ? ORDER BY created_at",
                (project_id,),
            )
        else:
            rows = self.fetchall(
                "SELECT * FROM cb_human_review_queue WHERE state='OPEN' ORDER BY created_at"
            )
        out = []
        for row in rows:
            item = dict(row)
            item["context"] = json.loads(item.pop("context_json"))
            out.append(item)
        return out
