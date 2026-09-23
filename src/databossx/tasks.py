"""Durable task-graph helpers. Only the orchestrator commits transitions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from .database import DataBossDatabase
from .hashing import sha256_bytes


TASK_STATES = (
    "PLANNED",
    "BLOCKED",
    "READY",
    "LEASED",
    "RUNNING",
    "WAITING_HUMAN",
    "SUCCEEDED",
    "FAILED_RETRYABLE",
    "FAILED_TERMINAL",
)

LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "PLANNED": frozenset({"BLOCKED", "READY"}),
    "BLOCKED": frozenset({"READY", "FAILED_TERMINAL"}),
    "READY": frozenset({"LEASED"}),
    "LEASED": frozenset({"RUNNING", "READY"}),
    "RUNNING": frozenset({"SUCCEEDED", "WAITING_HUMAN", "FAILED_RETRYABLE", "FAILED_TERMINAL"}),
    "FAILED_RETRYABLE": frozenset({"READY"}),
    "WAITING_HUMAN": frozenset({"READY", "FAILED_TERMINAL"}),
    "SUCCEEDED": frozenset(),
    "FAILED_TERMINAL": frozenset(),
}

DEFAULT_LEASE_SECONDS = 300


class IllegalTaskTransition(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def transition(db: DataBossDatabase, task_id: int, new_state: str) -> str:
    row = db.fetchone("SELECT state FROM tasks WHERE id = ?", (task_id,))
    if row is None:
        raise IllegalTaskTransition(f"unknown task {task_id}")
    current = str(row["state"])
    if new_state not in LEGAL_TRANSITIONS.get(current, frozenset()):
        raise IllegalTaskTransition(f"illegal transition {current} -> {new_state}")
    db.execute("UPDATE tasks SET state = ? WHERE id = ?", (new_state, task_id))
    return new_state


def seed_ready_task(
    db: DataBossDatabase,
    run_id: int,
    task_type: str,
    payload: dict[str, Any],
    *,
    capability: str = "",
    priority: int = 100,
) -> int:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    idempotency_key = sha256_bytes(f"{run_id}:{task_type}:{body}".encode("utf-8"))
    existing = db.fetchone(
        "SELECT task_id FROM task_manifests WHERE idempotency_key = ?",
        (idempotency_key,),
    )
    if existing:
        return int(existing["task_id"])
    task_id = db.execute(
        """
        INSERT INTO tasks (run_id, task_type, state, priority, payload_json)
        VALUES (?, ?, 'READY', ?, ?)
        """,
        (run_id, task_type, priority, body),
    )
    db.execute(
        """
        INSERT INTO task_manifests (task_id, input_manifest_hash, idempotency_key, capability)
        VALUES (?, ?, ?, ?)
        """,
        (task_id, sha256_bytes(body.encode("utf-8")), idempotency_key, capability),
    )
    return task_id


def lease_task(db: DataBossDatabase, task_id: int, worker_id: str, ttl_seconds: int = DEFAULT_LEASE_SECONDS) -> int:
    transition(db, task_id, "LEASED")
    expires = _iso(_now() + timedelta(seconds=ttl_seconds))
    lease_id = db.execute(
        """
        INSERT INTO task_leases (task_id, worker_id, expires_at, heartbeat_at)
        VALUES (?, ?, ?, ?)
        """,
        (task_id, worker_id, expires, _iso(_now())),
    )
    db.execute(
        "INSERT INTO task_attempts (task_id, worker_name, status) VALUES (?, ?, 'LEASED')",
        (task_id, worker_id),
    )
    return lease_id


def heartbeat(db: DataBossDatabase, lease_id: int, ttl_seconds: int = DEFAULT_LEASE_SECONDS) -> None:
    db.execute(
        "UPDATE task_leases SET heartbeat_at = ?, expires_at = ? WHERE id = ?",
        (_iso(_now()), _iso(_now() + timedelta(seconds=ttl_seconds)), lease_id),
    )


def expire_stale_leases(db: DataBossDatabase) -> list[int]:
    now = _iso(_now())
    rows = db.fetchall(
        """
        SELECT tl.id, tl.task_id, t.state
          FROM task_leases tl
          JOIN tasks t ON t.id = tl.task_id
         WHERE tl.expires_at <= ?
           AND t.state IN ('LEASED', 'RUNNING')
        """,
        (now,),
    )
    expired: list[int] = []
    for row in rows:
        db.execute("UPDATE tasks SET state = 'READY' WHERE id = ?", (row["task_id"],))
        expired.append(int(row["task_id"]))
    return expired


def start_task(db: DataBossDatabase, task_id: int) -> str:
    return transition(db, task_id, "RUNNING")


def complete_task(
    db: DataBossDatabase,
    task_id: int,
    *,
    success: bool,
    outcome: dict[str, Any] | None = None,
    retryable: bool = False,
) -> str:
    if _current(db, task_id) == "LEASED":
        start_task(db, task_id)
    if success:
        state = "SUCCEEDED"
    elif retryable:
        state = "FAILED_RETRYABLE"
    else:
        state = "FAILED_TERMINAL"
    new_state = transition(db, task_id, state)
    db.execute(
        "UPDATE task_manifests SET outcome_json = ? WHERE task_id = ?",
        (json.dumps(outcome or {}, sort_keys=True), task_id),
    )
    return new_state


def _current(db: DataBossDatabase, task_id: int) -> str:
    row = db.fetchone("SELECT state FROM tasks WHERE id = ?", (task_id,))
    if row is None:
        raise IllegalTaskTransition(f"unknown task {task_id}")
    return str(row["state"])
