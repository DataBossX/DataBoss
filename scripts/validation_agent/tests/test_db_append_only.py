"""Prove the database is append-only: INSERT/SELECT work; UPDATE/DELETE are
blocked at the manager level, at the authorizer level, AND at the trigger level
(so even a raw sqlite3 connection cannot bypass it)."""

import sqlite3

import pytest

from db.db_client import DatabaseManager, AppendOnlyViolation


@pytest.fixture()
def db(tmp_path):
    d = DatabaseManager(tmp_path / "audit.db")
    yield d
    d.close()


def test_insert_and_select_work(db):
    rowid = db.record_launcher_event("start", "launcher started")
    assert rowid > 0
    rows = db.query("SELECT * FROM launcher_events")
    assert len(rows) == 1
    assert rows[0]["event_type"] == "start"


def test_manager_blocks_update_string(db):
    db.record_launcher_event("start", "x")
    with pytest.raises(AppendOnlyViolation):
        db.execute("UPDATE launcher_events SET event_type='y' WHERE id=1")


def test_manager_blocks_delete_string(db):
    db.record_launcher_event("start", "x")
    with pytest.raises(AppendOnlyViolation):
        db.execute("DELETE FROM launcher_events WHERE id=1")


def test_manager_blocks_multistatement(db):
    with pytest.raises(AppendOnlyViolation):
        db.execute("INSERT INTO launcher_events(event_type) VALUES('a'); "
                   "INSERT INTO launcher_events(event_type) VALUES('b')")


def test_manager_blocks_insert_or_replace(db):
    with pytest.raises(AppendOnlyViolation):
        db.execute("INSERT OR REPLACE INTO launcher_events(id,event_type) "
                   "VALUES(1,'z')")


def test_authorizer_blocks_update_on_manager_connection(db):
    db.record_launcher_event("start", "x")
    # Bypass the string screen by calling the raw connection directly; the
    # authorizer must still deny the UPDATE on a protected table.
    with pytest.raises(sqlite3.DatabaseError):
        db._conn.execute("UPDATE launcher_events SET event_type='y'")


def test_raw_connection_bypass_is_blocked_by_triggers(tmp_path):
    d = DatabaseManager(tmp_path / "audit.db")
    d.record_launcher_event("start", "x")
    d.close()
    # A brand-new raw connection with NO authorizer installed. The database
    # triggers are the durable defense and must still block the UPDATE/DELETE.
    raw = sqlite3.connect(tmp_path / "audit.db")
    with pytest.raises(sqlite3.DatabaseError):
        raw.execute("UPDATE launcher_events SET event_type='hacked' WHERE id=1")
        raw.commit()
    with pytest.raises(sqlite3.DatabaseError):
        raw.execute("DELETE FROM launcher_events WHERE id=1")
        raw.commit()
    # Data is intact.
    row = raw.execute("SELECT event_type FROM launcher_events WHERE id=1").fetchone()
    assert row[0] == "start"
    raw.close()
