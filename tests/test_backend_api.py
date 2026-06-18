"""Integration tests for the FastAPI backend via TestClient.

Hermetic: LLM clients are disabled so no external/paid calls are made, and a
throwaway SQLite database is used per test. Skipped cleanly when the backend's
runtime deps are not installed.
"""
import dataclasses
import importlib
import warnings

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("multipart")  # python-multipart, needed for uploads

warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient  # noqa: E402

server = importlib.import_module("server")


@pytest.fixture()
def client(monkeypatch, tmp_path):
    # Disable all LLM providers → background processing makes no external calls.
    monkeypatch.setattr(server, "openai_client", None, raising=False)
    monkeypatch.setattr(server, "anthropic_client", None, raising=False)
    monkeypatch.setattr(server, "GEMINI_API_KEY", None, raising=False)
    monkeypatch.setattr(server, "genai", None, raising=False)
    # Fresh database per test.
    monkeypatch.setattr(server, "SQLITE_DB_PATH", str(tmp_path / "test.db"),
                        raising=False)
    # Generous rate limit so unrelated tests don't trip it.
    server._rate_buckets.clear()
    with TestClient(server.app) as c:
        yield c


def _upload(client, name="doc.txt", content=b"hello world", ctype="text/plain"):
    return client.post(
        "/api/documents/upload",
        files={"file": (name, content, ctype)},
    )


def test_root_and_health(client):
    assert client.get("/").json()["service"] == "DataBossX API"
    h = client.get("/api/health")
    assert h.status_code == 200
    body = h.json()
    assert body["status"] == "healthy"
    assert body["services"]["openai"] == "unavailable"
    assert "max_upload_mb" in body["limits"]
    assert "X-Request-ID" in h.headers
    assert "X-Process-Time-ms" in h.headers


def test_upload_happy_path(client):
    r = _upload(client)
    assert r.status_code == 200
    assert r.json()["status"] == "processing"
    docs = client.get("/api/documents").json()
    assert len(docs) == 1
    assert docs[0]["filename"] == "doc.txt"


def test_upload_rejects_empty(client):
    assert _upload(client, content=b"").status_code == 400


def test_upload_rejects_bad_extension(client):
    assert _upload(client, name="evil.exe",
                   ctype="application/octet-stream").status_code == 415


def test_upload_sanitizes_path_traversal_name(client):
    r = _upload(client, name="../../etc/passwd.txt")
    assert r.status_code == 200
    assert r.json()["filename"] == "passwd.txt"


def test_upload_rejects_oversize(client, monkeypatch):
    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 10, raising=False)
    assert _upload(client, content=b"x" * 50).status_code == 413


def test_duplicate_upload_returns_409(client):
    assert _upload(client, content=b"same").status_code == 200
    assert _upload(client, content=b"same").status_code == 409


def test_document_detail_404(client):
    assert client.get("/api/documents/does-not-exist").status_code == 404


def test_analytics_and_logs(client):
    _upload(client)
    assert client.get("/api/analytics").status_code == 200
    logs = client.get("/api/logs")
    assert logs.status_code == 200
    assert isinstance(logs.json(), list)


def test_rate_limit_returns_429(client, monkeypatch):
    low = dataclasses.replace(server.settings, rate_limit_max=2,
                              rate_limit_window_sec=60.0)
    monkeypatch.setattr(server, "settings", low, raising=False)
    server._rate_buckets.clear()
    codes = [_upload(client, content=bytes([i])).status_code for i in range(4)]
    assert 429 in codes
