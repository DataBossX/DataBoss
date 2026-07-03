"""Initialize the DataBossX SQLite master database (stdlib sqlite3).

Creates the schema if missing. Idempotent and non-destructive: existing tables
and data are left untouched (CREATE TABLE IF NOT EXISTS). The DB path comes from
the DB_PATH env var, falling back to data/databossx_master.sqlite.

Schema encodes 'every action leaves proof' via the audit_log table.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "databossx_master.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path  TEXT NOT NULL,
    doc_type     TEXT,
    county       TEXT,
    status       TEXT DEFAULT 'ingested',
    trust        TEXT DEFAULT 'untrusted',
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS extractions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id   INTEGER NOT NULL REFERENCES documents(id),
    field_name    TEXT NOT NULL,
    field_value   TEXT,
    confidence    REAL,
    model         TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    target      TEXT,
    detail      TEXT,
    approved_by TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_extractions_doc ON extractions(document_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
"""


def init_db(db_path: Path | None = None) -> Path:
    path = db_path or Path(os.environ.get("DB_PATH", DEFAULT_DB))
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    return path


if __name__ == "__main__":
    p = init_db()
    print(f"[SUCCESS] DataBossX master DB ready at {p}")
