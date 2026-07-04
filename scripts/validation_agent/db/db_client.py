"""Append-only SQLite access layer.

Two independent layers of protection:

  1. **Engine-level triggers** (see ``schema.sql``) reject UPDATE/DELETE on every
     protected table — this holds even for a raw ``sqlite3.connect`` that never
     touches this module.
  2. **Authorizer + statement guard** on the manager's own connection reject
     UPDATE, DELETE, DROP, ALTER, and multi-statement SQL before they reach the
     engine, and forbid ``INSERT OR REPLACE`` / ``REPLACE`` / UPSERT text.

The only public write path is :meth:`DatabaseManager.insert`.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# sqlite3 authorizer action codes we explicitly deny.
_DENIED_ACTIONS = {
    sqlite3.SQLITE_DELETE,
    sqlite3.SQLITE_UPDATE,
    sqlite3.SQLITE_DROP_TABLE,
    sqlite3.SQLITE_DROP_INDEX,
    sqlite3.SQLITE_DROP_TRIGGER,
    sqlite3.SQLITE_DROP_VIEW,
    sqlite3.SQLITE_ALTER_TABLE,
}

_FORBIDDEN_SQL = re.compile(
    r"\b(update|delete|drop|alter|replace)\b|insert\s+or\s+replace|on\s+conflict",
    re.IGNORECASE,
)

# Columns permitted per table (whitelist prevents accidental SQL surprises).
PROTECTED_TABLES = {
    "runs",
    "workbook_versions",
    "audit_events",
    "validation_results",
    "spend_ledger",
    "api_calls",
    "automated_repairs",
    "escalations",
    "source_documents",
    "report_exports",
    "launcher_events",
}


class AppendOnlyViolation(RuntimeError):
    """Raised when a caller attempts a mutating or unsafe statement."""


def _authorizer(action: int, arg1, arg2, dbname, source):
    if action in _DENIED_ACTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


class DatabaseManager:
    """The single sanctioned gateway to the audit database."""

    def __init__(self, db_path: Path, schema_path: Path):
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        # Install the authorizer AFTER schema creation (schema needs DDL).
        self._conn.set_authorizer(_authorizer)

    # ------------------------------------------------------------------ setup
    def _init_schema(self) -> None:
        sql = self.schema_path.read_text(encoding="utf-8")
        # Temporarily allow DDL by not having an authorizer yet.
        self._conn.executescript(sql)

    # ------------------------------------------------------------------ write
    def insert(self, table: str, values: Dict[str, Any]) -> int:
        """The ONLY write method. Parameterized INSERT into a protected table."""
        if table not in PROTECTED_TABLES:
            raise AppendOnlyViolation(f"unknown/forbidden table: {table}")
        if not values:
            raise AppendOnlyViolation("refusing empty insert")
        cols = list(values.keys())
        for c in cols:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", c):
                raise AppendOnlyViolation(f"illegal column name: {c}")
        placeholders = ", ".join(["?"] * len(cols))
        col_sql = ", ".join(cols)
        sql = f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})"
        if _FORBIDDEN_SQL.search(sql):  # defense in depth
            raise AppendOnlyViolation("statement rejected by SQL guard")
        cur = self._conn.execute(sql, [values[c] for c in cols])
        return int(cur.lastrowid)

    # ------------------------------------------------------------------ read
    def query(self, sql: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        stripped = sql.strip().rstrip(";")
        if ";" in stripped:
            raise AppendOnlyViolation("multi-statement SQL is not allowed")
        if not re.match(r"(?is)^\s*(select|with)\b", stripped):
            raise AppendOnlyViolation("only SELECT/CTE reads are allowed via query()")
        if _FORBIDDEN_SQL.search(stripped):
            raise AppendOnlyViolation("read statement contains forbidden keyword")
        return list(self._conn.execute(stripped, params).fetchall())

    def count(self, table: str) -> int:
        if table not in PROTECTED_TABLES:
            raise AppendOnlyViolation(f"unknown table: {table}")
        return int(self._conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])

    # ------------------------------------------------------------------ misc
    def raw_backup_to(self, dest: Path) -> Path:
        """Create a read-only file copy of the DB (for export packets)."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(str(dest))
        with target:
            self._conn.backup(target)
        target.close()
        return dest

    def close(self) -> None:
        try:
            self._conn.set_authorizer(None)
        except Exception:
            pass
        self._conn.close()

    def __enter__(self) -> "DatabaseManager":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
