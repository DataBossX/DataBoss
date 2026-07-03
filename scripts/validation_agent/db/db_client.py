"""Append-only SQLite connection manager (Golden Law #2, #5).

The database is *proof*, not scratch space.  Two independent layers keep it
append-only:

    1. A statement guard rejects any raw SQL whose leading verb mutates or
       destroys rows (UPDATE / DELETE / DROP / ALTER / REPLACE / TRUNCATE).
    2. A SQLite authorizer callback is the hard backstop -- even a cleverly
       constructed statement is denied at the C layer.  The only tolerated
       internal mutations are SQLite's own bookkeeping on ``sqlite_*`` tables
       (e.g. ``sqlite_sequence`` for AUTOINCREMENT).

Reads, inserts, and schema creation are permitted; nothing else is.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from ..config.settings import config

# --- SQLite authorizer constants (stable across the SQLite C ABI). ----------
# Defined explicitly rather than imported from sqlite3 so the module works
# identically on Python 3.10 (CI) and 3.11+ where the names were added.
_SQLITE_OK = 0
_SQLITE_DENY = 1
_SQLITE_DELETE = 9
_SQLITE_DROP_INDEX = 10
_SQLITE_DROP_TABLE = 11
_SQLITE_DROP_TRIGGER = 12
_SQLITE_DROP_VIEW = 13
_SQLITE_UPDATE = 23
_SQLITE_ALTER_TABLE = 26

_DENIED_ACTIONS = {
    _SQLITE_DELETE,
    _SQLITE_UPDATE,
    _SQLITE_DROP_INDEX,
    _SQLITE_DROP_TABLE,
    _SQLITE_DROP_TRIGGER,
    _SQLITE_DROP_VIEW,
    _SQLITE_ALTER_TABLE,
}

_FORBIDDEN_VERB = re.compile(
    r"^\s*(update|delete|drop|alter|truncate|replace)\b", re.IGNORECASE)


class AppendOnlyViolation(RuntimeError):
    """Raised when a caller attempts a mutating or destructive statement."""


def _authorizer(action: int, arg1: Optional[str], arg2: Optional[str],
                dbname: Optional[str], trigger: Optional[str]) -> int:
    if action in _DENIED_ACTIONS:
        # SQLite's own AUTOINCREMENT/bookkeeping touches sqlite_* tables; allow
        # only those, deny every user-table mutation.
        if arg1 and str(arg1).startswith("sqlite_"):
            return _SQLITE_OK
        return _SQLITE_DENY
    return _SQLITE_OK


class DatabaseManager:
    """Owns the DB path and hands out authorizer-guarded connections."""

    def __init__(self, db_path: Optional[Path] = None,
                 schema_path: Optional[Path] = None) -> None:
        self.db_path = db_path or config.db_path
        self.schema_path = schema_path or config.schema_path

    def init(self) -> None:
        """Create the schema if absent.  Idempotent."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        ddl = self.schema_path.read_text(encoding="utf-8")
        # Schema creation uses a raw connection *without* the authorizer so
        # CREATE TABLE/INDEX/PRAGMA run unhindered; it never mutates data.
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(ddl)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.set_authorizer(_authorizer)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.set_authorizer(None)
            conn.close()

    # -- write path (inserts only) -----------------------------------------
    def insert(self, table: str, row: dict[str, Any]) -> int:
        cols = list(row.keys())
        placeholders = ",".join("?" for _ in cols)
        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
        values = tuple(_encode(row[c]) for c in cols)
        with self.connect() as conn:
            cur = conn.execute(sql, values)
            return int(cur.lastrowid or 0)

    def insert_many(self, table: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        placeholders = ",".join("?" for _ in cols)
        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
        payload = [tuple(_encode(r[c]) for c in cols) for r in rows]
        with self.connect() as conn:
            cur = conn.executemany(sql, payload)
            return int(cur.rowcount)

    # -- read path ----------------------------------------------------------
    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        self._forbid(sql)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def query_one(self, sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: tuple = ()) -> Any:
        row = self.query_one(sql, params)
        if not row:
            return None
        return next(iter(row.values()))

    @staticmethod
    def _forbid(sql: str) -> None:
        if _FORBIDDEN_VERB.match(sql):
            raise AppendOnlyViolation(
                f"Append-only database rejects statement: {sql.strip()[:60]}...")


def _encode(value: Any) -> Any:
    """Serialize dict/list values to JSON so callers can pass structures."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return value


# Module-level singleton mirrors the existing doto_image_commander convention.
db = DatabaseManager()
