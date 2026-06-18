"""Tests for opt-in API-key auth, rate limiting, and security headers."""

import config
import security


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_auth_disabled_by_default(client):
    # No API_KEYS configured => endpoints are open.
    assert client.get("/api/documents").status_code == 200


def test_auth_enforced_when_configured(client, monkeypatch):
    monkeypatch.setattr(config, "API_KEYS", ["secret-key"])

    # Missing key -> 401 with the standard error envelope.
    r = client.get("/api/documents")
    assert r.status_code == 401
    assert "error" in r.json()

    # Wrong key -> 401.
    assert client.get("/api/documents", headers={"X-API-Key": "nope"}).status_code == 401

    # Correct key -> 200.
    assert client.get("/api/documents", headers={"X-API-Key": "secret-key"}).status_code == 200

    # Health stays open even with auth configured.
    assert client.get("/api/health").status_code == 200


def test_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 2)
    security.limiter.reset()

    assert client.get("/api/documents").status_code == 200
    assert client.get("/api/documents").status_code == 200
    blocked = client.get("/api/documents")
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") is not None

    security.limiter.reset()
