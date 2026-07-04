"""Append-only DB enforcement: INSERT/SELECT ok; UPDATE/DELETE and raw bypass blocked."""
import sqlite3
import pytest

from db.db_client import DatabaseManager, AppendOnlyViolation


def test_insert_and_select(db):
    rid = db.insert("runs", {"run_id": "r1", "status": "INIT"})
    assert rid == 1
    rows = db.query("SELECT run_id, status FROM runs")
    assert rows[0]["run_id"] == "r1"
    assert db.count("runs") == 1


def test_manager_update_blocked_by_authorizer(db):
    db.insert("runs", {"run_id": "r2", "status": "INIT"})
    conn = db._guarded_connect()
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE runs SET status='X' WHERE run_id='r2'")
    conn.close()


def test_raw_update_blocked_by_trigger(db):
    db.insert("runs", {"run_id": "r3", "status": "INIT"})
    raw = sqlite3.connect(str(db.db_path))
    with pytest.raises(sqlite3.DatabaseError):
        raw.execute("UPDATE runs SET status='X' WHERE run_id='r3'")
        raw.commit()
    raw.close()


def test_raw_delete_blocked_by_trigger(db):
    db.insert("runs", {"run_id": "r4", "status": "INIT"})
    raw = sqlite3.connect(str(db.db_path))
    with pytest.raises(sqlite3.DatabaseError):
        raw.execute("DELETE FROM runs WHERE run_id='r4'")
        raw.commit()
    raw.close()
    # row survived
    assert db.count("runs", "run_id=?", ("r4",)) == 1


def test_insert_or_replace_and_upsert_blocked(db):
    with pytest.raises(AppendOnlyViolation):
        db._reject_unsafe("INSERT OR REPLACE INTO runs (run_id) VALUES ('x')")
    with pytest.raises(AppendOnlyViolation):
        db._reject_unsafe("INSERT INTO runs (run_id) VALUES ('x') ON CONFLICT DO UPDATE SET status='y'")
    with pytest.raises(AppendOnlyViolation):
        db._reject_unsafe("INSERT INTO runs (run_id) VALUES ('x'); DROP TABLE runs")


def test_query_rejects_non_select(db):
    with pytest.raises(AppendOnlyViolation):
        db.query("UPDATE runs SET status='x'")
