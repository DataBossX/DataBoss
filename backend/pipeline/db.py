"""Pipeline-specific SQLite helpers — jobs table in the main backend DB."""

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

DB_PATH = os.getenv("SQLITE_DB_PATH", "./databossx.db")

JOB_TABLE = """
CREATE TABLE IF NOT EXISTS pipeline_jobs (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'queued',
    owner_name  TEXT,
    county      TEXT,
    state       TEXT,
    tract       TEXT,
    report_path TEXT,
    total_cost  REAL DEFAULT 0.0,
    error       TEXT,
    data        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON pipeline_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON pipeline_jobs(created_at DESC);
"""


@contextmanager
def _conn():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def ensure_jobs_table() -> None:
    with _conn() as con:
        con.executescript(JOB_TABLE)


def upsert_job(job_dict: dict) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO pipeline_jobs
                (id, source, status, owner_name, county, state, tract,
                 report_path, total_cost, error, data, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                report_path=excluded.report_path,
                total_cost=excluded.total_cost,
                error=excluded.error,
                data=excluded.data,
                updated_at=excluded.updated_at
            """,
            (
                job_dict["id"],
                job_dict["source"],
                job_dict["status"],
                job_dict.get("owner_name"),
                job_dict.get("county"),
                job_dict.get("state"),
                job_dict.get("tract_description"),
                job_dict.get("report_path"),
                job_dict.get("total_cost", 0.0),
                job_dict.get("error"),
                json.dumps(job_dict),
                job_dict["created_at"],
                job_dict["updated_at"],
            ),
        )


def get_job(job_id: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            "SELECT data FROM pipeline_jobs WHERE id=?", (job_id,)
        ).fetchone()
    if not row:
        return None
    return json.loads(row["data"])


def list_jobs(limit: int = 50, status: Optional[str] = None) -> list[dict]:
    sql = "SELECT data FROM pipeline_jobs"
    params: list = []
    if status:
        sql += " WHERE status=?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _conn() as con:
        rows = con.execute(sql, params).fetchall()
    return [json.loads(r["data"]) for r in rows]
