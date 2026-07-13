"""Tests for databossx.audit.events.AuditLog."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pytest

from databossx.audit.events import AuditLog


@pytest.fixture()
def audit_log(tmp_path):
    return AuditLog(tmp_path / "audit.db")


def test_record_returns_event_id(audit_log):
    event_id = audit_log.record(event_type="project.created", actor="user1", project_id="p1")
    assert isinstance(event_id, str)
    assert len(event_id) > 0


def test_record_persists_payload_as_json(audit_log):
    event_id = audit_log.record(
        event_type="task.completed",
        actor="worker1",
        task_id="t1",
        payload={"duration_ms": 1234},
    )
    results = audit_log.query(event_type="task.completed")
    assert len(results) == 1
    assert results[0]["id"] == event_id
    assert '"duration_ms": 1234' in results[0]["payload_json"]


def test_query_filters_by_project_id(audit_log):
    audit_log.record(event_type="a", project_id="p1")
    audit_log.record(event_type="b", project_id="p2")
    results = audit_log.query(project_id="p1")
    assert len(results) == 1
    assert results[0]["project_id"] == "p1"


def test_query_filters_by_event_type(audit_log):
    audit_log.record(event_type="task.completed", project_id="p1")
    audit_log.record(event_type="task.failed", project_id="p1")
    results = audit_log.query(event_type="task.failed")
    assert len(results) == 1
    assert results[0]["event_type"] == "task.failed"


def test_query_filters_by_since(audit_log):
    audit_log.record(event_type="old_event", project_id="p1")
    time.sleep(0.01)
    cutoff = datetime.now(timezone.utc)
    time.sleep(0.01)
    audit_log.record(event_type="new_event", project_id="p1")

    results = audit_log.query(since=cutoff)
    event_types = {r["event_type"] for r in results}
    assert "new_event" in event_types
    assert "old_event" not in event_types


def test_query_orders_newest_first(audit_log):
    audit_log.record(event_type="first")
    time.sleep(0.01)
    audit_log.record(event_type="second")
    time.sleep(0.01)
    audit_log.record(event_type="third")

    results = audit_log.query(limit=10)
    event_types = [r["event_type"] for r in results]
    assert event_types == ["third", "second", "first"]


def test_query_respects_limit(audit_log):
    for i in range(5):
        audit_log.record(event_type=f"event_{i}")
    results = audit_log.query(limit=2)
    assert len(results) == 2


def test_audit_events_table_rejects_update(audit_log):
    event_id = audit_log.record(event_type="immutable_test")
    conn = sqlite3.connect(audit_log.db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE audit_events SET event_type = 'tampered' WHERE id = ?",
                (event_id,),
            )
    finally:
        conn.close()


def test_audit_events_table_rejects_delete(audit_log):
    event_id = audit_log.record(event_type="immutable_test_2")
    conn = sqlite3.connect(audit_log.db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM audit_events WHERE id = ?", (event_id,))
    finally:
        conn.close()
