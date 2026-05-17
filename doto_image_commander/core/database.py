"""SQLite database setup, schema, and query helpers."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import config

_DB: Path = config.DB_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS pull_list_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id         TEXT NOT NULL,
    county           TEXT,
    book             TEXT,
    page             TEXT,
    instrument_number TEXT,
    image_number     TEXT,
    instrument_type  TEXT,
    section          TEXT,
    township         TEXT,
    range_val        TEXT,
    recording_date   TEXT,
    raw_data         TEXT,
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS image_index_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id         TEXT NOT NULL,
    county           TEXT,
    book             TEXT,
    page             TEXT,
    instrument_number TEXT,
    image_number     TEXT,
    instrument_type  TEXT,
    file_name        TEXT,
    raw_data         TEXT,
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS image_queue (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key        TEXT UNIQUE NOT NULL,
    county           TEXT,
    book             TEXT,
    page             TEXT,
    instrument_number TEXT,
    image_number     TEXT,
    instrument_type  TEXT,
    section          TEXT,
    township         TEXT,
    range_val        TEXT,
    recording_date   TEXT,
    estimated_cost   REAL DEFAULT 0.0,
    status           TEXT DEFAULT 'pending',
    approved_at      TEXT,
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS downloads (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_item_id    INTEGER NOT NULL,
    file_path        TEXT,
    file_size_bytes  INTEGER,
    api_charge       REAL DEFAULT 0.0,
    status           TEXT DEFAULT 'pending',
    error_message    TEXT,
    downloaded_at    TEXT,
    FOREIGN KEY (queue_item_id) REFERENCES image_queue(id)
);

CREATE TABLE IF NOT EXISTS document_pages (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    download_id      INTEGER NOT NULL,
    page_number      INTEGER NOT NULL,
    image_path       TEXT NOT NULL,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (download_id) REFERENCES downloads(id)
);

CREATE TABLE IF NOT EXISTS analyses (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    download_id               INTEGER NOT NULL,
    queue_item_id             INTEGER NOT NULL,
    instrument_type           TEXT,
    instrument_number         TEXT,
    book                      TEXT,
    page                      TEXT,
    recording_date            TEXT,
    instrument_date           TEXT,
    grantors                  TEXT,
    grantees                  TEXT,
    legal_description         TEXT,
    section                   TEXT,
    township                  TEXT,
    range_val                 TEXT,
    interest_conveyed         TEXT,
    lease_royalty_terms       TEXT,
    title_requirement_affected TEXT,
    confidence_score          REAL,
    openai_cost               REAL DEFAULT 0.0,
    needs_review              INTEGER DEFAULT 0,
    raw_response              TEXT,
    analyzed_at               TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (download_id) REFERENCES downloads(id),
    FOREIGN KEY (queue_item_id) REFERENCES image_queue(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,
    description TEXT,
    data        TEXT,
    api_called  TEXT,
    cost        REAL,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cost_tracking (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    api_type    TEXT NOT NULL,
    amount      REAL NOT NULL,
    description TEXT,
    queue_item_id INTEGER,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_queue_status ON image_queue(status);
CREATE INDEX IF NOT EXISTS idx_queue_dedup  ON image_queue(dedup_key);
CREATE INDEX IF NOT EXISTS idx_downloads_queue ON downloads(queue_item_id);
CREATE INDEX IF NOT EXISTS idx_analyses_download ON analyses(download_id);
"""


def init_database() -> None:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn():
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_stats() -> dict:
    with get_conn() as conn:
        queue_total = conn.execute("SELECT COUNT(*) FROM image_queue").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM image_queue WHERE status='pending'").fetchone()[0]
        approved = conn.execute("SELECT COUNT(*) FROM image_queue WHERE status='approved'").fetchone()[0]
        downloaded = conn.execute("SELECT COUNT(*) FROM downloads WHERE status='success'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM downloads WHERE status='failed'").fetchone()[0]
        analyzed = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        needs_review = conn.execute("SELECT COUNT(*) FROM analyses WHERE needs_review=1").fetchone()[0]
        okcounty_cost = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM cost_tracking WHERE api_type='okcounty'"
        ).fetchone()[0]
        openai_cost = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM cost_tracking WHERE api_type='openai'"
        ).fetchone()[0]
        return {
            "queue_total": queue_total,
            "pending": pending,
            "approved": approved,
            "downloaded": downloaded,
            "failed_downloads": failed,
            "analyzed": analyzed,
            "needs_review": needs_review,
            "okcounty_cost": okcounty_cost,
            "openai_cost": openai_cost,
            "total_cost": okcounty_cost + openai_cost,
        }


def insert_many(table: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ",".join("?" for _ in cols)
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
    with get_conn() as conn:
        cursor = conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
        return cursor.rowcount


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def execute(sql: str, params: tuple = ()) -> int:
    with get_conn() as conn:
        cursor = conn.execute(sql, params)
        return cursor.lastrowid or cursor.rowcount


def log_audit(event_type: str, description: str, data: Any = None,
              api_called: str = None, cost: float = None) -> None:
    execute(
        "INSERT INTO audit_log (event_type, description, data, api_called, cost) VALUES (?,?,?,?,?)",
        (event_type, description, json.dumps(data) if data else None, api_called, cost),
    )


def track_cost(api_type: str, amount: float, description: str, queue_item_id: int = None) -> None:
    execute(
        "INSERT INTO cost_tracking (api_type, amount, description, queue_item_id) VALUES (?,?,?,?)",
        (api_type, amount, description, queue_item_id),
    )
