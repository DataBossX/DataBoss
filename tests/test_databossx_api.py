from __future__ import annotations

from databossx.api import create_app
from databossx.config import DataBossConfig
from databossx.intake import create_project


def test_control_api_health_and_project_routes(tmp_path):
    if not _fastapi_available():
        return
    from fastapi.testclient import TestClient

    config = DataBossConfig.from_repo_root(tmp_path / "repo")
    project = create_project(config, name="API", jurisdiction_code="OK", project_id="api1")
    client = TestClient(create_app(str(config.project_db_path(project.project_id))))

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["external_writes"] is False

    found = client.get("/projects/api1")
    assert found.status_code == 200
    assert found.json()["name"] == "API"

    tasks = client.get("/projects/api1/tasks")
    assert tasks.status_code == 200
    assert tasks.json()

    missing = client.get("/projects/missing")
    assert missing.status_code == 404


def _fastapi_available() -> bool:
    try:
        import fastapi  # noqa: F401
    except ImportError:
        return False
    return True
