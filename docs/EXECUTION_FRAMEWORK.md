# DataBossX Execution Framework

The execution framework is the runtime that drives the DataBossX durable task
graph forward under the non-negotiable rules in
[`DATABOSSX_OS_BLUEPRINT.md`](DATABOSSX_OS_BLUEPRINT.md). It lives in
`src/databossx/executor.py` and is stdlib-only, deterministic, and fully
covered by `tests/test_databossx_executor.py`.

## What it provides

| Capability | Guarantee |
| --- | --- |
| **One writer** | Only the `Orchestrator` commits task/run state transitions, leases, attempts, and downstream tasks. Workers are pure functions of a `TaskContext` and never write state. |
| **Durable task graph** | Tasks move through `BLOCKED → READY → LEASED → DONE`/`FAILED`. Dependencies gate claims; a task is claimable only when every parent is `DONE`. |
| **Atomic leasing** | `claim_next_task` selects the highest-priority runnable task and leases it inside a single `BEGIN IMMEDIATE` transaction, recording a `task_leases` row and a `RUNNING` `task_attempts` row. |
| **Bounded retries** | A worker exception or `TaskOutcome.fail(...)` reschedules the task to `READY` until `max_attempts` is exhausted, then `FAILED`. A missing handler fails once, unrecoverably (`no_handler`). |
| **Lease recovery** | `recover_expired_leases` requeues tasks whose lease expired while still `LEASED` (a crashed worker), closing the open attempt as `LEASE_EXPIRED`. Time is injected via a `clock` callable so this is testable without sleeping. |
| **Ownership guard** | `_finalize` commits only if *this* attempt is still `RUNNING`. If the lease expired and the task was recovered/re-leased, the late finalize matches zero rows, rolls back, and the outcome is dropped — a slow or crashed worker cannot double-apply a side effect or clobber a fresh lease. |
| **Follow-up work** | A handler may return `follow_up=[FollowUpTask(...)]`; the orchestrator — as the single writer — creates each child task and wires the dependency edge to the just-completed parent. |
| **Atomic transitions** | The task-state change, the attempt/lease writes, and the paired append-only `audit_events` + reliable `outbox_events` rows are committed in **one** SQLite transaction. A crash before `COMMIT` rolls back the entire transition — no state change can survive without its audit and outbox record, and none can leak without its state change. Proven by failure-injection tests. |

## Minimal usage

```python
from databossx import (
    DataBossConfig, DataBossDatabase, Orchestrator, WorkerRegistry, TaskOutcome,
    create_project,
)

config = DataBossConfig.from_repo_root("/path/to/repo")
project = create_project(config, name="Section 32", jurisdiction_code="OK")
db = DataBossDatabase(config.project_db_path(project.project_id))

registry = WorkerRegistry()

@registry.handler("REGISTER_SOURCES")
def register_sources(ctx):
    # ... do least-privilege work using ctx.payload ...
    return TaskOutcome.ok({"registered": True})

run_id = db.fetchone("SELECT id FROM runs ORDER BY id LIMIT 1")["id"]
summary = Orchestrator(db, registry).run_until_idle(run_id)
# summary.run_status in {"COMPLETED", "BLOCKED", "FAILED", "RUNNING"}
```

`create_project` seeds a `title_project_intake` run with `REGISTER_SOURCES`,
`INVENTORY_AND_LOCK` (blocked on `REGISTER_SOURCES`), and `REGISTER_TEMPLATE`.
Register a handler per `task_type` and call `run_until_idle`.

## Running the real intake workflow

`databossx.workers` provides concrete handlers wrapping the intake operations,
plus a one-call runner:

```python
from databossx import DataBossConfig, run_project_intake

config = DataBossConfig.from_repo_root("/path/to/repo")
project, summary = run_project_intake(
    config,
    name="Section 32",
    jurisdiction_code="OK",
    source_roots=["/path/to/source_docs"],   # read-only; bytes are hashed + vaulted
    template_path="/path/to/control_template.xlsx",
)
assert summary.run_status == "COMPLETED"
```

Or from the command line:

```bash
python -m databossx run-intake --repo-root . --name "Section 32" \
    --jurisdiction OK --source /path/to/source_docs --template /path/to/template.xlsx
```

The CLI prints a JSON run report and exits non-zero if the run did not complete.

**Delivery is at-least-once.** A task whose first attempt fails partway is
retried, so handlers should be idempotent. The intake operations copy bytes
idempotently (the content-addressed vault skips existing hashes) but append new
bookkeeping rows per run; run a single attempt per task where exactly-once
bookkeeping matters.

## Worker contract

A handler receives a read-only `TaskContext` (`task_id`, `run_id`,
`project_id`, `task_type`, `payload`, `attempt_number`, `worker_id`) and returns
one of:

- `TaskOutcome.ok(result, follow_up=[...])` — success.
- `TaskOutcome.fail(error_code, error_message)` — retryable failure.
- a plain `dict` — treated as a successful result payload.
- `None` — success with an empty result.
- raising an exception — caught and treated as a retryable failure.

Handlers must be idempotent: a recovered lease or a retry can run the same task
body more than once, and only the orchestrator's committed state is
authoritative.

## Run status semantics

`run_until_idle` refreshes and persists the run status:

- `COMPLETED` — every task is `DONE`.
- `BLOCKED` — open tasks remain but none are runnable (e.g. a parent `FAILED`).
- `FAILED` — work stopped with failures and nothing runnable remains.
- `RUNNING` — runnable work remains (only seen when an iteration cap is hit).
