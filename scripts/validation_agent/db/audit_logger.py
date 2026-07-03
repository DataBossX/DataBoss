"""Append-only file mirror of audit events.

Every important action is written both to the SQLite ``audit_events`` table
(via :class:`DatabaseManager`) and to a human-readable JSONL log file. The file
log is opened in append mode only and is never truncated.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, log_path: str | Path, db=None):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = db

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def log(self, event_type: str, description: str, run_id: str | None = None,
            state: str | None = None, data: Any = None) -> None:
        record = {
            "ts": self._now(),
            "run_id": run_id,
            "event": event_type,
            "state": state,
            "desc": description,
        }
        if data is not None:
            record["data"] = data
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        if self.db is not None:
            try:
                self.db.record_event(run_id, event_type, state, description, data)
            except Exception:
                # File log is the durable fallback; never let DB errors lose it.
                pass
