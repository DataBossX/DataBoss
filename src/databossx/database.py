from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path


class DataBossDatabase:
    """SQLite bootstrap and convenience helpers for one project runtime."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def schema_path() -> Path:
        return Path(__file__).resolve().parents[2] / "migrations" / "001_initial_schema.sql"

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def initialize(self) -> None:
        schema_sql = self.schema_path().read_text(encoding="utf-8")
        with contextlib.closing(self.connect()) as conn:
            conn.executescript(schema_sql)
            conn.commit()

    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        with contextlib.closing(self.connect()) as conn:
            return conn.execute(query, params).fetchone()

    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        with contextlib.closing(self.connect()) as conn:
            return conn.execute(query, params).fetchall()

    def execute(self, query: str, params: tuple = ()) -> int:
        with contextlib.closing(self.connect()) as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    def executescript(self, script: str) -> None:
        with contextlib.closing(self.connect()) as conn:
            conn.executescript(script)
            conn.commit()

    def audit(self, project_id: str, event_type: str, entity_type: str, entity_id: str, payload: str) -> int:
        return self.execute(
            """
            INSERT INTO audit_events (
                project_id, actor_type, actor_id, event_type, entity_type, entity_id, payload_json
            ) VALUES (?, 'system', 'databossx', ?, ?, ?, ?)
            """,
            (project_id, event_type, entity_type, entity_id, payload),
        )
