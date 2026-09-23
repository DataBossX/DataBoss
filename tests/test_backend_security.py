from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from security_controls import (  # noqa: E402
    authenticate,
    bind_host,
    cors_origins,
    demo_ocr_payload,
    mock_ocr_allowed,
    validate_upload,
)


def test_unauthenticated_access_rejected(monkeypatch):
    monkeypatch.delenv("DATABOSSX_API_TOKEN", raising=False)
    ok, _ = authenticate(None)
    assert ok is False
    monkeypatch.setenv("DATABOSSX_API_TOKEN", "secret-token")
    assert authenticate(None)[0] is False
    assert authenticate("wrong")[0] is False
    assert authenticate("secret-token")[0] is True


def test_cors_forbids_wildcard_and_untrusted_origins(monkeypatch):
    monkeypatch.delenv("DATABOSSX_CORS_ORIGINS", raising=False)
    origins = cors_origins()
    assert "*" not in origins
    assert "https://evil.example" not in origins
    monkeypatch.setenv("DATABOSSX_CORS_ORIGINS", "*,http://localhost:3000")
    with pytest.raises(ValueError):
        cors_origins()


def test_bind_host_is_loopback(monkeypatch):
    monkeypatch.delenv("DATABOSSX_BIND_HOST", raising=False)
    assert bind_host() == "127.0.0.1"
    monkeypatch.setenv("DATABOSSX_BIND_HOST", "0.0.0.0")
    with pytest.raises(ValueError):
        bind_host()


def test_real_upload_mode_refuses_mock_ocr_and_invented_facts(monkeypatch):
    monkeypatch.delenv("DATABOSSX_DEMO_MODE", raising=False)
    allowed, reason = mock_ocr_allowed()
    assert allowed is False
    assert "disabled" in reason
    monkeypatch.setenv("DATABOSSX_DEMO_MODE", "1")
    payload = demo_ocr_payload("deed.pdf")
    assert payload["raw_text"] == ""
    assert payload["cleaned_text"] == ""
    assert payload["synthetic"] is True
    assert "no parties" in payload["note"]


def test_upload_limits():
    assert validate_upload("ok.txt", 12)[0] is True
    assert validate_upload("virus.exe", 12)[0] is False
    assert validate_upload("ok.txt", 11 * 1024 * 1024)[0] is False


def test_data_endpoints_require_auth(monkeypatch):
    monkeypatch.setenv("DATABOSSX_API_TOKEN", "kernel-token")
    monkeypatch.delenv("DATABOSSX_DEMO_MODE", raising=False)
    monkeypatch.setenv("DATABOSSX_CORS_ORIGINS", "http://127.0.0.1:3000")
    import server as backend_server

    importlib.reload(backend_server)
    from fastapi.testclient import TestClient

    client = TestClient(backend_server.app)
    assert client.get("/api/health").status_code == 200
    for path in ("/api/documents", "/api/logs", "/api/analytics"):
        response = client.get(path)
        assert response.status_code == 401, path
    authorized = client.get("/api/documents", headers={"X-DataBossX-Token": "kernel-token"})
    assert authorized.status_code in {200, 503}
    upload = client.post("/api/documents/upload", files={"file": ("deed.txt", b"hello", "text/plain")})
    assert upload.status_code == 401
    evil = client.get(
        "/api/documents",
        headers={"Origin": "https://evil.example", "Cookie": "session=1"},
    )
    assert evil.status_code in {401, 403}
