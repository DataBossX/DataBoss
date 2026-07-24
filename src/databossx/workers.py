"""Concrete intake workers for the ``title_project_intake`` workflow.

These are the handlers the execution engine dispatches for the tasks seeded by
:func:`databossx.orchestrator.seed_project_intake_run`. Each wraps the
evidence-grounded, non-destructive intake operations in :mod:`databossx.intake`
so the durable task graph performs real work instead of abstract placeholders:

* ``REGISTER_SOURCES`` — register each configured source root as read-only.
* ``INVENTORY_AND_LOCK`` — inventory every enabled source connection for the
  project (hashing bytes into the content-addressed vault, recording custody).
* ``REGISTER_TEMPLATE`` — register the approved workbook template, if configured.

Execution model: the orchestrator guarantees a task runs to a committed outcome
under a single-writer lease, but delivery is **at-least-once** — a task whose
first attempt fails partway (or whose lease is recovered) is retried. Each
intake operation is therefore **idempotent**: bytes are copied into the
content-addressed vault (existing hashes skipped), and ``source_connection`` /
``asset`` / ``asset_version`` / ``source_snapshot`` / ``workbook_template`` rows
are created with select-or-return-existing and content-stable snapshot keys, so
a retry after a committed side effect resumes cleanly instead of duplicating
rows or hitting a ``UNIQUE`` constraint. The operations also **fail closed**: a
missing/unreadable/empty source root raises rather than recording a
falsely-COMPLETE inventory (see :class:`databossx.intake.SourceValidationError`;
pass ``allow_empty`` to record an intentional empty snapshot).
"""

from __future__ import annotations

from pathlib import Path

from .config import DataBossConfig
from .database import DataBossDatabase
from .executor import Orchestrator, RunSummary, TaskContext, TaskOutcome, WorkerRegistry
from .intake import (
    create_project,
    inventory_source,
    register_source_connection,
    register_workbook_template,
)
from .models import ProjectRecord


def register_intake_workers(registry: WorkerRegistry, config: DataBossConfig) -> WorkerRegistry:
    """Register the three ``title_project_intake`` handlers on ``registry``.

    Returns the same registry for convenient chaining.
    """

    @registry.handler("REGISTER_SOURCES")
    def _register_sources(ctx: TaskContext) -> TaskOutcome:
        roots = ctx.payload.get("source_roots") or []
        if not isinstance(roots, list):
            return TaskOutcome.fail("bad_payload", "source_roots must be a list of paths")
        connection_ids = [
            register_source_connection(config, ctx.project_id, root).source_connection_id
            for root in roots
        ]
        return TaskOutcome.ok({"source_connection_ids": connection_ids, "count": len(connection_ids)})

    @registry.handler("INVENTORY_AND_LOCK")
    def _inventory_and_lock(ctx: TaskContext) -> TaskOutcome:
        db = DataBossDatabase(config.project_db_path(ctx.project_id))
        rows = db.fetchall(
            "SELECT id FROM source_connections WHERE project_id = ? AND enabled = 1 ORDER BY id",
            (ctx.project_id,),
        )
        snapshots: list[int] = []
        total_items = 0
        total_duplicates = 0
        for row in rows:
            result = inventory_source(config, ctx.project_id, int(row["id"]))
            snapshots.append(result.source_snapshot_id)
            total_items += result.item_count
            total_duplicates += result.duplicate_count
        return TaskOutcome.ok(
            {
                "source_snapshot_ids": snapshots,
                "item_count": total_items,
                "duplicate_count": total_duplicates,
            }
        )

    @registry.handler("REGISTER_TEMPLATE")
    def _register_template(ctx: TaskContext) -> TaskOutcome:
        template_path = ctx.payload.get("template_path")
        if not template_path:
            return TaskOutcome.ok({"skipped": True, "reason": "no template configured"})
        workbook_template_id = register_workbook_template(config, ctx.project_id, template_path)
        return TaskOutcome.ok({"workbook_template_id": workbook_template_id})

    return registry


def run_project_intake(
    config: DataBossConfig,
    *,
    name: str,
    jurisdiction_code: str,
    source_roots: list[str],
    template_path: str | Path | None = None,
    policy_profile: str = "default",
    project_id: str | None = None,
    worker_id: str = "orchestrator-1",
) -> tuple[ProjectRecord, RunSummary]:
    """Create a project and drive its seeded intake run to completion.

    Ties the pieces together: seed a project whose intake tasks carry the given
    inputs, register the intake workers, and run the durable task graph until it
    is idle. Returns the project record and the run summary (``run_status`` is
    ``COMPLETED`` on success).
    """
    project = create_project(
        config,
        name=name,
        jurisdiction_code=jurisdiction_code,
        policy_profile=policy_profile,
        project_id=project_id,
        source_roots=source_roots,
        template_path=template_path,
    )
    db = DataBossDatabase(config.project_db_path(project.project_id))
    registry = register_intake_workers(WorkerRegistry(), config)
    run_row = db.fetchone(
        "SELECT id FROM runs WHERE project_id = ? ORDER BY id LIMIT 1", (project.project_id,)
    )
    if run_row is None:  # pragma: no cover - create_project always seeds a run
        raise RuntimeError(f"No intake run seeded for project {project.project_id}")
    summary = Orchestrator(db, registry, worker_id=worker_id).run_until_idle(int(run_row["id"]))
    return project, summary
