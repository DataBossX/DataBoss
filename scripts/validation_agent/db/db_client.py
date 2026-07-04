"""Append-only SQLite access layer.

The single system law this module enforces: **durable memory is append-only**.
Only ``INSERT`` and ``SELECT`` reach the database. Everything that mutates or
destroys existing rows — UPDATE, DELETE, DROP, ALTER, REPLACE,
INSERT OR REPLACE, UPSERT, VACUUM, ATTACH, DETACH, multi-statement SQL — is
rejected at three layers:

1. **SQL text guard** — rejects forbidden syntax before it reaches SQLite.
2. **SQLite authorizer** — a C-level callback that denies mutating actions even
   for SQL that slipped past the text guard.
3. **Triggers** (see ``schema.sql``) — a final backstop that fires for any
   connection that bypassed this class entirely (e.g. raw ``sqlite3``).

Errors are never silently swallowed: a blocked operation raises
``AppendOnlyViolation``; a genuine SQL error propagates as ``DatabaseError``.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


class DatabaseError(RuntimeError):
    """A real database error that must not be swallowed."""


class AppendOnlyViolation(DatabaseError):
    """Raised when a forbidden (non-append) operation is attempted."""


# Forbidden tokens scanned in write SQL. Word-boundary matched, case-insensitive.
_FORBIDDEN_PATTERNS = [
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bALTER\b",
    r"\bREPLACE\b",          # covers "REPLACE INTO" and "INSERT OR REPLACE"
    r"\bTRUNCATE\b",
    r"\bVACUUM\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
    r"\bUPSERT\b",
    r"\bON\s+CONFLICT\b",    # UPSERT-style mutation
]
_FORBIDDEN_RE = re.compile("|".join(_FORBIDDEN_PATTERNS), re.IGNORECASE)

# "INSERT OR REPLACE" specifically (REPLACE already caught, but be explicit).
_INSERT_OR_REPLACE_RE = re.compile(r"\bINSERT\s+OR\s+REPLACE\b", re.IGNORECASE)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql


def _count_statements(sql: str) -> int:
    """Count top-level statements, ignoring a single trailing semicolon and
    semicolons inside string literals."""
    cleaned = _strip_sql_comments(sql)
    # remove quoted string literals so their semicolons don't count
    cleaned = re.sub(r"'(?:[^']|'')*'", "''", cleaned)
    cleaned = re.sub(r'"(?:[^"]|"")*"', '""', cleaned)
    parts = [p for p in cleaned.split(";") if p.strip()]
    return len(parts)


class DatabaseManager:
    """Thread-safe, append-only SQLite manager."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._schema_mode = False  # only True during initialize_schema()
        self._conn = sqlite3.connect(
            str(self.db_path), check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.set_authorizer(self._authorizer)

    # ------------------------------------------------------------------ #
    # Authorizer
    # ------------------------------------------------------------------ #
    def _authorizer(
        self,
        action: int,
        arg1: Optional[str],
        arg2: Optional[str],
        db_name: Optional[str],
        trigger: Optional[str],
    ) -> int:
        # Schema initialization runs only our own vetted schema.sql within an
        # explicit, short-lived window. Trust it fully; the append-only
        # guarantee applies to every operation outside this window.
        if self._schema_mode:
            return sqlite3.SQLITE_OK

        # Always-allowed, non-mutating actions.
        allowed = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
            sqlite3.SQLITE_TRANSACTION,
            sqlite3.SQLITE_RECURSIVE,
            sqlite3.SQLITE_INSERT,  # the one write we permit
        }
        # Hard-denied mutating / destructive actions.
        denied = {
            sqlite3.SQLITE_UPDATE,
            sqlite3.SQLITE_DELETE,
            sqlite3.SQLITE_DROP_TABLE,
            sqlite3.SQLITE_DROP_TEMP_TABLE,
            sqlite3.SQLITE_DROP_INDEX,
            sqlite3.SQLITE_DROP_TEMP_INDEX,
            sqlite3.SQLITE_DROP_TRIGGER,
            sqlite3.SQLITE_DROP_TEMP_TRIGGER,
            sqlite3.SQLITE_DROP_VIEW,
            sqlite3.SQLITE_DROP_TEMP_VIEW,
            sqlite3.SQLITE_ALTER_TABLE,
            sqlite3.SQLITE_ATTACH,
            sqlite3.SQLITE_DETACH,
            sqlite3.SQLITE_REINDEX,
        }

        if action in denied:
            return sqlite3.SQLITE_DENY

        if action == sqlite3.SQLITE_INSERT:
            # Block INSERT into sqlite internal tables; allow user tables.
            if arg1 and str(arg1).startswith("sqlite_"):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        # Schema creation is only permitted while explicitly initializing.
        create_actions = {
            sqlite3.SQLITE_CREATE_TABLE,
            sqlite3.SQLITE_CREATE_INDEX,
            sqlite3.SQLITE_CREATE_TRIGGER,
            sqlite3.SQLITE_CREATE_VIEW,
            sqlite3.SQLITE_CREATE_TEMP_TABLE,
            sqlite3.SQLITE_CREATE_TEMP_INDEX,
            sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
            sqlite3.SQLITE_CREATE_TEMP_VIEW,
        }
        if action in create_actions:
            return sqlite3.SQLITE_OK if self._schema_mode else sqlite3.SQLITE_DENY

        if action == sqlite3.SQLITE_PRAGMA:
            # Allow only read/config pragmas needed for setup.
            safe_pragmas = {"foreign_keys", "journal_mode", "table_info",
                            "wal_checkpoint", "user_version", "integrity_check"}
            if arg1 and str(arg1).lower() in safe_pragmas:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        if action in allowed:
            return sqlite3.SQLITE_OK

        # Default-deny anything unrecognised (e.g. SQLITE_ANALYZE, VACUUM maps
        # through function/pragma paths). Fail closed.
        return sqlite3.SQLITE_DENY

    # ------------------------------------------------------------------ #
    # Schema
    # ------------------------------------------------------------------ #
    def initialize_schema(self, schema_path: Optional[Path] = None) -> None:
        """Create tables/views/triggers idempotently (safe to call repeatedly)."""
        if schema_path is None:
            schema_path = Path(__file__).resolve().parent / "schema.sql"
        schema_sql = Path(schema_path).read_text(encoding="utf-8")
        with self._lock:
            self._schema_mode = True
            try:
                self._conn.executescript(schema_sql)
            except sqlite3.Error as exc:  # never swallow
                raise DatabaseError(f"schema initialization failed: {exc}") from exc
            finally:
                self._schema_mode = False

    # ------------------------------------------------------------------ #
    # Write path (append-only)
    # ------------------------------------------------------------------ #
    def _guard_write_sql(self, sql: str) -> None:
        cleaned = _strip_sql_comments(sql)
        if _count_statements(cleaned) > 1:
            raise AppendOnlyViolation("multi-statement SQL is forbidden")
        if _INSERT_OR_REPLACE_RE.search(cleaned):
            raise AppendOnlyViolation("INSERT OR REPLACE is forbidden")
        if _FORBIDDEN_RE.search(cleaned):
            raise AppendOnlyViolation(
                "forbidden mutating keyword detected in write SQL"
            )
        if not re.match(r"^\s*INSERT\s+INTO\b", cleaned, re.IGNORECASE):
            raise AppendOnlyViolation("only INSERT INTO statements may write")

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """Insert a single row; returns the new rowid. Timestamps auto-filled."""
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table):
            raise AppendOnlyViolation(f"illegal table name: {table!r}")
        row = dict(data)
        if "created_at" not in row:
            row["created_at"] = _utc_now_iso()
        columns = list(row.keys())
        for col in columns:
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", col):
                raise AppendOnlyViolation(f"illegal column name: {col!r}")
        placeholders = ", ".join("?" for _ in columns)
        col_sql = ", ".join(columns)
        sql = f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})"
        self._guard_write_sql(sql)
        with self._lock:
            try:
                cur = self._conn.execute(sql, [row[c] for c in columns])
            except sqlite3.Error as exc:
                raise DatabaseError(f"insert into {table} failed: {exc}") from exc
            return int(cur.lastrowid)

    def execute_insert(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Execute a caller-supplied INSERT after validation."""
        self._guard_write_sql(sql)
        with self._lock:
            try:
                cur = self._conn.execute(sql, list(params))
            except sqlite3.Error as exc:
                raise DatabaseError(f"insert failed: {exc}") from exc
            return int(cur.lastrowid)

    # ------------------------------------------------------------------ #
    # Read path
    # ------------------------------------------------------------------ #
    def query(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        cleaned = _strip_sql_comments(sql)
        if _count_statements(cleaned) > 1:
            raise AppendOnlyViolation("multi-statement SQL is forbidden")
        if not re.match(r"^\s*(SELECT|WITH)\b", cleaned, re.IGNORECASE):
            raise AppendOnlyViolation("query() accepts only SELECT/WITH statements")
        if _FORBIDDEN_RE.search(cleaned):
            raise AppendOnlyViolation("mutating keyword detected in query SQL")
        with self._lock:
            try:
                cur = self._conn.execute(sql, list(params))
                rows = cur.fetchall()
            except sqlite3.Error as exc:
                raise DatabaseError(f"query failed: {exc}") from exc
            return [dict(r) for r in rows]

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: Sequence[Any] = ()) -> Any:
        row = self.query_one(sql, params)
        if not row:
            return None
        return next(iter(row.values()))

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error as exc:  # pragma: no cover
                raise DatabaseError(f"close failed: {exc}") from exc

    def __enter__(self) -> "DatabaseManager":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
