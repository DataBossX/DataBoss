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
    task_specs = [
        ("REGISTER_SOURCES", {"stage": "A", "description": "Register source roots as read-only"}),
        ("INVENTORY_AND_LOCK", {"stage": "B", "description": "Inventory and evidence lock"}),
        ("REGISTER_TEMPLATE", {"stage": "A", "description": "Register approved workbook template"}),
    ]
    task_ids: list[int] = []
    for task_type, payload in task_specs:
        task_ids.append(
            db.execute(
                """
                INSERT INTO tasks (run_id, task_type, state, priority, payload_json)
                VALUES (?, ?, 'READY', 100, ?)
                """,
                (run_id, task_type, json.dumps(payload, sort_keys=True)),
            )
        )
    db.audit(
        project_id,
        "run.seeded",
        "run",
        str(run_id),
        json.dumps({"workflow_id": workflow_id, "task_ids": task_ids}, sort_keys=True),
    )
    return run_id, task_ids
