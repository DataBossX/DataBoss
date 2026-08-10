"""SQLite state store for the DataBossX Command Center.

This is runtime state only (jobs, receipts, caches, worker registry,
UI preferences) -- it is NOT the operations source of truth. The COO
master status tracker and client sources remain authoritative; this
database only caches bounded local projections of them.
"""
import json
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    task TEXT NOT NULL,
    lane TEXT,
    project TEXT,
    status TEXT NOT NULL,
    cost_class TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    inputs_json TEXT,
    output_json TEXT,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS receipts (
    id TEXT PRIMARY KEY,
    job_id TEXT,
    task TEXT NOT NULL,
    lane TEXT,
    project TEXT,
    action TEXT,
    start_ts TEXT,
    end_ts TEXT,
    inputs_json TEXT,
    output_summary TEXT,
    files_changed_json TEXT,
    model_tool TEXT,
    tests_json TEXT,
    warnings_json TEXT,
    rollback TEXT
);

CREATE TABLE IF NOT EXISTS workers (
    pid INTEGER PRIMARY KEY,
    owner TEXT NOT NULL,
    task TEXT,
    model TEXT,
    start_time TEXT,
    heartbeat TEXT,
    status TEXT,
    idle_seconds REAL,
    retry_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    purpose TEXT,
    schedule TEXT,
    last_run TEXT,
    next_run TEXT,
    cost_class TEXT DEFAULT 'FREE',
    enabled INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS project_cache (
    path TEXT PRIMARY KEY,
    project TEXT,
    client TEXT,
    lane TEXT,
    last_scan TEXT,
    file_count INTEGER,
    last_mtime REAL,
    meta_json TEXT
);

CREATE TABLE IF NOT EXISTS schema_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);
"""

SCHEMA_VERSION = 1
_lock = threading.Lock()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Idempotent, safe-to-rerun schema init/migration."""
    with _lock:
        conn.executescript(SCHEMA)
        cur = conn.execute("SELECT version FROM schema_meta WHERE id = 1")
        row = cur.fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO schema_meta (id, version) VALUES (1, ?)", (SCHEMA_VERSION,)
            )
        conn.commit()


def get_setting(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return row["value"]


def set_setting(conn: sqlite3.Connection, key: str, value) -> None:
    with _lock:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )
        conn.commit()
