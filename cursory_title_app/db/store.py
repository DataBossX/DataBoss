"""Local-first SQLite store: work queue + evidence + audit.

This is where ALL metadata, OCR confidence, screenshots paths, source URLs,
manual corrections, and processing status live. None of this ever goes into the
workbook (the workbook only gets vetted values in its existing cells).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .. import config

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS index_rows (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    page_number   INTEGER,
    grantor       TEXT,
    grantee       TEXT,
    instrument_kind TEXT,
    book          TEXT,
    page          TEXT,
    date_filed    TEXT,
    legal_note    TEXT,
    remarks       TEXT,
    confidence    REAL,
    needs_review  INTEGER DEFAULT 1,
    raw_json      TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS work_queue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key     TEXT UNIQUE,
    source        TEXT,                 -- 'index' | 'runsheet' | 'manual'
    runsheet_row  INTEGER,              -- existing row this maps to, if any
    instrument_number TEXT,
    book_page     TEXT,
    doc_type      TEXT,
    grantor       TEXT,
    grantee       TEXT,
    document_url  TEXT,
    status        TEXT DEFAULT 'pending', -- pending|in_progress|extracted|review|done|skipped
    diff_kind     TEXT,                 -- missing|duplicate|conflict|present
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS evidence (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id      INTEGER,
    kind          TEXT,                 -- 'screenshot'|'pdf'|'page_text'|'ocr'|'extraction'|'manual'
    provider      TEXT,
    source_url    TEXT,
    file_path     TEXT,
    confidence    REAL,
    payload_json  TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (queue_id) REFERENCES work_queue(id)
);

CREATE TABLE IF NOT EXISTS corrections (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id      INTEGER,
    field         TEXT,
    old_value     TEXT,
    new_value     TEXT,
    corrected_by  TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (queue_id) REFERENCES work_queue(id)
);

CREATE INDEX IF NOT EXISTS idx_queue_status ON work_queue(status);
CREATE INDEX IF NOT EXISTS idx_evidence_queue ON evidence(queue_id);
"""


def init() -> None:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.DB_PATH) as c:
        c.executescript(SCHEMA)


@contextmanager
def conn():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def insert(table: str, row: dict) -> int:
    cols = list(row.keys())
    ph = ",".join("?" for _ in cols)
    with conn() as c:
        cur = c.execute(
            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph})",
            tuple(row[k] for k in cols),
        )
        return cur.lastrowid


def upsert_queue(item: dict) -> int:
    """Insert-or-update a work-queue item keyed by dedup_key. On re-analysis the
    mutable fields (diff_kind, status, runsheet_row, …) are refreshed so counts
    and pull lists never go stale. Always returns the row id (never 0), so
    evidence is attached to the right item."""
    cols = list(item.keys())
    ph = ",".join("?" for _ in cols)
    updatable = [c for c in cols if c != "dedup_key"]
    set_clause = ",".join(f"{c}=excluded.{c}" for c in updatable) or "dedup_key=dedup_key"
    with conn() as c:
        c.execute(
            f"INSERT INTO work_queue ({','.join(cols)}) VALUES ({ph}) "
            f"ON CONFLICT(dedup_key) DO UPDATE SET {set_clause}",
            tuple(item[k] for k in cols),
        )
        row = c.execute("SELECT id FROM work_queue WHERE dedup_key=?",
                        (item["dedup_key"],)).fetchone()
        return row[0] if row else 0


def fetch_all(sql: str, params: Iterable = ()) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute(sql, tuple(params)).fetchall()]


def fetch_one(sql: str, params: Iterable = ()) -> dict | None:
    with conn() as c:
        r = c.execute(sql, tuple(params)).fetchone()
        return dict(r) if r else None


def execute(sql: str, params: Iterable = ()) -> int:
    with conn() as c:
        cur = c.execute(sql, tuple(params))
        return cur.lastrowid or cur.rowcount


def add_evidence(queue_id: int, kind: str, *, provider=None, source_url=None,
                 file_path=None, confidence=None, payload: Any = None) -> int:
    return insert("evidence", {
        "queue_id": queue_id, "kind": kind, "provider": provider,
        "source_url": source_url, "file_path": file_path,
        "confidence": confidence,
        "payload_json": json.dumps(payload) if payload is not None else None,
    })


def record_correction(queue_id: int, field: str, old, new, by: str) -> int:
    return insert("corrections", {
        "queue_id": queue_id, "field": field,
        "old_value": str(old) if old is not None else None,
        "new_value": str(new) if new is not None else None,
        "corrected_by": by,
    })


def audit(event: str, detail: str = "", data: Any = None) -> None:
    """Append-only JSONL audit trail. Fail loudly, never silently."""
    config.AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.now().isoformat(), "event": event, "detail": detail}
    if data is not None:
        rec["data"] = data
    with open(config.AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def stats() -> dict:
    with conn() as c:
        def n(sql):
            return c.execute(sql).fetchone()[0]
        return {
            "index_rows": n("SELECT COUNT(*) FROM index_rows"),
            "queue_total": n("SELECT COUNT(*) FROM work_queue"),
            "pending": n("SELECT COUNT(*) FROM work_queue WHERE status='pending'"),
            "review": n("SELECT COUNT(*) FROM work_queue WHERE status='review'"),
            "done": n("SELECT COUNT(*) FROM work_queue WHERE status='done'"),
            "missing": n("SELECT COUNT(*) FROM work_queue WHERE diff_kind='missing'"),
            "duplicate": n("SELECT COUNT(*) FROM work_queue WHERE diff_kind='duplicate'"),
            "conflict": n("SELECT COUNT(*) FROM work_queue WHERE diff_kind='conflict'"),
        }
