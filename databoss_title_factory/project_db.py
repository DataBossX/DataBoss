"""Durable per-project SQLite state for resumable pipeline stages."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any


def database_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / "databoss_project.sqlite3"


def _connect(output_dir: str | Path) -> sqlite3.Connection:
    path = database_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def initialize(output_dir: str | Path) -> Path:
    with _connect(output_dir) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                project_root TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                pause_requested INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS stages (
                run_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                details_json TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (run_id, stage),
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                run_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                path TEXT NOT NULL,
                sha256 TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (run_id, path),
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
            """
        )
    return database_path(output_dir)


def register_run(output_dir: str | Path, run_id: str, project_root: str) -> None:
    initialize(output_dir)
    with _connect(output_dir) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO runs(run_id, project_root, created_at, status)
            VALUES (?, ?, ?, 'IN PROGRESS')
            """,
            (run_id, project_root, dt.datetime.now(dt.timezone.utc).isoformat()),
        )


def update_stage(
    output_dir: str | Path,
    run_id: str,
    stage: str,
    status: str,
    details: dict[str, Any] | None = None,
) -> None:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    completed = now if status in {"PASSED", "FAILED", "READY FOR REVIEW", "BLOCKED"} else None
    with _connect(output_dir) as connection:
        connection.execute(
            """
            INSERT INTO stages(run_id, stage, status, started_at, completed_at, details_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, stage) DO UPDATE SET
                status=excluded.status,
                started_at=COALESCE(stages.started_at, excluded.started_at),
                completed_at=excluded.completed_at,
                details_json=excluded.details_json
            """,
            (run_id, stage, status, now, completed, json.dumps(details or {}, default=str)),
        )


def request_pause(output_dir: str | Path, run_id: str, pause: bool = True) -> None:
    with _connect(output_dir) as connection:
        connection.execute(
            "UPDATE runs SET pause_requested=? WHERE run_id=?",
            (1 if pause else 0, run_id),
        )


def is_pause_requested(output_dir: str | Path, run_id: str) -> bool:
    with _connect(output_dir) as connection:
        row = connection.execute(
            "SELECT pause_requested FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
    return bool(row and row["pause_requested"])


def stage_statuses(output_dir: str | Path, run_id: str) -> list[dict[str, Any]]:
    with _connect(output_dir) as connection:
        rows = connection.execute(
            "SELECT stage, status, started_at, completed_at, details_json "
            "FROM stages WHERE run_id=? ORDER BY started_at",
            (run_id,),
        ).fetchall()
    return [
        {
            **dict(row),
            "details": json.loads(row["details_json"]),
        }
        for row in rows
    ]
