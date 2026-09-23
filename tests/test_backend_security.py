from __future__ import annotations

import os

import pytest

from backend import security_controls as security


@pytest.fixture
def demo_env(monkeypatch):
    monkeypatch.setenv("DATABOSSX_DEMO_MODE", "1")
    monkeypatch.setenv("DATABOSSX_DEMO_TOKEN", "demo-token")
    monkeypatch.setenv("DATABOSSX_BIND", "0.0.0.0")
    monkeypatch.setenv("DATABOSSX_CORS_ORIGINS", "http://127.0.0.1:3000")
    monkeypatch.delenv("DATABOSSX_ALLOW_NONLOCAL_BIND", raising=False)


def test_bind_host_fails_closed_to_loopback(demo_env):
    assert security.bind_host() == "127.0.0.1"


def test_wildcard_cors_rejected(monkeypatch):
    monkeypatch.setenv("DATABOSSX_CORS_ORIGINS", "*")
    with pytest.raises(security.SecurityError) as exc:
        security.cors_origins()
    assert exc.value.code == "WILDCARD_CORS_FORBIDDEN"


def test_protected_paths_need_token(demo_env):
    assert security.authorized({}) is False
    assert security.authorized({"X-Databossx-Demo-Token": "demo-token"}) is True
    assert security.authorized({"Authorization": "Bearer demo-token"}) is True
    assert security.is_protected_path("/api/documents")
    assert security.is_protected_path("/api/logs")
    assert security.is_protected_path("/api/analytics")
    assert not security.is_protected_path("/api/health")


def test_real_upload_refuses_mock_ocr(monkeypatch):
    monkeypatch.setenv("DATABOSSX_DEMO_MODE", "0")
    with pytest.raises(security.SecurityError) as exc:
        security.validate_upload("deed.pdf", 12, {})
    assert exc.value.code == "REAL_UPLOAD_REFUSED"
    assert security.mock_ocr_allowed("deed.pdf", {}) is False


def test_demo_mode_still_refuses_non_synthetic(demo_env):
    with pytest.raises(security.SecurityError) as exc:
        security.validate_upload("real_deed.pdf", 12, {})
    assert exc.value.code == "REAL_UPLOAD_REFUSED"


def test_synthetic_placeholder_has_no_invented_legal_facts(demo_env):
    text = security.synthetic_ocr_placeholder("SYNTHETIC_demo.txt")
    assert "SYNTHETIC_DEMO_PLACEHOLDER" in text
    assert "DataBossX Corp" not in text
    assert "Client ABC" not in text


def test_auth_is_default_deny_for_unknown_routes(demo_env):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from backend.server import create_app

    app = create_app()

    @app.get("/api/new-later-route")
    def later():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/api/new-later-route").status_code == 401
    ok = client.get("/api/new-later-route", headers={"X-Databossx-Demo-Token": "demo-token"})
    assert ok.status_code == 200


def test_app_data_routes_unauthenticated(demo_env):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from backend.server import create_app

    client = TestClient(create_app())
    assert client.get("/api/health").status_code == 200
    for path in ("/api/documents", "/api/logs", "/api/analytics"):
        assert client.get(path).status_code == 401
    upload = client.post(
        "/api/documents/upload",
        files={"file": ("SYNTHETIC_note.txt", b"hello", "text/plain")},
    )
    assert upload.status_code == 401


def test_untrusted_origin_is_not_reflected(demo_env):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from backend.server import create_app

    client = TestClient(create_app())
    response = client.get(
        "/api/health",
        headers={"Origin": "https://evil.example"},
    )
    assert response.headers.get("access-control-allow-origin") != "https://evil.example"
