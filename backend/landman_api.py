"""FastAPI router for the DataBossX Landman Helper.

Exposes the connected title-examination workflow over HTTP:

    POST   /api/landman/projects              create a title project
    GET    /api/landman/projects              list title projects
    GET    /api/landman/projects/{id}         project detail + latest analysis
    DELETE /api/landman/projects/{id}         delete a project (local runtime)
    POST   /api/landman/projects/{id}/documents        upload a document (file)
    POST   /api/landman/projects/{id}/documents/text   add a document (JSON text)
    POST   /api/landman/projects/{id}/analyze          run the title analysis
    GET    /api/landman/projects/{id}/analysis         latest analysis
    POST   /api/landman/demo                   one-click seeded demo project

Persistence, evidence vaulting, and audit all flow through the DataBossX
foundation (:mod:`databossx`); the actual reconciliation is done by the exact
interest engine (``horizon``) fed by deterministic document extraction
(``grocery_report_pipeline``).
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

# Make the repo root (grocery + horizon) and src/ (databossx) importable.
_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (_REPO_ROOT, _REPO_ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from databossx.config import DataBossConfig  # noqa: E402
from databossx.database import DataBossDatabase  # noqa: E402
from databossx.intake import create_project  # noqa: E402
from databossx.title_intelligence import (  # noqa: E402
    analyze_project,
    extract_conveyance,
    load_text_from_bytes,
    register_document,
    seed_demo_project,
)

router = APIRouter(prefix="/api/landman", tags=["landman"])

CONFIG = DataBossConfig.from_repo_root(_REPO_ROOT)


class CreateProjectRequest(BaseModel):
    name: str
    jurisdiction_code: str = "OK"
    section: Optional[str] = None


class TextDocumentRequest(BaseModel):
    filename: str
    text: str


class AnalyzeRequest(BaseModel):
    section: Optional[str] = None


def _db(project_id: str) -> DataBossDatabase:
    db_path = CONFIG.project_db_path(project_id)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    return DataBossDatabase(db_path)


def _project_meta(project_id: str) -> Dict[str, Any]:
    db = _db(project_id)
    row = db.fetchone(
        "SELECT id, name, jurisdiction_code, status, created_at FROM projects LIMIT 1"
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")
    notes_row = db.fetchone(
        "SELECT notes FROM title_projects WHERE project_id = ?", (project_id,)
    )
    section = None
    if notes_row and notes_row["notes"]:
        try:
            section = json.loads(notes_row["notes"]).get("section")
        except (json.JSONDecodeError, AttributeError):
            section = None
    doc_row = db.fetchone(
        "SELECT COUNT(*) AS n FROM assets WHERE project_id = ? AND asset_class = 'source_document'",
        (project_id,),
    )
    return {
        "project_id": row["id"],
        "name": row["name"],
        "jurisdiction_code": row["jurisdiction_code"],
        "status": row["status"],
        "created_at": row["created_at"],
        "section": section,
        "document_count": int(doc_row["n"]) if doc_row else 0,
    }


def _latest_analysis(project_id: str) -> Optional[Dict[str, Any]]:
    db = _db(project_id)
    art = db.fetchone(
        """
        SELECT id FROM derived_artifacts
         WHERE project_id = ? AND artifact_type = 'title_analysis'
         ORDER BY id DESC LIMIT 1
        """,
        (project_id,),
    )
    if art is None:
        return None
    path = CONFIG.project_artifacts_root(project_id) / f"title_analysis_{art['id']}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _set_section(project_id: str, section: Optional[str]) -> None:
    if not section:
        return
    db = _db(project_id)
    db.execute(
        "UPDATE title_projects SET notes = ? WHERE project_id = ?",
        (json.dumps({"section": section}), project_id),
    )


@router.post("/projects")
async def create_landman_project(req: CreateProjectRequest) -> Dict[str, Any]:
    project = await asyncio.to_thread(
        create_project, CONFIG, name=req.name, jurisdiction_code=req.jurisdiction_code
    )
    _set_section(project.project_id, req.section)
    return _project_meta(project.project_id)


@router.get("/projects")
async def list_landman_projects() -> List[Dict[str, Any]]:
    root = CONFIG.projects_root
    if not root.exists():
        return []
    projects: List[Dict[str, Any]] = []
    for entry in sorted(root.iterdir()):
        if not CONFIG.project_db_path(entry.name).exists():
            continue
        try:
            meta = _project_meta(entry.name)
        except HTTPException:
            continue
        analysis = _latest_analysis(entry.name)
        meta["latest_summary"] = analysis["summary"] if analysis else None
        projects.append(meta)
    projects.sort(key=lambda p: p.get("created_at") or "", reverse=True)
    return projects


@router.get("/projects/{project_id}")
async def get_landman_project(project_id: str) -> Dict[str, Any]:
    meta = _project_meta(project_id)
    analysis = _latest_analysis(project_id)
    if analysis is not None:
        documents = analysis.get("documents", [])
    else:
        db = _db(project_id)
        rows = db.fetchall(
            "SELECT logical_key FROM assets WHERE project_id = ? AND asset_class = 'source_document' ORDER BY id",
            (project_id,),
        )
        documents = [{"filename": r["logical_key"], "analyzed": False} for r in rows]
    return {"project": meta, "documents": documents, "analysis": analysis}


@router.delete("/projects/{project_id}")
async def delete_landman_project(project_id: str) -> Dict[str, Any]:
    root = CONFIG.project_root(project_id)
    if not root.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    await asyncio.to_thread(shutil.rmtree, root)
    return {"deleted": project_id}


@router.post("/projects/{project_id}/documents")
async def upload_landman_document(project_id: str, file: UploadFile = File(...)) -> Dict[str, Any]:
    _db(project_id)  # existence check
    data = await file.read()
    stored = await asyncio.to_thread(
        register_document, CONFIG, project_id, file.filename or "document.txt", data
    )
    text, ocr_used = await asyncio.to_thread(load_text_from_bytes, stored["filename"], data)
    fact = extract_conveyance(stored["filename"], text)
    fact.ocr_used = ocr_used
    return {"stored": stored, "preview": fact.to_dict()}


@router.post("/projects/{project_id}/documents/text")
async def add_landman_document_text(project_id: str, req: TextDocumentRequest) -> Dict[str, Any]:
    _db(project_id)  # existence check
    stored = await asyncio.to_thread(
        register_document, CONFIG, project_id, req.filename, req.text.encode("utf-8")
    )
    preview = extract_conveyance(stored["filename"], req.text).to_dict()
    return {"stored": stored, "preview": preview}


@router.post("/projects/{project_id}/analyze")
async def analyze_landman_project(project_id: str, req: AnalyzeRequest) -> Dict[str, Any]:
    meta = _project_meta(project_id)
    section = req.section or meta.get("section")
    _set_section(project_id, section)
    analysis = await asyncio.to_thread(analyze_project, CONFIG, project_id, section)
    return analysis


@router.get("/projects/{project_id}/analysis")
async def get_landman_analysis(project_id: str) -> Dict[str, Any]:
    _db(project_id)  # existence check
    analysis = _latest_analysis(project_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="No analysis yet; run /analyze first")
    return analysis


@router.post("/demo")
async def create_landman_demo() -> Dict[str, Any]:
    result = await asyncio.to_thread(seed_demo_project, CONFIG)
    _set_section(result["project_id"], result["analysis"].get("section"))
    return {"project": _project_meta(result["project_id"]), "analysis": result["analysis"]}
