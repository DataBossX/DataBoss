from __future__ import annotations

import pytest
from pathlib import Path

from databossx.config import DataBossConfig
from databossx.database import DataBossDatabase
from databossx.intake import (
    create_project,
    inventory_source,
    register_source_connection,
)
from databossx.api import create_app

try:
    from fastapi.testclient import TestClient
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI or TestClient not installed")
def test_databossx_api_endpoints(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    config = DataBossConfig.from_repo_root(repo_root)

    source_root = tmp_path / "source_docs"
    source_root.mkdir()
    doc = source_root / "sample_doc.txt"
    doc.write_text("API test content", encoding="utf-8")

    project = create_project(
        config,
        name="API Test Project",
        jurisdiction_code="OK",
        project_id="api_proj_001",
    )
    source = register_source_connection(config, project.project_id, source_root)
    inventory = inventory_source(config, project.project_id, source.source_connection_id)

    db_path = config.project_db_path(project.project_id)
    app = create_app(str(db_path))
    client = TestClient(app)

    # Health check
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

    # Get project
    res = client.get(f"/projects/{project.project_id}")
    assert res.status_code == 200
    pdata = res.json()
    assert pdata["id"] == project.project_id
    assert pdata["name"] == "API Test Project"
    assert pdata["jurisdiction_code"] == "OK"

    # Non-existent project
    res = client.get("/projects/non_existent_id")
    assert res.status_code == 404

    # Get assets
    res = client.get(f"/projects/{project.project_id}/assets")
    assert res.status_code == 200
    assets = res.json()
    assert len(assets) == 1
    assert assets[0]["logical_key"] == "sample_doc.txt"
    assert assets[0]["sha256"] == inventory.items[0].sha256
