"""
Append-only SQLite access layer.

Two independent defences:
  1. Database triggers (in schema.sql) ABORT any UPDATE/DELETE on protected
     tables. These live in the file and stop even a raw sqlite3 connection.
  2. An application-level authorizer on DatabaseManager connections denies
     UPDATE, DELETE, DROP, ALTER and transaction-less DDL, and insert() refuses
     multi-statement SQL and REPLACE/UPSERT verbs.

Only INSERT and SELECT are sanctioned. There is deliberately no update() or
delete() method anywhere in the codebase.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

PROTECTED_TABLES = {
    "runs", "workbook_versions", "audit_events", "validation_results",
    "spend_ledger", "api_calls", "automated_repairs", "escalations",
    "source_documents", "report_exports", "launcher_events",
}

_BLOCKED_VERBS = ("update", "delete", "drop", "alter", "replace", "truncate")


class AppendOnlyViolation(RuntimeError):
    """Raised when a mutating or unsafe SQL operation is attempted."""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _authorizer(action, arg1, arg2, dbname, source):
    """SQLite authorizer callback: deny mutation/DDL on protected tables."""
    # Block table-level UPDATE and DELETE.
    if action == sqlite3.SQLITE_UPDATE and arg1 in PROTECTED_TABLES:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_DELETE and arg1 in PROTECTED_TABLES:
        return sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_DROP_TRIGGER,
                  sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_DROP_VIEW):
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_ALTER_TABLE:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


class DatabaseManager:
    """The single sanctioned gateway to the audit database."""

    def __init__(self, db_path: str | Path, schema_path: Optional[str | Path] = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if schema_path is None:
            schema_path = Path(__file__).with_name("schema.sql")
        self.schema_path = Path(schema_path)
        self._init_schema()

    # ---- connections ----
    def _raw_connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _guarded_connect(self) -> sqlite3.Connection:
        conn = self._raw_connect()
        conn.set_authorizer(_authorizer)
        return conn

    def _init_schema(self) -> None:
        sql = self.schema_path.read_text(encoding="utf-8")
        # Schema creation uses a raw connection (authorizer would block CREATE
        # TRIGGER's internal steps); this runs once at setup only.
        conn = self._raw_connect()
        try:
            conn.executescript(sql)
            conn.commit()
        finally:
            conn.close()

    # ---- writes (INSERT only) ----
    def insert(self, table: str, data: Dict[str, Any]) -> int:
        if table not in PROTECTED_TABLES:
            raise AppendOnlyViolation(f"Unknown/unprotected table: {table}")
        if not data:
            raise AppendOnlyViolation("Refusing empty insert")
        data = dict(data)
        data.setdefault("created_at", utcnow())
        cols = list(data.keys())
        # Defensive: reject any attempt to smuggle SQL through identifiers.
        for c in cols:
            if not c.replace("_", "").isalnum():
                raise AppendOnlyViolation(f"Illegal column identifier: {c!r}")
        placeholders = ", ".join(["?"] * len(cols))
        col_sql = ", ".join(cols)
        sql = f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})"
        self._reject_unsafe(sql)
        conn = self._guarded_connect()
        try:
            cur = conn.execute(sql, [data[c] for c in cols])
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    @staticmethod
    def _reject_unsafe(sql: str) -> None:
        low = sql.strip().lower()
        if not low.startswith("insert into "):
            raise AppendOnlyViolation("Only INSERT INTO is permitted for writes")
        # No multi-statement.
        if ";" in sql.strip().rstrip(";"):
            raise AppendOnlyViolation("Multi-statement SQL is blocked")
        # No REPLACE / UPSERT / ON CONFLICT.
        if "insert or replace" in low or "replace into" in low:
            raise AppendOnlyViolation("INSERT OR REPLACE / REPLACE is blocked")
        if "on conflict" in low:
            raise AppendOnlyViolation("UPSERT (ON CONFLICT) is blocked")
        for verb in _BLOCKED_VERBS:
            # allow the substring only if not a leading statement verb
            if low.startswith(verb + " "):
                raise AppendOnlyViolation(f"{verb.upper()} is blocked")

    # ---- reads (SELECT only) ----
    def query(self, sql: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        low = sql.strip().lower()
        if not (low.startswith("select ") or low.startswith("select\n") or low.startswith("with ")):
            raise AppendOnlyViolation("query() accepts SELECT statements only")
        if ";" in sql.strip().rstrip(";"):
            raise AppendOnlyViolation("Multi-statement SQL is blocked")
        conn = self._guarded_connect()
        try:
            return list(conn.execute(sql, params))
        finally:
            conn.close()

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[sqlite3.Row]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # ---- convenience aggregates ----
    def scalar(self, sql: str, params: Sequence[Any] = (), default: Any = None) -> Any:
        row = self.query_one(sql, params)
        if row is None:
            return default
        return row[0] if row[0] is not None else default

    def count(self, table: str, where: str = "", params: Sequence[Any] = ()) -> int:
        if table not in PROTECTED_TABLES:
            raise AppendOnlyViolation(f"Unknown table: {table}")
        sql = f"SELECT COUNT(*) FROM {table}"
        if where:
            sql += f" WHERE {where}"
        return int(self.scalar(sql, params, 0))
