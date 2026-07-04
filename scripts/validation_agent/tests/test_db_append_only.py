"""Append-only DB enforcement, through the manager and via raw-sqlite bypass."""

from __future__ import annotations

import sqlite3

import pytest

from db.db_client import AppendOnlyViolation, DatabaseManager


def _seed(db: DatabaseManager) -> None:
    db.insert("launcher_events", {"event_type": "seed", "detail": "row"})


def test_insert_and_select_allowed(db: DatabaseManager):
    rid = db.insert("audit_events", {"event_type": "x", "detail": "d"})
    assert rid > 0
    rows = db.query("SELECT * FROM audit_events WHERE id = ?", (rid,))
    assert rows and rows[0]["event_type"] == "x"


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE runs SET status='x'",
        "DELETE FROM runs",
        "DROP TABLE runs",
        "ALTER TABLE runs ADD COLUMN foo TEXT",
        "REPLACE INTO runs (run_id) VALUES ('x')",
        "INSERT OR REPLACE INTO runs (run_id) VALUES ('x')",
        "INSERT INTO runs (run_id) VALUES ('a'); DROP TABLE runs",
        "VACUUM",
        "ATTACH DATABASE 'x.db' AS y",
    ],
)
def test_forbidden_statements_blocked(db: DatabaseManager, sql: str):
    with pytest.raises(AppendOnlyViolation):
        db.execute_insert(sql)


def test_upsert_on_conflict_blocked(db: DatabaseManager):
    with pytest.raises(AppendOnlyViolation):
        db.execute_insert(
            "INSERT INTO runs (run_id) VALUES ('a') ON CONFLICT DO NOTHING"
        )


def test_query_rejects_mutation(db: DatabaseManager):
    with pytest.raises(AppendOnlyViolation):
        db.query("DELETE FROM runs")


def test_raw_sqlite_update_blocked_by_trigger(db: DatabaseManager, settings):
    """Even bypassing the manager, triggers must block UPDATE/DELETE."""
    _seed(db)
    raw = sqlite3.connect(str(settings.db_path))
    try:
        with pytest.raises(sqlite3.Error):
            raw.execute("UPDATE launcher_events SET detail='hacked'")
            raw.commit()
        with pytest.raises(sqlite3.Error):
            raw.execute("DELETE FROM launcher_events")
            raw.commit()
    finally:
        raw.close()


def test_raw_sqlite_insert_still_works(db: DatabaseManager, settings):
    """Append (INSERT) must remain possible even on raw connections."""
    raw = sqlite3.connect(str(settings.db_path))
    try:
        raw.execute(
            "INSERT INTO launcher_events (event_type, created_at) VALUES ('raw','t')"
        )
        raw.commit()
    finally:
        raw.close()
    rows = db.query("SELECT * FROM launcher_events WHERE event_type='raw'")
    assert rows
