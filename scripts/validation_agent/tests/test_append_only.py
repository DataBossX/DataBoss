"""Phase 1 done-definition: the DB initializes and rejects UPDATE/DELETE."""

from __future__ import annotations

import sqlite3

import pytest

from validation_agent.config.settings import config
from validation_agent.db.db_client import AppendOnlyViolation, DatabaseManager


@pytest.fixture()
def dbm(tmp_path):
    m = DatabaseManager(db_path=tmp_path / "t.db", schema_path=config.schema_path)
    m.init()
    return m


def test_insert_and_read(dbm):
    rid = dbm.insert("audit_log", {"event_type": "t", "description": "hi",
                                   "data": {"k": 1}})
    assert rid == 1
    rows = dbm.query("SELECT event_type, data FROM audit_log")
    assert rows[0]["event_type"] == "t"
    assert '"k": 1' in rows[0]["data"]


def test_query_guard_blocks_update(dbm):
    with pytest.raises(AppendOnlyViolation):
        dbm.query("UPDATE audit_log SET description='x'")
    with pytest.raises(AppendOnlyViolation):
        dbm.query("DELETE FROM audit_log")


def test_authorizer_backstops_update_and_delete(dbm):
    dbm.insert("audit_log", {"event_type": "t", "description": "hi"})
    with dbm.connect() as conn:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("UPDATE audit_log SET description='x'")
    with dbm.connect() as conn:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM audit_log")


def test_autoincrement_still_works(dbm):
    a = dbm.insert("audit_log", {"event_type": "a", "description": "1"})
    b = dbm.insert("audit_log", {"event_type": "b", "description": "2"})
    assert b == a + 1
