"""SQLite shared-memory layer with an append-only audit guarantee.

One database file per run lives at ``output/<run_id>/run.db``. Log tables are
protected by triggers that reject UPDATE and DELETE, enforcing Golden Law #4
(immutability / append-only) at the storage layer rather than by convention.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

# Tables that must never be mutated after insert.
_APPEND_ONLY_TABLES: tuple[str, ...] = (
    "audit_log",
    "validation_results",
    "fixes",
    "escalations",
    "spend_ledger",
    "evidence",
    "versions",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    created_ts  TEXT NOT NULL,
    state       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS versions (
    version        INTEGER PRIMARY KEY,
    run_id         TEXT NOT NULL,
    path           TEXT NOT NULL,
    sha256         TEXT NOT NULL,
    created_ts     TEXT NOT NULL,
    parent_version INTEGER
);

CREATE TABLE IF NOT EXISTS audit_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,
    run_id         TEXT NOT NULL,
    actor          TEXT NOT NULL,
    action         TEXT NOT NULL,
    gate           TEXT,
    coord          TEXT,
    before         TEXT,
    after          TEXT,
    risk           TEXT,
    source_refs    TEXT,
    result         TEXT NOT NULL,
    action_hash    TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_audit_action_hash
    ON audit_log(run_id, action_hash) WHERE action_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS validation_results (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    run_id   TEXT NOT NULL,
    version  INTEGER NOT NULL,
    gate     TEXT NOT NULL,
    passed   INTEGER NOT NULL,
    severity TEXT NOT NULL,
    message  TEXT NOT NULL,
    metric   REAL,
    expected REAL,
    locations TEXT
);

CREATE TABLE IF NOT EXISTS fixes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    run_id       TEXT NOT NULL,
    version      INTEGER NOT NULL,
    strategy_id  TEXT NOT NULL,
    risk         TEXT NOT NULL,
    coord        TEXT NOT NULL,
    before       TEXT,
    after        TEXT,
    justification TEXT NOT NULL,
    source_refs  TEXT
);

CREATE TABLE IF NOT EXISTS escalations (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    run_id    TEXT NOT NULL,
    version   INTEGER NOT NULL,
    gate      TEXT NOT NULL,
    category  TEXT NOT NULL,
    reason    TEXT NOT NULL,
    payload   TEXT,
    decision  TEXT
);

CREATE TABLE IF NOT EXISTS spend_ledger (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    run_id        TEXT NOT NULL,
    cost_usd      TEXT NOT NULL,
    evidence_hash TEXT,
    note          TEXT
);

CREATE TABLE IF NOT EXISTS evidence (
    hash       TEXT PRIMARY KEY,
    run_id     TEXT NOT NULL,
    kind       TEXT NOT NULL,
    locator    TEXT NOT NULL,
    path       TEXT,
    fetched_ts TEXT NOT NULL,
    cost_usd   TEXT
);
"""


def _append_only_triggers() -> str:
    stmts: list[str] = []
    for tbl in _APPEND_ONLY_TABLES:
        stmts.append(
            f"CREATE TRIGGER IF NOT EXISTS no_update_{tbl} "
            f"BEFORE UPDATE ON {tbl} BEGIN "
            f"SELECT RAISE(ABORT, 'append-only: UPDATE forbidden on {tbl}'); END;"
        )
        stmts.append(
            f"CREATE TRIGGER IF NOT EXISTS no_delete_{tbl} "
            f"BEFORE DELETE ON {tbl} BEGIN "
            f"SELECT RAISE(ABORT, 'append-only: DELETE forbidden on {tbl}'); END;"
        )
    return "\n".join(stmts)


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Open (creating parents) a WAL-mode connection with row access by name."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables and the append-only triggers (idempotent)."""
    conn.executescript(_SCHEMA)
    conn.executescript(_append_only_triggers())
    conn.commit()
