from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from databossx.config import DataBossConfig
from databossx.database import DataBossDatabase
from databossx.executor import (
    STATE_BLOCKED,
    STATE_DONE,
    STATE_FAILED,
    STATE_READY,
    FollowUpTask,
    Orchestrator,
    TaskContext,
    TaskOutcome,
    WorkerRegistry,
)
from databossx.intake import create_project


class FakeClock:
    """Deterministic, advanceable clock for lease-expiry tests."""

    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now = self.now + timedelta(seconds=seconds)


def _project(tmp_path) -> tuple[DataBossConfig, DataBossDatabase, str]:
    config = DataBossConfig.from_repo_root(tmp_path / "repo")
    project = create_project(config, name="Section 32", jurisdiction_code="OK", project_id="proj_exec")
    db = DataBossDatabase(config.project_db_path(project.project_id))
    return config, db, project.project_id


def _task_states(db: DataBossDatabase) -> dict[str, str]:
    rows = db.fetchall("SELECT task_type, state FROM tasks ORDER BY id")
    return {row["task_type"]: row["state"] for row in rows}


def _run_id(db: DataBossDatabase) -> int:
    return int(db.fetchone("SELECT id FROM runs ORDER BY id LIMIT 1")["id"])


def test_seed_creates_blocked_task_with_dependency(tmp_path):
    _, db, _ = _project(tmp_path)
    states = _task_states(db)
    assert states["REGISTER_SOURCES"] == STATE_READY
    assert states["REGISTER_TEMPLATE"] == STATE_READY
    assert states["INVENTORY_AND_LOCK"] == STATE_BLOCKED
    dep = db.fetchone("SELECT COUNT(*) AS n FROM task_dependencies")
    assert dep["n"] == 1


def test_run_until_idle_completes_all_tasks_in_dependency_order(tmp_path):
    _, db, project_id = _project(tmp_path)
    registry = WorkerRegistry()
    executed: list[str] = []

    def make(name):
        def _handler(ctx: TaskContext) -> TaskOutcome:
            executed.append(ctx.task_type)
            return TaskOutcome.ok({"ran": name})

        return _handler

    for task_type in ("REGISTER_SOURCES", "INVENTORY_AND_LOCK", "REGISTER_TEMPLATE"):
        registry.register(task_type, make(task_type))

    run_id = _run_id(db)
    orch = Orchestrator(db, registry)
    summary = orch.run_until_idle(run_id)

    assert summary.processed == 3
    assert summary.succeeded == 3
    assert summary.failed == 0
    assert summary.remaining == 0
    assert summary.run_status == "COMPLETED"
    assert set(_task_states(db).values()) == {STATE_DONE}
    # The dependent task must run strictly after its parent.
    assert executed.index("REGISTER_SOURCES") < executed.index("INVENTORY_AND_LOCK")


def test_dependency_gates_claim_until_parent_done(tmp_path):
    _, db, _ = _project(tmp_path)
    registry = WorkerRegistry()
    registry.register("REGISTER_SOURCES", lambda ctx: TaskOutcome.ok())
    registry.register("REGISTER_TEMPLATE", lambda ctx: TaskOutcome.ok())
    run_id = _run_id(db)
    orch = Orchestrator(db, registry)

    # Only the two READY roots are claimable; the BLOCKED task never is until promoted.
    claimed = []
    for _ in range(2):
        ctx = orch.claim_next_task(run_id)
        claimed.append(ctx.task_type)
        orch.execute_task(ctx)
    assert set(claimed) == {"REGISTER_SOURCES", "REGISTER_TEMPLATE"}

    # INVENTORY_AND_LOCK is now promotable because REGISTER_SOURCES is DONE.
    promoted = orch.promote_ready_tasks(run_id)
    assert len(promoted) == 1
    ctx = orch.claim_next_task(run_id)
    assert ctx.task_type == "INVENTORY_AND_LOCK"


def test_failure_retries_until_budget_exhausted(tmp_path):
    _, db, _ = _project(tmp_path)
    registry = WorkerRegistry()
    calls = {"n": 0}

    def flaky(ctx: TaskContext) -> TaskOutcome:
        calls["n"] += 1
        raise RuntimeError("boom")

    registry.register("REGISTER_SOURCES", flaky)
    registry.register("REGISTER_TEMPLATE", lambda ctx: TaskOutcome.ok())
    run_id = _run_id(db)
    orch = Orchestrator(db, registry, max_attempts=3)

    # Drive only the flaky root by claiming it explicitly three times.
    for expected_attempt in (1, 2, 3):
        orch.promote_ready_tasks(run_id)
        ctx = None
        while True:
            ctx = orch.claim_next_task(run_id)
            if ctx is None:
                break
            if ctx.task_type == "REGISTER_SOURCES":
                break
            orch.execute_task(ctx)  # clear the healthy sibling
        assert ctx is not None and ctx.attempt_number == expected_attempt
        orch.execute_task(ctx)

    assert calls["n"] == 3
    state = db.fetchone("SELECT state FROM tasks WHERE task_type = 'REGISTER_SOURCES'")["state"]
    assert state == STATE_FAILED
    attempts = db.fetchall("SELECT status FROM task_attempts")
    assert sum(1 for a in attempts if a["status"] == "FAILED") == 3


def test_failure_then_success_recovers(tmp_path):
    _, db, _ = _project(tmp_path)
    registry = WorkerRegistry()
    state = {"fail_once": True}

    def sometimes(ctx: TaskContext) -> TaskOutcome:
        if state["fail_once"]:
            state["fail_once"] = False
            return TaskOutcome.fail("transient", "first attempt fails")
        return TaskOutcome.ok({"ok": True})

    registry.register("REGISTER_SOURCES", sometimes)
    registry.register("INVENTORY_AND_LOCK", lambda ctx: TaskOutcome.ok())
    registry.register("REGISTER_TEMPLATE", lambda ctx: TaskOutcome.ok())
    run_id = _run_id(db)
    orch = Orchestrator(db, registry, max_attempts=3)

    summary = orch.run_until_idle(run_id)
    assert summary.run_status == "COMPLETED"
    src_state = db.fetchone("SELECT state FROM tasks WHERE task_type = 'REGISTER_SOURCES'")["state"]
    assert src_state == STATE_DONE
    attempts = db.fetchall(
        "SELECT status FROM task_attempts a JOIN tasks t ON t.id = a.task_id WHERE t.task_type = 'REGISTER_SOURCES'"
    )
    statuses = sorted(a["status"] for a in attempts)
    assert statuses == ["FAILED", "SUCCEEDED"]


def test_no_handler_fails_task_immediately_without_retry(tmp_path):
    _, db, _ = _project(tmp_path)
    registry = WorkerRegistry()  # nothing registered
    run_id = _run_id(db)
    orch = Orchestrator(db, registry, max_attempts=3)

    ctx = orch.claim_next_task(run_id)
    outcome = orch.execute_task(ctx)
    assert not outcome.success
    assert outcome.error_code == "no_handler"
    state = db.fetchone("SELECT state FROM tasks WHERE id = ?", (ctx.task_id,))["state"]
    assert state == STATE_FAILED
    # Unrecoverable: exactly one attempt, no retry.
    n = db.fetchone("SELECT COUNT(*) AS n FROM task_attempts WHERE task_id = ?", (ctx.task_id,))["n"]
    assert n == 1


def test_expired_lease_is_recovered_and_requeued(tmp_path):
    _, db, _ = _project(tmp_path)
    registry = WorkerRegistry()
    clock = FakeClock()
    orch = Orchestrator(db, registry, lease_seconds=60, max_attempts=3, clock=clock)
    run_id = _run_id(db)

    ctx = orch.claim_next_task(run_id)
    assert ctx is not None
    # Simulate a crashed worker: lease expires with the task still LEASED.
    clock.advance(120)
    recovered = orch.recover_expired_leases(run_id)
    assert recovered == [ctx.task_id]
    state = db.fetchone("SELECT state FROM tasks WHERE id = ?", (ctx.task_id,))["state"]
    assert state == STATE_READY
    leases = db.fetchone("SELECT COUNT(*) AS n FROM task_leases WHERE task_id = ?", (ctx.task_id,))["n"]
    assert leases == 0
    expired = db.fetchone(
        "SELECT COUNT(*) AS n FROM task_attempts WHERE task_id = ? AND status = 'LEASE_EXPIRED'",
        (ctx.task_id,),
    )["n"]
    assert expired == 1


def test_follow_up_tasks_are_created_and_wired(tmp_path):
    _, db, _ = _project(tmp_path)
    registry = WorkerRegistry()

    def spawner(ctx: TaskContext) -> TaskOutcome:
        return TaskOutcome.ok(follow_up=[FollowUpTask("RENDER_PAGES", {"stage": "C"})])

    registry.register("REGISTER_SOURCES", spawner)
    registry.register("INVENTORY_AND_LOCK", lambda ctx: TaskOutcome.ok())
    registry.register("REGISTER_TEMPLATE", lambda ctx: TaskOutcome.ok())
    child_ran = {"ok": False}
    registry.register("RENDER_PAGES", lambda ctx: child_ran.__setitem__("ok", True) or TaskOutcome.ok())

    run_id = _run_id(db)
    orch = Orchestrator(db, registry)
    summary = orch.run_until_idle(run_id)

    assert child_ran["ok"] is True
    assert summary.run_status == "COMPLETED"
    child = db.fetchone("SELECT id, state FROM tasks WHERE task_type = 'RENDER_PAGES'")
    assert child["state"] == STATE_DONE
    dep = db.fetchone(
        "SELECT COUNT(*) AS n FROM task_dependencies WHERE child_task_id = ?", (child["id"],)
    )["n"]
    assert dep == 1


def test_every_transition_emits_audit_and_outbox(tmp_path):
    _, db, project_id = _project(tmp_path)
    registry = WorkerRegistry()
    for task_type in ("REGISTER_SOURCES", "INVENTORY_AND_LOCK", "REGISTER_TEMPLATE"):
        registry.register(task_type, lambda ctx: TaskOutcome.ok())
    run_id = _run_id(db)
    orch = Orchestrator(db, registry)
    orch.run_until_idle(run_id)

    outbox = db.fetchall("SELECT event_type FROM outbox_events WHERE aggregate_type = 'task'")
    event_types = {row["event_type"] for row in outbox}
    assert {"task.leased", "task.succeeded"} <= event_types
    # Outbox and task-audit rows are paired one-to-one per emission.
    task_audits = db.fetchone(
        "SELECT COUNT(*) AS n FROM audit_events WHERE entity_type = 'task' AND project_id = ?",
        (project_id,),
    )["n"]
    assert task_audits == len(outbox)


def test_blocked_run_status_when_parent_fails(tmp_path):
    _, db, _ = _project(tmp_path)
    registry = WorkerRegistry()
    registry.register("REGISTER_SOURCES", lambda ctx: TaskOutcome.fail("hard", "no recovery"))
    registry.register("REGISTER_TEMPLATE", lambda ctx: TaskOutcome.ok())
    # INVENTORY_AND_LOCK depends on the failing REGISTER_SOURCES, so it can never run.
    run_id = _run_id(db)
    orch = Orchestrator(db, registry, max_attempts=1)
    summary = orch.run_until_idle(run_id)

    assert summary.remaining == 1  # INVENTORY_AND_LOCK stranded (parent FAILED)
    assert summary.run_status == "BLOCKED"
    states = _task_states(db)
    assert states["REGISTER_SOURCES"] == STATE_FAILED
    assert states["INVENTORY_AND_LOCK"] == STATE_BLOCKED
    assert states["REGISTER_TEMPLATE"] == STATE_DONE


def test_handler_dict_return_is_treated_as_success(tmp_path):
    _, db, _ = _project(tmp_path)
    registry = WorkerRegistry()
    registry.register("REGISTER_SOURCES", lambda ctx: {"note": "plain dict"})
    run_id = _run_id(db)
    orch = Orchestrator(db, registry)
    ctx = orch.claim_next_task(run_id)
    assert ctx.task_type == "REGISTER_SOURCES"
    outcome = orch.execute_task(ctx)
    assert outcome.success is True
    assert outcome.result == {"note": "plain dict"}


def test_registry_rejects_non_callable():
    registry = WorkerRegistry()
    with pytest.raises(TypeError):
        registry.register("X", 42)  # type: ignore[arg-type]


def test_orchestrator_validates_construction(tmp_path):
    _, db, _ = _project(tmp_path)
    with pytest.raises(ValueError):
        Orchestrator(db, WorkerRegistry(), max_attempts=0)
    with pytest.raises(ValueError):
        Orchestrator(db, WorkerRegistry(), lease_seconds=0)


def _counts(db: DataBossDatabase) -> dict[str, int]:
    return {
        "outbox": db.fetchone("SELECT COUNT(*) AS n FROM outbox_events")["n"],
        "audit_task": db.fetchone(
            "SELECT COUNT(*) AS n FROM audit_events WHERE entity_type = 'task'"
        )["n"],
        "attempts": db.fetchone("SELECT COUNT(*) AS n FROM task_attempts")["n"],
        "leases": db.fetchone("SELECT COUNT(*) AS n FROM task_leases")["n"],
    }


def _explode_emit(orch: Orchestrator, on_event: str):
    """Wrap _emit_in_conn so it raises for one event type, after doing the
    in-transaction inserts, to prove the whole transaction rolls back."""
    original = orch._emit_in_conn

    def _boom(conn, task_id, event_type, payload, project_id):
        original(conn, task_id, event_type, payload, project_id)
        if event_type == on_event:
            raise RuntimeError(f"injected crash during {event_type}")

    orch._emit_in_conn = _boom  # type: ignore[assignment]


def test_claim_transition_is_atomic_under_injected_crash(tmp_path):
    _, db, _ = _project(tmp_path)
    orch = Orchestrator(db, WorkerRegistry())
    before = _counts(db)
    states_before = _task_states(db)

    _explode_emit(orch, "task.leased")
    with pytest.raises(RuntimeError, match="injected crash during task.leased"):
        orch.claim_next_task(_run_id(db))

    # Nothing from the failed lease transaction survived: no state flip to
    # LEASED, no attempt, no lease row, no audit, no outbox.
    assert _task_states(db) == states_before
    assert _counts(db) == before
    assert db.fetchone("SELECT COUNT(*) AS n FROM tasks WHERE state = 'LEASED'")["n"] == 0


def test_success_transition_is_atomic_under_injected_crash(tmp_path):
    _, db, _ = _project(tmp_path)
    registry = WorkerRegistry()
    registry.register(
        "REGISTER_SOURCES",
        lambda ctx: TaskOutcome.ok(follow_up=[FollowUpTask("RENDER_PAGES", {"stage": "C"})]),
    )
    orch = Orchestrator(db, registry)
    run_id = _run_id(db)

    ctx = orch.claim_next_task(run_id)
    assert ctx.task_type == "REGISTER_SOURCES"
    after_claim = _counts(db)

    _explode_emit(orch, "task.succeeded")
    with pytest.raises(RuntimeError, match="injected crash during task.succeeded"):
        orch.execute_task(ctx)

    # The success transition (DONE + succeeded attempt + follow-up child +
    # dependency + audit + outbox) is all-or-nothing. It rolled back entirely:
    task = db.fetchone("SELECT state FROM tasks WHERE id = ?", (ctx.task_id,))
    assert task["state"] == "LEASED"  # still leased, not DONE
    assert db.fetchone("SELECT COUNT(*) AS n FROM tasks WHERE task_type = 'RENDER_PAGES'")["n"] == 0
    assert db.fetchone("SELECT COUNT(*) AS n FROM task_dependencies")["n"] == 1  # only the seed edge
    assert (
        db.fetchone(
            "SELECT COUNT(*) AS n FROM task_attempts WHERE task_id = ? AND status = 'SUCCEEDED'",
            (ctx.task_id,),
        )["n"]
        == 0
    )
    # Outbox/audit unchanged since the claim; no partial success record leaked.
    assert _counts(db)["outbox"] == after_claim["outbox"]
    assert _counts(db)["audit_task"] == after_claim["audit_task"]
    # The still-open RUNNING attempt from the claim remains (its lease too),
    # so lease recovery can later requeue the task cleanly.
    assert (
        db.fetchone(
            "SELECT COUNT(*) AS n FROM task_attempts WHERE task_id = ? AND status = 'RUNNING'",
            (ctx.task_id,),
        )["n"]
        == 1
    )


def test_failure_transition_is_atomic_under_injected_crash(tmp_path):
    _, db, _ = _project(tmp_path)
    registry = WorkerRegistry()
    registry.register("REGISTER_SOURCES", lambda ctx: TaskOutcome.fail("boom", "worker failed"))
    orch = Orchestrator(db, registry, max_attempts=3)
    run_id = _run_id(db)

    ctx = orch.claim_next_task(run_id)
    after_claim = _counts(db)

    _explode_emit(orch, "task.retry_scheduled")
    with pytest.raises(RuntimeError, match="injected crash during task.retry_scheduled"):
        orch.execute_task(ctx)

    # The failed-attempt transition rolled back: task not requeued to READY,
    # no FAILED attempt recorded, no audit/outbox leaked.
    assert db.fetchone("SELECT state FROM tasks WHERE id = ?", (ctx.task_id,))["state"] == "LEASED"
    assert (
        db.fetchone(
            "SELECT COUNT(*) AS n FROM task_attempts WHERE task_id = ? AND status = 'FAILED'",
            (ctx.task_id,),
        )["n"]
        == 0
    )
    assert _counts(db)["outbox"] == after_claim["outbox"]
    assert _counts(db)["audit_task"] == after_claim["audit_task"]


def test_lease_recovery_transition_is_atomic_under_injected_crash(tmp_path):
    _, db, _ = _project(tmp_path)
    clock = FakeClock()
    orch = Orchestrator(db, WorkerRegistry(), lease_seconds=60, clock=clock)
    run_id = _run_id(db)
    ctx = orch.claim_next_task(run_id)
    clock.advance(120)
    after_claim = _counts(db)

    _explode_emit(orch, "task.lease_expired")
    with pytest.raises(RuntimeError, match="injected crash during task.lease_expired"):
        orch.recover_expired_leases(run_id)

    # Recovery is atomic: the lease still exists, the task is still LEASED, the
    # attempt is still RUNNING (not LEASE_EXPIRED), and no event leaked.
    assert db.fetchone("SELECT state FROM tasks WHERE id = ?", (ctx.task_id,))["state"] == "LEASED"
    assert db.fetchone("SELECT COUNT(*) AS n FROM task_leases WHERE task_id = ?", (ctx.task_id,))["n"] == 1
    assert (
        db.fetchone(
            "SELECT COUNT(*) AS n FROM task_attempts WHERE task_id = ? AND status = 'LEASE_EXPIRED'",
            (ctx.task_id,),
        )["n"]
        == 0
    )
    assert _counts(db)["outbox"] == after_claim["outbox"]
    assert _counts(db)["audit_task"] == after_claim["audit_task"]

    # And after removing the fault, a clean recovery fully succeeds.
    orch._emit_in_conn = Orchestrator._emit_in_conn.__get__(orch)  # restore
    recovered = orch.recover_expired_leases(run_id)
    assert recovered == [ctx.task_id]
    assert db.fetchone("SELECT state FROM tasks WHERE id = ?", (ctx.task_id,))["state"] == STATE_READY


def test_audit_and_outbox_are_paired_one_to_one_per_transition(tmp_path):
    _, db, project_id = _project(tmp_path)
    registry = WorkerRegistry()
    for task_type in ("REGISTER_SOURCES", "INVENTORY_AND_LOCK", "REGISTER_TEMPLATE"):
        registry.register(task_type, lambda ctx: TaskOutcome.ok())
    orch = Orchestrator(db, registry)
    orch.run_until_idle(_run_id(db))

    # Every outbox row has exactly one matching task audit row (same event on
    # the same task), because both are written in the same transaction.
    outbox = db.fetchall("SELECT event_type, aggregate_id FROM outbox_events WHERE aggregate_type = 'task'")
    for row in outbox:
        n = db.fetchone(
            """
            SELECT COUNT(*) AS n FROM audit_events
             WHERE entity_type = 'task' AND event_type = ? AND entity_id = ? AND project_id = ?
            """,
            (row["event_type"], row["aggregate_id"], project_id),
        )["n"]
        assert n == 1
    total_audit = db.fetchone(
        "SELECT COUNT(*) AS n FROM audit_events WHERE entity_type = 'task' AND project_id = ?",
        (project_id,),
    )["n"]
    assert total_audit == len(outbox)


def test_context_payload_round_trips_json(tmp_path):
    _, db, _ = _project(tmp_path)
    registry = WorkerRegistry()
    seen = {}
    registry.register("REGISTER_SOURCES", lambda ctx: seen.update(ctx.payload) or TaskOutcome.ok())
    run_id = _run_id(db)
    orch = Orchestrator(db, registry)
    ctx = orch.claim_next_task(run_id)
    orch.execute_task(ctx)
    assert seen["stage"] == "A"
    assert "description" in seen
