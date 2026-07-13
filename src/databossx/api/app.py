"""FastAPI control API for DataBossX.

Loopback-only by default: the API is intended to be bound to 127.0.0.1 by
the process that runs it (see ``__main__`` below). CORS only allows
localhost origins. The API is intentionally thin -- it validates input,
delegates to the domain services (``TaskGraph``, ``AuditLog``, ``Vault``,
``MigrationRunner``), and returns plain dict/JSON responses.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from databossx import __version__
from databossx.audit.events import AuditLog
from databossx.db.migrations import MigrationRunner
from databossx.vault.store import Vault

app = FastAPI(title="DataBossX Control API", version="0.1.0")

# CORS: allow only local development origins -- never "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Configuration / dependency injection
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = Path("runtime/databossx.db")
_DEFAULT_VAULT_ROOT = Path("runtime/vault")
_DEFAULT_MIGRATIONS_DIR = Path("migrations")

_state: dict[str, Path] = {
    "db_path": _DEFAULT_DB_PATH,
    "vault_root": _DEFAULT_VAULT_ROOT,
    "migrations_dir": _DEFAULT_MIGRATIONS_DIR,
}


def configure(
    db_path: Path | None = None,
    vault_root: Path | None = None,
    migrations_dir: Path | None = None,
) -> None:
    """Configure global paths used by the API's dependency providers.

    Intended for use by the process entry point (or tests) before the
    application starts serving requests.
    """
    if db_path is not None:
        _state["db_path"] = Path(db_path)
    if vault_root is not None:
        _state["vault_root"] = Path(vault_root)
    if migrations_dir is not None:
        _state["migrations_dir"] = Path(migrations_dir)


def get_db_path() -> Path:
    return _state["db_path"]


def get_vault_root() -> Path:
    return _state["vault_root"]


def get_migrations_dir() -> Path:
    return _state["migrations_dir"]


def get_vault(vault_root: Path = Depends(get_vault_root)) -> Vault:
    return Vault(vault_root)


def get_audit_log(db_path: Path = Depends(get_db_path)) -> AuditLog:
    return AuditLog(db_path)


def get_connection(db_path: Path = Depends(get_db_path)) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str
    jurisdiction: str
    policy_set: str
    confidentiality: str
    lifecycle_state: str = "DRAFT"


class ProjectOut(BaseModel):
    id: str
    name: str
    jurisdiction: str
    policy_set: str
    confidentiality: str
    lifecycle_state: str
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health(
    db_path: Path = Depends(get_db_path),
    migrations_dir: Path = Depends(get_migrations_dir),
) -> dict:
    """Report service health, API version, and current DB schema version."""
    try:
        runner = MigrationRunner(db_path, migrations_dir)
        db_version = runner.current_version()
    except Exception:
        db_version = None
    return {"status": "ok", "version": __version__, "db_version": db_version}


@app.get("/projects")
def list_projects(conn: sqlite3.Connection = Depends(get_connection)) -> list[dict]:
    """List all projects."""
    try:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY created_at DESC"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(row) for row in rows]


@app.post("/projects", status_code=201)
def create_project(
    project: ProjectCreate, conn: sqlite3.Connection = Depends(get_connection)
) -> dict:
    """Create a new project."""
    project_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO projects
            (id, name, jurisdiction, policy_set, confidentiality,
             lifecycle_state, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            project.name,
            project.jurisdiction,
            project.policy_set,
            project.confidentiality,
            project.lifecycle_state,
            now,
            now,
        ),
    )
    conn.commit()
    return {
        "id": project_id,
        "name": project.name,
        "jurisdiction": project.jurisdiction,
        "policy_set": project.policy_set,
        "confidentiality": project.confidentiality,
        "lifecycle_state": project.lifecycle_state,
        "created_at": now,
        "updated_at": now,
    }


@app.get("/projects/{project_id}")
def get_project(
    project_id: str, conn: sqlite3.Connection = Depends(get_connection)
) -> dict:
    """Get a single project by id."""
    row = conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="project not found")
    return dict(row)


@app.get("/projects/{project_id}/tasks")
def list_project_tasks(
    project_id: str, conn: sqlite3.Connection = Depends(get_connection)
) -> list[dict]:
    """List tasks belonging to runs under this project."""
    rows = conn.execute(
        """
        SELECT tasks.* FROM tasks
        JOIN runs ON runs.id = tasks.run_id
        WHERE runs.project_id = ?
        ORDER BY tasks.created_at
        """,
        (project_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@app.get("/projects/{project_id}/audit")
def get_project_audit(
    project_id: str,
    event_type: Optional[str] = None,
    limit: int = 100,
    audit_log: AuditLog = Depends(get_audit_log),
) -> list[dict]:
    """Query the audit log scoped to this project."""
    return audit_log.query(project_id=project_id, event_type=event_type, limit=limit)


@app.post("/vault/put")
async def vault_put(file: UploadFile, vault: Vault = Depends(get_vault)) -> dict:
    """Accept an uploaded file, store it in the vault, and return its hash."""
    data = await file.read()
    sha256_hex = vault.put(data, artifact_type=file.content_type or "")
    return {"sha256": sha256_hex, "size_bytes": len(data)}


@app.get("/vault/{sha256_hex}")
def vault_get(sha256_hex: str, vault: Vault = Depends(get_vault)) -> dict:
    """Retrieve bytes from the vault by hash (base64-encoded in JSON)."""
    import base64

    try:
        data = vault.get(sha256_hex)
    except KeyError:
        raise HTTPException(status_code=404, detail="not found in vault")
    return {"sha256": sha256_hex, "content_base64": base64.b64encode(data).decode("ascii")}


def main() -> None:
    """Run the API bound to loopback (127.0.0.1) only."""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
