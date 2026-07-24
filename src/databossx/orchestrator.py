from __future__ import annotations

import contextlib
import json

from .database import DataBossDatabase


def seed_project_intake_run(
    db: DataBossDatabase,
    project_id: str,
    *,
    source_roots: list[str] | None = None,
    template_path: str | None = None,
) -> tuple[int, list[int]]:
    """Seed the title-intake run and its task graph in one transaction.

    The workflow row, run row, all task rows, the dependency edge, and the seed
    audit event are committed atomically. A crash before ``COMMIT`` leaves no
    partial run — critically, the graph can never persist with a task but a
    missing dependency edge, which would let ``INVENTORY_AND_LOCK`` run before
    ``REGISTER_SOURCES`` (the dependency gate is a ``NOT EXISTS`` over the edge,
    so a missing edge reads as "no unmet parents").

    Optional ``source_roots`` and ``template_path`` are embedded in the relevant
    task payloads so registered workers have the inputs they need to run the
    workflow for real (see ``databossx.workers``).
    """
    workflow_name = "title_project_intake"
    # (task_type, initial_state, priority, payload). INVENTORY_AND_LOCK cannot
    # start until sources are registered, so it seeds BLOCKED with a dependency
    # edge and the orchestrator promotes it once REGISTER_SOURCES is DONE.
    task_specs = [
        (
            "REGISTER_SOURCES",
            "READY",
            100,
            {
                "stage": "A",
                "description": "Register source roots as read-only",
                "source_roots": list(source_roots or []),
            },
        ),
        ("INVENTORY_AND_LOCK", "BLOCKED", 100, {"stage": "B", "description": "Inventory and evidence lock"}),
        (
            "REGISTER_TEMPLATE",
            "READY",
            100,
            {
                "stage": "A",
                "description": "Register approved workbook template",
                "template_path": template_path,
            },
        ),
    ]

    with contextlib.closing(db.connect()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT OR IGNORE INTO workflow_definitions (name, version) VALUES (?, ?)",
                (workflow_name, "1.0.0"),
            )
            workflow_id = int(
                conn.execute(
                    "SELECT id FROM workflow_definitions WHERE name = ? ORDER BY id DESC LIMIT 1",
                    (workflow_name,),
                ).fetchone()["id"]
            )
            run_id = conn.execute(
                "INSERT INTO runs (project_id, workflow_id, status) VALUES (?, ?, ?)",
                (project_id, workflow_id, "PLANNED"),
            ).lastrowid
            task_ids: list[int] = []
            for task_type, state, priority, payload in task_specs:
                task_ids.append(
                    conn.execute(
                        """
                        INSERT INTO tasks (run_id, task_type, state, priority, payload_json)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (run_id, task_type, state, priority, json.dumps(payload, sort_keys=True)),
                    ).lastrowid
                )
            # REGISTER_SOURCES (index 0) blocks INVENTORY_AND_LOCK (index 1).
            conn.execute(
                "INSERT INTO task_dependencies (parent_task_id, child_task_id) VALUES (?, ?)",
                (task_ids[0], task_ids[1]),
            )
            conn.execute(
                """
                INSERT INTO audit_events (
                    project_id, actor_type, actor_id, event_type, entity_type, entity_id, payload_json
                ) VALUES (?, 'system', 'databossx', 'run.seeded', 'run', ?, ?)
                """,
                (
                    project_id,
                    str(run_id),
                    json.dumps({"workflow_id": workflow_id, "task_ids": task_ids}, sort_keys=True),
                ),
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return int(run_id), [int(t) for t in task_ids]
