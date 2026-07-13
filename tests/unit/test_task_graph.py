"""Tests for databossx.tasks.graph.TaskGraph."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from databossx.tasks.graph import TaskGraph


@pytest.fixture()
def graph(tmp_path):
    return TaskGraph(tmp_path / "tasks.db")


def test_add_task_defaults_to_planned(graph):
    task_id = graph.add_task(run_id="run1", name="ocr", worker_type="ocr", input_json="{}")
    conn = graph._connect()
    try:
        row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()
    assert row["status"] == "PLANNED"


def test_task_without_dependencies_promotes_to_ready(graph):
    task_id = graph.add_task(run_id="run1", name="ocr", worker_type="ocr", input_json="{}")
    promoted = graph.promote_ready("run1")
    assert promoted == 1
    ready = graph.ready_tasks("run1")
    assert len(ready) == 1
    assert ready[0]["id"] == task_id


def test_task_with_pending_dependency_stays_planned(graph):
    upstream = graph.add_task(run_id="run1", name="scan", worker_type="scanner", input_json="{}")
    downstream = graph.add_task(
        run_id="run1",
        name="ocr",
        worker_type="ocr",
        input_json="{}",
        depends_on=[upstream],
    )
    promoted = graph.promote_ready("run1")
    # Only the upstream task (no deps) should promote.
    assert promoted == 1
    ready_ids = {t["id"] for t in graph.ready_tasks("run1")}
    assert upstream in ready_ids
    assert downstream not in ready_ids


def test_acquire_lease_moves_ready_to_leased(graph):
    task_id = graph.add_task(run_id="run1", name="ocr", worker_type="ocr", input_json="{}")
    graph.promote_ready("run1")
    lease_id = graph.acquire_lease(task_id, worker_id="worker1", duration_seconds=60)
    assert lease_id is not None

    conn = graph._connect()
    try:
        row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()
    assert row["status"] == "LEASED"


def test_acquire_lease_fails_if_not_ready(graph):
    task_id = graph.add_task(run_id="run1", name="ocr", worker_type="ocr", input_json="{}")
    # Task is still PLANNED, not READY.
    lease_id = graph.acquire_lease(task_id, worker_id="worker1")
    assert lease_id is None


def test_heartbeat_extends_lease(graph):
    task_id = graph.add_task(run_id="run1", name="ocr", worker_type="ocr", input_json="{}")
    graph.promote_ready("run1")
    lease_id = graph.acquire_lease(task_id, worker_id="worker1", duration_seconds=60)

    conn = graph._connect()
    try:
        before = conn.execute(
            "SELECT expires_at FROM task_leases WHERE id = ?", (lease_id,)
        ).fetchone()["expires_at"]
    finally:
        conn.close()

    time.sleep(0.01)
    assert graph.heartbeat(lease_id) is True

    conn = graph._connect()
    try:
        after = conn.execute(
            "SELECT expires_at FROM task_leases WHERE id = ?", (lease_id,)
        ).fetchone()["expires_at"]
    finally:
        conn.close()
    assert after >= before


def test_heartbeat_fails_for_unknown_lease(graph):
    assert graph.heartbeat("nonexistent-lease") is False


def test_complete_task_unblocks_downstream(graph):
    upstream = graph.add_task(run_id="run1", name="scan", worker_type="scanner", input_json="{}")
    downstream = graph.add_task(
        run_id="run1",
        name="ocr",
        worker_type="ocr",
        input_json="{}",
        depends_on=[upstream],
    )
    graph.promote_ready("run1")
    lease_id = graph.acquire_lease(upstream, worker_id="worker1")
    assert lease_id is not None

    graph.complete_task(lease_id, output_json='{"result": "ok"}')

    conn = graph._connect()
    try:
        upstream_status = conn.execute(
            "SELECT status, output_json FROM tasks WHERE id = ?", (upstream,)
        ).fetchone()
        downstream_status = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (downstream,)
        ).fetchone()
    finally:
        conn.close()

    assert upstream_status["status"] == "SUCCEEDED"
    assert upstream_status["output_json"] == '{"result": "ok"}'
    assert downstream_status["status"] == "READY"


def test_fail_task_retryable(graph):
    task_id = graph.add_task(run_id="run1", name="ocr", worker_type="ocr", input_json="{}")
    graph.promote_ready("run1")
    lease_id = graph.acquire_lease(task_id, worker_id="worker1")

    graph.fail_task(lease_id, error="transient network error", retryable=True)

    conn = graph._connect()
    try:
        row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()
    assert row["status"] == "FAILED_RETRYABLE"


def test_fail_task_terminal(graph):
    task_id = graph.add_task(run_id="run1", name="ocr", worker_type="ocr", input_json="{}")
    graph.promote_ready("run1")
    lease_id = graph.acquire_lease(task_id, worker_id="worker1")

    graph.fail_task(lease_id, error="permanent validation error", retryable=False)

    conn = graph._connect()
    try:
        row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()
    assert row["status"] == "FAILED_TERMINAL"


def test_expire_leases_recovers_expired_tasks(graph):
    task_id = graph.add_task(run_id="run1", name="ocr", worker_type="ocr", input_json="{}")
    graph.promote_ready("run1")
    lease_id = graph.acquire_lease(task_id, worker_id="worker1", duration_seconds=60)

    # Force the lease into the past to simulate expiry.
    conn = graph._connect()
    try:
        past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        conn.execute("UPDATE task_leases SET expires_at = ? WHERE id = ?", (past, lease_id))
        conn.execute("UPDATE tasks SET lease_expires_at = ? WHERE id = ?", (past, task_id))
        conn.commit()
    finally:
        conn.close()

    recovered = graph.expire_leases()
    assert recovered == 1

    conn = graph._connect()
    try:
        row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()
    assert row["status"] == "READY"


def test_expire_leases_ignores_active_leases(graph):
    task_id = graph.add_task(run_id="run1", name="ocr", worker_type="ocr", input_json="{}")
    graph.promote_ready("run1")
    graph.acquire_lease(task_id, worker_id="worker1", duration_seconds=300)

    recovered = graph.expire_leases()
    assert recovered == 0

    conn = graph._connect()
    try:
        row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()
    assert row["status"] == "LEASED"
