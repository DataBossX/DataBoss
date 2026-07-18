from __future__ import annotations

from .database import DataBossDatabase


def create_app(db_path: str):
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("FastAPI is required to create the DataBossX API app") from exc

    db = DataBossDatabase(db_path)
    app = FastAPI(title="DataBossX Control API", version="0.1.0")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

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
        rows = db.fetchall(
            """
            SELECT a.id, a.logical_key, a.asset_class, av.sha256, av.byte_size, av.original_locator
              FROM assets a
              JOIN asset_versions av ON av.asset_id = a.id
             WHERE a.project_id = ?
             ORDER BY a.id, av.id
            """,
            (project_id,),
        )
        return [dict(row) for row in rows]

    return app
