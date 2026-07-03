"""Thin SQLite access helpers over the schema in scripts/init_db.py.

Every insert is a small, explicit function so the call sites read as an audit
trail. The audit_log table is the durable 'every action leaves proof' record.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from init_db import init_db  # noqa: E402


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = init_db(db_path)  # ensures schema exists (idempotent)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def insert_document(
    conn: sqlite3.Connection,
    source_path: str,
    doc_type: Optional[str] = None,
    county: Optional[str] = None,
    trust: str = "untrusted",
) -> int:
    cur = conn.execute(
        "INSERT INTO documents(source_path, doc_type, county, trust) VALUES (?,?,?,?)",
        (source_path, doc_type, county, trust),
    )
    conn.commit()
    return int(cur.lastrowid)


def insert_extraction(
    conn: sqlite3.Connection,
    document_id: int,
    field_name: str,
    field_value: Any,
    confidence: Optional[float] = None,
    model: Optional[str] = None,
) -> int:
    if not isinstance(field_value, (str, type(None))):
        field_value = json.dumps(field_value)
    cur = conn.execute(
        "INSERT INTO extractions(document_id, field_name, field_value, confidence, model)"
        " VALUES (?,?,?,?,?)",
        (document_id, field_name, field_value, confidence, model),
    )
    conn.commit()
    return int(cur.lastrowid)


def log_audit(
    conn: sqlite3.Connection,
    actor: str,
    action: str,
    target: Optional[str] = None,
    detail: Any = None,
    approved_by: Optional[str] = None,
) -> int:
    if detail is not None and not isinstance(detail, str):
        detail = json.dumps(detail)
    cur = conn.execute(
        "INSERT INTO audit_log(actor, action, target, detail, approved_by)"
        " VALUES (?,?,?,?,?)",
        (actor, action, target, detail, approved_by),
    )
    conn.commit()
    return int(cur.lastrowid)
