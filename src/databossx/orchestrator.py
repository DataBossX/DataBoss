from __future__ import annotations

import json

from .database import DataBossDatabase


def seed_project_intake_run(db: DataBossDatabase, project_id: str) -> tuple[int, list[int]]:
    workflow_name = "title_project_intake"
    workflow_id = db.execute(
        "INSERT OR IGNORE INTO workflow_definitions (name, version) VALUES (?, ?)",
        (workflow_name, "1.0.0"),
    )
    if not workflow_id:
        row = db.fetchone(
            "SELECT id FROM workflow_definitions WHERE name = ? ORDER BY id DESC LIMIT 1",
            (workflow_name,),
        )
        workflow_id = int(row["id"])

    run_id = db.execute(
        "INSERT INTO runs (project_id, workflow_id, status) VALUES (?, ?, ?)",
        (project_id, workflow_id, "PLANNED"),
    )
    # (task_type, initial_state, priority, payload). INVENTORY_AND_LOCK cannot
    # start until sources are registered, so it seeds BLOCKED with a dependency
    # edge and the orchestrator promotes it once REGISTER_SOURCES is DONE.
    task_specs = [
        ("REGISTER_SOURCES", "READY", 100, {"stage": "A", "description": "Register source roots as read-only"}),
        ("INVENTORY_AND_LOCK", "BLOCKED", 100, {"stage": "B", "description": "Inventory and evidence lock"}),
        ("REGISTER_TEMPLATE", "READY", 100, {"stage": "A", "description": "Register approved workbook template"}),
    ]
    task_ids: list[int] = []
    for task_type, state, priority, payload in task_specs:
        task_ids.append(
            db.execute(
                """
                INSERT INTO tasks (run_id, task_type, state, priority, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, task_type, state, priority, json.dumps(payload, sort_keys=True)),
            )
        )
    # REGISTER_SOURCES (index 0) blocks INVENTORY_AND_LOCK (index 1).
    db.execute(
        "INSERT INTO task_dependencies (parent_task_id, child_task_id) VALUES (?, ?)",
        (task_ids[0], task_ids[1]),
    )
    db.audit(
        project_id,
        "run.seeded",
        "run",
        str(run_id),
        json.dumps({"workflow_id": workflow_id, "task_ids": task_ids}, sort_keys=True),
    )
    return run_id, task_ids
