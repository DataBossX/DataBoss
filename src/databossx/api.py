from __future__ import annotations

from .connectors.drive import DriveConnection, GoogleDriveConnector
from .database import DataBossDatabase
from .policy import POLICY_VERSION, PolicyEngine


def create_app(db_path: str):
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("FastAPI is required to create the DataBossX API app") from exc

    db = DataBossDatabase(db_path)
    engine = PolicyEngine()
    app = FastAPI(title="DataBossX Control API", version="0.2.0")

    def as_dicts(rows):
        return [dict(row) for row in rows]

    @app.get("/healthz")
    def healthz():
        write = engine.decide("drive.write", write=True)
        return {
            "status": "ok",
            "policy_version": POLICY_VERSION,
            "external_writes": write.allowed,
        }

    @app.get("/projects/{project_id}")
    def get_project(project_id: str):
        row = db.fetchone(
            "SELECT id, name, jurisdiction_code, policy_version, status, root_path FROM projects WHERE id = ?",
            (project_id,),
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return dict(row)

    @app.get("/projects/{project_id}/assets")
    def get_assets(project_id: str):
        return as_dicts(
            db.fetchall(
                """
                SELECT a.id, a.logical_key, a.asset_class, av.sha256, av.byte_size, av.original_locator
                  FROM assets a
                  JOIN asset_versions av ON av.asset_id = a.id
                 WHERE a.project_id = ?
                 ORDER BY a.id, av.id
                """,
                (project_id,),
            )
        )

    @app.get("/projects/{project_id}/tasks")
    def get_tasks(project_id: str):
        return as_dicts(
            db.fetchall(
                """
                SELECT t.id, t.task_type, t.state, t.priority, t.payload_json
                  FROM tasks t
                  JOIN runs r ON r.id = t.run_id
                 WHERE r.project_id = ?
                 ORDER BY t.id
                """,
                (project_id,),
            )
        )

    @app.get("/projects/{project_id}/audit")
    def get_audit(project_id: str, q: str = ""):
        if q:
            rows = db.fetchall(
                """
                SELECT a.id, a.event_type, a.entity_type, a.entity_id, a.payload_json, a.created_at
                  FROM audit_events_fts f
                  JOIN audit_events a ON a.id = f.rowid
                 WHERE audit_events_fts MATCH ?
                   AND a.project_id = ?
                 ORDER BY a.id
                """,
                (q, project_id),
            )
        else:
            rows = db.fetchall(
                """
                SELECT id, event_type, entity_type, entity_id, payload_json, created_at
                  FROM audit_events
                 WHERE project_id = ?
                 ORDER BY id
                """,
                (project_id,),
            )
        return as_dicts(rows)

    @app.get("/projects/{project_id}/claims")
    def get_claims(project_id: str):
        return as_dicts(
            db.fetchall(
                """
                SELECT id, subject, predicate, value_text, value_state, confidence
                  FROM claims
                 WHERE project_id = ?
                 ORDER BY id
                """,
                (project_id,),
            )
        )

    @app.post("/connectors/drive/scan")
    def drive_scan(payload: dict):
        root = payload.get("root")
        if not root:
            raise HTTPException(status_code=400, detail="root is required")
        connector = GoogleDriveConnector(
            DriveConnection(
                root_locator=str(root),
                backend=str(payload.get("backend") or "local_mirror"),
            )
        )
        write = connector.refuse_write()
        scan = connector.scan(dry_run=bool(payload.get("dry_run", True)))
        return {
            "item_count": len(scan.items),
            "cursor": scan.cursor,
            "dry_run": scan.dry_run,
            "write_attempted": scan.write_attempted,
            "external_write_allowed": write.allowed,
        }

    return app
