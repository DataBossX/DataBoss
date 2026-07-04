import sqlite3, pytest
from db.db_client import AppendOnlyViolation

def test_insert_and_select(audit, db):
    audit.launcher_event("e","d")
    rows = db.query("SELECT event, detail FROM launcher_events")
    assert rows and rows[0]["event"] == "e"

def test_update_blocked_via_manager(db, audit):
    audit.launcher_event("e","d")
    with pytest.raises(sqlite3.DatabaseError):
        db._conn.execute("UPDATE launcher_events SET detail='x'")

def test_delete_blocked_via_manager(db, audit):
    audit.launcher_event("e","d")
    with pytest.raises(sqlite3.DatabaseError):
        db._conn.execute("DELETE FROM launcher_events")

def test_raw_bypass_blocked_by_trigger(db, audit):
    audit.launcher_event("e","d")
    raw = sqlite3.connect(str(db.db_path))
    with pytest.raises(sqlite3.DatabaseError):
        raw.execute("UPDATE launcher_events SET detail='x'"); raw.commit()
    with pytest.raises(sqlite3.DatabaseError):
        raw.execute("DELETE FROM launcher_events"); raw.commit()
    raw.close()

def test_query_rejects_non_select(db):
    with pytest.raises(AppendOnlyViolation):
        db.query("UPDATE launcher_events SET detail='x'")

def test_query_rejects_multistatement(db):
    with pytest.raises(AppendOnlyViolation):
        db.query("SELECT 1; DROP TABLE runs")

def test_insert_rejects_unknown_table(db):
    with pytest.raises(AppendOnlyViolation):
        db.insert("evil", {"a": 1})
