"""Durable task-graph execution engine for the DataBossX operating system.

This module implements the execution contract described in
``docs/DATABOSSX_OS_BLUEPRINT.md``:

* One orchestrator commits every task state transition ("one writer").
* Work is a durable task graph with explicit dependencies.
* Workers receive a leased task and return an outcome; they never mutate task
  state or create downstream tasks directly. The orchestrator does that after a
  worker returns, which keeps state transitions single-writer and auditable.
* Every transition emits an append-only ``audit_events`` row and an
  ``outbox_events`` row for reliable downstream delivery. **The task-state
  change, the attempt/lease writes, and both event rows are committed in one
  SQLite transaction** — a crash before ``COMMIT`` rolls the whole thing back,
  so no state transition can ever survive without its audit and outbox record
  (and vice versa). This is proven by the failure-injection tests in
  ``tests/test_databossx_executor.py``.
* Attempts are bounded and retryable; abandoned leases are recovered so a
  crashed worker never strands a task.

The engine is deterministic and stdlib-only. Time is injected through a
``clock`` callable so lease expiry and recovery are testable without sleeping.

Task states
-----------
``BLOCKED``   waiting on one or more parent tasks that are not yet ``DONE``.
``READY``     eligible to be leased.
``LEASED``    leased to a worker and executing.
``DONE``      completed successfully (terminal).
``FAILED``    exhausted its attempt budget or hit an unrecoverable error
              (terminal).

Run states follow the tasks: ``RUNNING`` while work remains, ``COMPLETED`` when
every task is ``DONE``, ``BLOCKED`` when work remains but nothing is runnable
(for example a failed parent), and ``FAILED`` when work stopped with a failure
and nothing runnable remains.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping

from .database import DataBossDatabase

# --- Task states -----------------------------------------------------------
STATE_BLOCKED = "BLOCKED"
STATE_READY = "READY"
STATE_LEASED = "LEASED"
STATE_DONE = "DONE"
STATE_FAILED = "FAILED"

TERMINAL_STATES = frozenset({STATE_DONE, STATE_FAILED})

# --- Attempt statuses ------------------------------------------------------
ATTEMPT_RUNNING = "RUNNING"
ATTEMPT_SUCCEEDED = "SUCCEEDED"
ATTEMPT_FAILED = "FAILED"
ATTEMPT_LEASE_EXPIRED = "LEASE_EXPIRED"

# --- Run states ------------------------------------------------------------
RUN_RUNNING = "RUNNING"
RUN_COMPLETED = "COMPLETED"
RUN_BLOCKED = "BLOCKED"
RUN_FAILED = "FAILED"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    """Serialize to a sortable ISO-8601 UTC string (``...Z``)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _json(data) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


class TaskExecutionError(RuntimeError):
    """Raised for unrecoverable orchestration faults (never a worker failure)."""


@dataclass(frozen=True)
class TaskContext:
    """Read-only view of a leased task handed to a worker handler."""

    task_id: int
    run_id: int
    project_id: str
    task_type: str
    payload: Mapping[str, object]
    attempt_number: int
    worker_id: str


@dataclass(frozen=True)
class FollowUpTask:
    """A downstream task a handler asks the orchestrator to create on success.

    The handler only describes the work; the orchestrator is the single writer
    that actually inserts the task and wires the dependency edge to the parent.
    """

    task_type: str
    payload: Mapping[str, object] = field(default_factory=dict)
    priority: int = 100


@dataclass(frozen=True)
class TaskOutcome:
    """What a worker handler returns for a task.

    Handlers may return a ``TaskOutcome``, a plain ``dict`` (treated as a
    successful result payload), or ``None`` (success with an empty result).
    Raising an exception is a failure and is caught by the orchestrator.
    """

    success: bool = True
    result: Mapping[str, object] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    follow_up: tuple[FollowUpTask, ...] = ()

    @classmethod
    def ok(cls, result: Mapping[str, object] | None = None, *, follow_up=()) -> "TaskOutcome":
        return cls(success=True, result=dict(result or {}), follow_up=tuple(follow_up))

    @classmethod
    def fail(cls, error_code: str, error_message: str | None = None) -> "TaskOutcome":
        return cls(success=False, error_code=error_code, error_message=error_message)


Handler = Callable[[TaskContext], "TaskOutcome | Mapping[str, object] | None"]


class WorkerRegistry:
    """Maps a ``task_type`` to the handler that executes it."""

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, task_type: str, handler: Handler) -> None:
        if not callable(handler):
            raise TypeError(f"Handler for {task_type!r} must be callable")
        self._handlers[task_type] = handler

    def handler(self, task_type: str):
        """Decorator form of :meth:`register`."""

        def _decorator(func: Handler) -> Handler:
            self.register(task_type, func)
            return func

        return _decorator

    def get(self, task_type: str) -> Handler | None:
        return self._handlers.get(task_type)

    def __contains__(self, task_type: str) -> bool:
        return task_type in self._handlers


@dataclass(frozen=True)
class RunSummary:
    """Aggregate outcome of :meth:`Orchestrator.run_until_idle`."""

    processed: int
    succeeded: int
    failed: int
    remaining: int
    run_status: str | None


class Orchestrator:
    """Single-writer engine that drives the durable task graph forward.

    Only this object writes task/run state transitions, leases, attempts, and
    downstream tasks. Workers are pure functions of a :class:`TaskContext`.
    """

    def __init__(
        self,
        db: DataBossDatabase,
        registry: WorkerRegistry,
        *,
        worker_id: str = "orchestrator-1",
        max_attempts: int = 3,
        lease_seconds: int = 300,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be >= 1")
        self.db = db
        self.registry = registry
        self.worker_id = worker_id
        self.max_attempts = max_attempts
        self.lease_seconds = lease_seconds
        self._clock = clock

    # -- public API ---------------------------------------------------------

    def promote_ready_tasks(self, run_id: int | None = None) -> list[int]:
        """Flip ``BLOCKED`` tasks whose parents are all ``DONE`` to ``READY``.

        Returns the ids of the tasks promoted. Idempotent.
        """
        promoted: list[int] = []
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                f"""
                SELECT t.id AS id, r.project_id AS project_id
                  FROM tasks t
                  JOIN runs r ON r.id = t.run_id
                 WHERE t.state = '{STATE_BLOCKED}'
                   {"AND t.run_id = ?" if run_id is not None else ""}
                   AND NOT EXISTS (
                       SELECT 1 FROM task_dependencies d
                         JOIN tasks p ON p.id = d.parent_task_id
                        WHERE d.child_task_id = t.id
                          AND p.state <> '{STATE_DONE}'
                   )
                 ORDER BY t.id
                """,
                (run_id,) if run_id is not None else (),
            ).fetchall()
            for row in rows:
                task_id = int(row["id"])
                conn.execute("UPDATE tasks SET state = ? WHERE id = ?", (STATE_READY, task_id))
                # Same transaction as the state change: no promotion can commit
                # without its audit and outbox record, and none can survive alone.
                self._emit_in_conn(conn, task_id, "task.promoted", {"to": STATE_READY}, row["project_id"])
                promoted.append(task_id)
            conn.commit()
        return promoted

    def claim_next_task(self, run_id: int | None = None) -> TaskContext | None:
        """Atomically lease the highest-priority runnable task.

        A task is runnable when it is ``READY`` and every parent is ``DONE``.
        Lower ``priority`` numbers are leased first. Returns ``None`` when no
        task is currently claimable.
        """
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                f"""
                SELECT t.id, t.run_id, t.task_type, t.payload_json, r.project_id
                  FROM tasks t
                  JOIN runs r ON r.id = t.run_id
                 WHERE t.state = '{STATE_READY}'
                   {"AND t.run_id = ?" if run_id is not None else ""}
                   AND NOT EXISTS (
                       SELECT 1 FROM task_dependencies d
                         JOIN tasks p ON p.id = d.parent_task_id
                        WHERE d.child_task_id = t.id
                          AND p.state <> '{STATE_DONE}'
                   )
                 ORDER BY t.priority ASC, t.id ASC
                 LIMIT 1
                """,
                (run_id,) if run_id is not None else (),
            ).fetchone()
            if row is None:
                conn.rollback()
                return None

            task_id = int(row["id"])
            now = self._clock()
            attempt_number = (
                conn.execute(
                    "SELECT COUNT(*) AS n FROM task_attempts WHERE task_id = ?",
                    (task_id,),
                ).fetchone()["n"]
                + 1
            )
            conn.execute("UPDATE tasks SET state = ? WHERE id = ?", (STATE_LEASED, task_id))
            conn.execute(
                """
                INSERT INTO task_leases (task_id, worker_id, leased_at, expires_at, heartbeat_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    self.worker_id,
                    _iso(now),
                    _iso(now + timedelta(seconds=self.lease_seconds)),
                    _iso(now),
                ),
            )
            conn.execute(
                """
                INSERT INTO task_attempts (task_id, worker_name, started_at, status)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, self.worker_id, _iso(now), ATTEMPT_RUNNING),
            )
            # State + lease + attempt + audit + outbox commit as one unit: a
            # crash before commit rolls the lease back to READY with no orphan
            # audit/outbox row.
            self._emit_in_conn(
                conn,
                task_id,
                "task.leased",
                {"worker_id": self.worker_id, "attempt": int(attempt_number)},
                row["project_id"],
            )
            conn.commit()
            payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
            context = TaskContext(
                task_id=task_id,
                run_id=int(row["run_id"]),
                project_id=row["project_id"],
                task_type=row["task_type"],
                payload=payload,
                attempt_number=int(attempt_number),
                worker_id=self.worker_id,
            )
        return context

    def execute_task(self, context: TaskContext) -> TaskOutcome:
        """Run the registered handler for a leased task and commit the outcome.

        Handler exceptions are caught and converted to a failed outcome so one
        bad worker never crashes the orchestrator loop.
        """
        handler = self.registry.get(context.task_type)
        if handler is None:
            outcome = TaskOutcome.fail(
                "no_handler",
                f"No worker registered for task_type {context.task_type!r}",
            )
            self._finalize(context, outcome, unrecoverable=True)
            return outcome

        try:
            raw = handler(context)
        except Exception as exc:  # noqa: BLE001 - isolate worker faults
            outcome = TaskOutcome.fail(type(exc).__name__, str(exc))
            self._finalize(context, outcome)
            return outcome

        outcome = _coerce_outcome(raw)
        self._finalize(context, outcome)
        return outcome

    def run_until_idle(self, run_id: int | None = None, *, max_iterations: int = 10_000) -> RunSummary:
        """Promote, claim, and execute tasks until nothing is runnable.

        Bounded by ``max_iterations`` as a safety valve against a handler that
        endlessly re-creates work.
        """
        processed = succeeded = failed = 0
        for _ in range(max_iterations):
            self.recover_expired_leases(run_id)
            self.promote_ready_tasks(run_id)
            context = self.claim_next_task(run_id)
            if context is None:
                break
            outcome = self.execute_task(context)
            processed += 1
            if outcome.success:
                succeeded += 1
            else:
                failed += 1
        else:  # pragma: no cover - defensive iteration cap
            raise TaskExecutionError(
                f"run_until_idle exceeded {max_iterations} iterations; possible task loop"
            )

        run_status = self._refresh_run_status(run_id) if run_id is not None else None
        remaining = self._remaining_open_tasks(run_id)
        return RunSummary(
            processed=processed,
            succeeded=succeeded,
            failed=failed,
            remaining=remaining,
            run_status=run_status,
        )

    def recover_expired_leases(self, run_id: int | None = None) -> list[int]:
        """Requeue tasks whose lease expired while ``LEASED`` (crashed worker).

        The open attempt is closed as ``LEASE_EXPIRED``; the task returns to
        ``READY`` if attempts remain, otherwise ``FAILED``. Returns recovered
        task ids.
        """
        now_iso = _iso(self._clock())
        recovered: list[tuple[int, str]] = []
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                f"""
                SELECT t.id AS task_id, r.project_id AS project_id, l.id AS lease_id
                  FROM tasks t
                  JOIN runs r ON r.id = t.run_id
                  JOIN task_leases l ON l.task_id = t.id
                 WHERE t.state = '{STATE_LEASED}'
                   {"AND t.run_id = ?" if run_id is not None else ""}
                   AND l.expires_at < ?
                """,
                ((run_id, now_iso) if run_id is not None else (now_iso,)),
            ).fetchall()
            for row in rows:
                task_id = int(row["task_id"])
                attempts = conn.execute(
                    "SELECT COUNT(*) AS n FROM task_attempts WHERE task_id = ?",
                    (task_id,),
                ).fetchone()["n"]
                conn.execute(
                    """
                    UPDATE task_attempts
                       SET status = ?, completed_at = ?, error_code = 'lease_expired'
                     WHERE task_id = ? AND status = ?
                    """,
                    (ATTEMPT_LEASE_EXPIRED, now_iso, task_id, ATTEMPT_RUNNING),
                )
                conn.execute("DELETE FROM task_leases WHERE task_id = ?", (task_id,))
                next_state = STATE_READY if attempts < self.max_attempts else STATE_FAILED
                conn.execute("UPDATE tasks SET state = ? WHERE id = ?", (next_state, task_id))
                self._emit_in_conn(
                    conn, task_id, "task.lease_expired", {"requeued_to": next_state}, row["project_id"]
                )
                recovered.append((task_id, next_state))
            conn.commit()
        return [task_id for task_id, _ in recovered]

    # -- internal helpers ---------------------------------------------------

    def _finalize(self, context: TaskContext, outcome: TaskOutcome, *, unrecoverable: bool = False) -> None:
        """Commit the terminal or retry transition for a just-run task."""
        now_iso = _iso(self._clock())
        task_id = context.task_id
        created_children: list[int] = []
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM task_leases WHERE task_id = ?", (task_id,))
            if outcome.success:
                conn.execute(
                    "UPDATE task_attempts SET status = ?, completed_at = ? WHERE task_id = ? AND status = ?",
                    (ATTEMPT_SUCCEEDED, now_iso, task_id, ATTEMPT_RUNNING),
                )
                conn.execute("UPDATE tasks SET state = ? WHERE id = ?", (STATE_DONE, task_id))
                for spec in outcome.follow_up:
                    child_id = conn.execute(
                        """
                        INSERT INTO tasks (run_id, task_type, state, priority, payload_json)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            context.run_id,
                            spec.task_type,
                            STATE_BLOCKED,
                            spec.priority,
                            _json(dict(spec.payload)),
                        ),
                    ).lastrowid
                    conn.execute(
                        "INSERT INTO task_dependencies (parent_task_id, child_task_id) VALUES (?, ?)",
                        (task_id, child_id),
                    )
                    created_children.append(int(child_id))
                final_state = STATE_DONE
                # State + attempt + follow-up + audit + outbox as one atomic
                # unit. No DONE task can survive without its success record.
                self._emit_in_conn(
                    conn,
                    task_id,
                    "task.succeeded",
                    {"result": dict(outcome.result), "children": created_children},
                    context.project_id,
                )
            else:
                conn.execute(
                    """
                    UPDATE task_attempts
                       SET status = ?, completed_at = ?, error_code = ?
                     WHERE task_id = ? AND status = ?
                    """,
                    (ATTEMPT_FAILED, now_iso, outcome.error_code, task_id, ATTEMPT_RUNNING),
                )
                attempts = conn.execute(
                    "SELECT COUNT(*) AS n FROM task_attempts WHERE task_id = ?",
                    (task_id,),
                ).fetchone()["n"]
                retryable = (not unrecoverable) and attempts < self.max_attempts
                final_state = STATE_READY if retryable else STATE_FAILED
                conn.execute("UPDATE tasks SET state = ? WHERE id = ?", (final_state, task_id))
                self._emit_in_conn(
                    conn,
                    task_id,
                    "task.failed" if final_state == STATE_FAILED else "task.retry_scheduled",
                    {
                        "error_code": outcome.error_code,
                        "error_message": outcome.error_message,
                        "next_state": final_state,
                        "attempt": context.attempt_number,
                    },
                    context.project_id,
                )
            conn.commit()

        # Promotion of just-created children runs in its own atomic transaction
        # (see promote_ready_tasks); it is idempotent and safely re-derivable if
        # a crash happens after the finalize commit but before promotion.
        if outcome.success and created_children:
            self.promote_ready_tasks(context.run_id)

    def _emit_in_conn(self, conn, task_id: int, event_type: str, payload: dict, project_id: str) -> None:
        """Write the audit and outbox rows for a transition on an open connection.

        This deliberately takes the caller's connection and does **not** commit:
        the audit and outbox writes must land in the same transaction as the
        state change that produced them, so a transition and its evidence are
        durable together or not at all.
        """
        body = dict(payload)
        body["task_id"] = task_id
        payload_json = _json(body)
        conn.execute(
            """
            INSERT INTO outbox_events (aggregate_type, aggregate_id, event_type, payload_json)
            VALUES ('task', ?, ?, ?)
            """,
            (str(task_id), event_type, payload_json),
        )
        conn.execute(
            """
            INSERT INTO audit_events (
                project_id, actor_type, actor_id, event_type, entity_type, entity_id, payload_json
            ) VALUES (?, 'system', ?, ?, 'task', ?, ?)
            """,
            (project_id, self.worker_id, event_type, str(task_id), payload_json),
        )

    def _remaining_open_tasks(self, run_id: int | None) -> int:
        clause = "AND run_id = ?" if run_id is not None else ""
        params = (run_id,) if run_id is not None else ()
        row = self.db.fetchone(
            f"SELECT COUNT(*) AS n FROM tasks WHERE state NOT IN ('{STATE_DONE}', '{STATE_FAILED}') {clause}",
            params,
        )
        return int(row["n"]) if row else 0

    def _refresh_run_status(self, run_id: int) -> str:
        """Derive and persist the run status from its tasks. Returns the status."""
        rows = self.db.fetchall("SELECT state, COUNT(*) AS n FROM tasks WHERE run_id = ? GROUP BY state", (run_id,))
        counts = {row["state"]: int(row["n"]) for row in rows}
        total = sum(counts.values())
        done = counts.get(STATE_DONE, 0)
        failed = counts.get(STATE_FAILED, 0)
        open_tasks = total - done - failed

        if total == 0 or done == total:
            status = RUN_COMPLETED
        elif open_tasks > 0:
            # Work remains; if nothing is runnable it is blocked, else running.
            status = RUN_BLOCKED if self._remaining_open_tasks(run_id) and not self._has_runnable(run_id) else RUN_RUNNING
        elif failed:
            status = RUN_FAILED
        else:  # pragma: no cover - defensive
            status = RUN_RUNNING

        completed_at = "CURRENT_TIMESTAMP" if status in (RUN_COMPLETED, RUN_FAILED) else "completed_at"
        self.db.execute(
            f"UPDATE runs SET status = ?, completed_at = {completed_at} WHERE id = ?",
            (status, run_id),
        )
        return status

    def _has_runnable(self, run_id: int) -> bool:
        row = self.db.fetchone(
            f"""
            SELECT 1 FROM tasks t
             WHERE t.run_id = ? AND t.state = '{STATE_READY}'
               AND NOT EXISTS (
                   SELECT 1 FROM task_dependencies d
                     JOIN tasks p ON p.id = d.parent_task_id
                    WHERE d.child_task_id = t.id AND p.state <> '{STATE_DONE}'
               )
             LIMIT 1
            """,
            (run_id,),
        )
        return row is not None


def _coerce_outcome(raw: "TaskOutcome | Mapping[str, object] | None") -> TaskOutcome:
    if raw is None:
        return TaskOutcome.ok()
    if isinstance(raw, TaskOutcome):
        return raw
    if isinstance(raw, Mapping):
        return TaskOutcome.ok(dict(raw))
    raise TaskExecutionError(
        f"Handler returned unsupported type {type(raw).__name__}; expected TaskOutcome, Mapping, or None"
    )
