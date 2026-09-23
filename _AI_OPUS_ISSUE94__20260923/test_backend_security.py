"""Issue #94 fail-closed backend regressions (mandatory cases 5-7).

  5. Every non-health data endpoint rejects unauthenticated access.
  6. Untrusted origins cannot make credentialed requests.
  7. Real-upload mode refuses mock OCR and never emits invented legal facts.

Requirements on ``backend.server``:
  * importing it must not import openai / anthropic / google.generativeai and
    must not create log files or databases (checked in a subprocess);
  * it exposes ``create_app()`` that reads configuration from the environment
    at call time (a module-level ``app`` is used via reload as a fallback).

Only synthetic bytes are uploaded. No network, no LLM calls.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import os
import re
import subprocess
import sys
import textwrap
from datetime import date
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Environment contract. Adjust here if production renames a variable.
TOKEN_ENV = "DATABOSSX_DEMO_TOKEN"
DEMO_ENV = "DATABOSSX_DEMO_MODE"
CORS_ENV = "DATABOSSX_CORS_ORIGINS"
SYNTHETIC_HEADER = "X-Databossx-Synthetic"
TOKEN = "issue94-synthetic-token-7c1e0b"
AUTH = {"Authorization": f"Bearer {TOKEN}"}

TRUSTED = "http://trusted.issue94.test"
EVIL = "https://evil.issue94.test"

PUBLIC_PATHS = {"/api/health", "/healthz", "/docs", "/docs/oauth2-redirect",
                "/openapi.json", "/redoc"}
KNOWN_DATA_ROUTES = [
    ("POST", "/api/documents/upload"),
    ("GET", "/api/documents"),
    ("GET", "/api/documents/issue94-nonexistent"),
    ("GET", "/api/logs"),
    ("GET", "/api/analytics"),
]
BLOCKED_SDKS = ("openai", "anthropic", "google.generativeai", "google.genai")

MOCK_FACT_MARKERS = (
    "Mock OCR result", "DataBossX Corp", "Client ABC", "Sample Legal Document",
    "important legal information", "Key Information:", "Document Type:",
)
LEAK_MARKERS = ("Traceback", "Exception", ".py\"", ".py'", "/workspace", "site-packages")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
@pytest.fixture()
def make_client(monkeypatch, tmp_path):
    def _make(*, demo: bool = False, token: str | None = TOKEN,
              cors: str | None = TRUSTED):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "issue94.db"))
        for name, value in ((TOKEN_ENV, token), (CORS_ENV, cors),
                            (DEMO_ENV, "1" if demo else None)):
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        server = importlib.import_module("backend.server")
        if hasattr(server, "create_app"):
            app = server.create_app()
        else:
            app = importlib.reload(server).app
        return TestClient(app, raise_server_exceptions=False), app, server
    return _make


def _data_routes(app):
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path not in PUBLIC_PATHS:
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                yield method, route.path


def _call(client, method, path, headers=None, filename="SYNTHETIC_probe.txt"):
    url = re.sub(r"\{[^}]+\}", "issue94-nonexistent", path)
    if method == "POST" and "upload" in path:
        return client.post(url, headers=headers or {},
                           files={"file": (filename, b"SYNTHETIC probe bytes", "text/plain")})
    return client.request(method, url, headers=headers or {})


def _assert_rejected(resp, where):
    assert resp.status_code in (401, 403), f"{where}: HTTP {resp.status_code} {resp.text[:200]}"
    _assert_no_leak(resp, where)


def _assert_no_leak(resp, where):
    for marker in LEAK_MARKERS + MOCK_FACT_MARKERS:
        assert marker not in resp.text, f"{where}: response leaked {marker!r}"


# ---------------------------------------------------------------------------
# Import hygiene (precondition for every test below)
# ---------------------------------------------------------------------------
def test_backend_imports_without_llm_sdks_or_side_effects(tmp_path):
    probe = textwrap.dedent(f"""
        import importlib.abc, sys
        BLOCKED = {BLOCKED_SDKS!r}
        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if any(name == b or name.startswith(b + ".") for b in BLOCKED):
                    raise ImportError("issue94: blocked eager import of " + name)
                return None
        sys.meta_path.insert(0, Block())
        sys.path.insert(0, {str(REPO_ROOT)!r})
        import backend.server as s
        assert hasattr(s, "create_app") or hasattr(s, "app")
        leaked = [m for m in sys.modules if any(m == b or m.startswith(b + ".") for b in BLOCKED)]
        assert not leaked, leaked
    """)
    env = {k: v for k, v in os.environ.items() if not k.startswith("DATABOSSX_")}
    env.update(SQLITE_DB_PATH=str(tmp_path / "issue94.db"), PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-c", probe], cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-2000:]
    created = sorted(p.name for p in tmp_path.iterdir())
    assert created == [], f"import created files: {created}"


# ---------------------------------------------------------------------------
# Regression 5 -- authentication on every non-health data endpoint
# ---------------------------------------------------------------------------
def test_health_is_public(make_client):
    client, _, _ = make_client()
    resp = client.get("/api/health")
    assert resp.status_code == 200
    _assert_no_leak(resp, "/api/health")


def test_every_registered_data_route_rejects_unauthenticated(make_client):
    client, app, _ = make_client()
    routes = list(_data_routes(app))
    assert routes, "no data routes discovered; coverage would be vacuous"
    for method, path in routes:
        _assert_rejected(_call(client, method, path), f"{method} {path}")


@pytest.mark.parametrize("method, path", KNOWN_DATA_ROUTES,
                         ids=[f"{m} {p}" for m, p in KNOWN_DATA_ROUTES])
def test_known_data_routes_reject_unauthenticated(make_client, method, path):
    client, app, _ = make_client()
    resp = _call(client, method, path)
    registered = {p for _, p in _data_routes(app)}
    if resp.status_code == 404 and not any(
            re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", p), path) for p in registered):
        pytest.skip(f"{path} retired from the app")
    _assert_rejected(resp, f"{method} {path}")


BAD_CREDENTIALS = {
    "none": ({}, ""),
    "wrong_bearer": ({"Authorization": "Bearer wrong"}, ""),
    "empty_bearer": ({"Authorization": "Bearer "}, ""),
    "prefix_of_token": ({"Authorization": f"Bearer {TOKEN[:-1]}"}, ""),
    "token_plus_suffix": ({"Authorization": f"Bearer {TOKEN}x"}, ""),
    "no_scheme": ({"Authorization": TOKEN + "x"}, ""),
    "basic_scheme": ({"Authorization": "Basic aXNzdWU5NDp3cm9uZw=="}, ""),
    "wrong_demo_header": ({"X-Databossx-Demo-Token": "wrong"}, ""),
    "token_in_query_string": ({}, f"?token={TOKEN}&access_token={TOKEN}"),
    "token_in_cookie": ({"Cookie": f"token={TOKEN}; session={TOKEN}"}, ""),
}


@pytest.mark.parametrize("headers, query", BAD_CREDENTIALS.values(), ids=BAD_CREDENTIALS.keys())
@pytest.mark.parametrize("path", ["/api/documents", "/api/logs", "/api/analytics"])
def test_bad_credentials_rejected(make_client, headers, query, path):
    client, _, _ = make_client()
    _assert_rejected(client.get(path + query, headers=headers), f"GET {path}{query} {headers}")


@pytest.mark.parametrize("headers", [
    {}, {"Authorization": "Bearer "}, {"Authorization": "Bearer None"},
    {"Authorization": "Bearer null"}, {"X-Databossx-Demo-Token": ""},
], ids=["none", "empty", "None", "null", "empty_demo_header"])
def test_unconfigured_token_denies_everyone(make_client, headers):
    client, app, _ = make_client(token=None)
    for method, path in _data_routes(app):
        _assert_rejected(_call(client, method, path, headers), f"{method} {path} token-unset")


def test_valid_token_is_accepted(make_client):
    client, _, _ = make_client()
    resp = client.get("/api/documents", headers=AUTH)
    assert resp.status_code == 200, resp.text[:200]


@pytest.mark.parametrize("path", [
    "/api/documents/", "/api/logs/", "/api/analytics/", "/api/logs?limit=1",
    "/api//logs", "/api/documents/%2e%2e/logs", "/api/documents/x/../../logs",
])
def test_path_variants_do_not_bypass_auth(make_client, path):
    client, _, _ = make_client()
    resp = client.get(path, follow_redirects=False)
    assert resp.status_code in (301, 307, 308, 401, 403, 404, 405), (
        f"{path}: unauthenticated HTTP {resp.status_code} {resp.text[:200]}")
    _assert_no_leak(resp, path)


@pytest.mark.parametrize("probe_path", ["/api/issue94-probe", "/internal/issue94-probe"])
def test_auth_is_default_deny_for_routes_added_later(make_client, probe_path):
    client, app, _ = make_client()

    async def probe():
        return {"synthetic": "data"}

    app.add_api_route(probe_path, probe, methods=["GET"])
    _assert_rejected(client.get(probe_path), f"GET {probe_path}")
    assert client.get(probe_path, headers=AUTH).status_code == 200


# ---------------------------------------------------------------------------
# Regression 6 -- no credentialed requests from untrusted origins
# ---------------------------------------------------------------------------
def _assert_origin_not_trusted(resp, origin, where):
    acao = resp.headers.get("access-control-allow-origin")
    acac = (resp.headers.get("access-control-allow-credentials") or "").lower()
    assert acao != origin, f"{where}: reflected untrusted origin {origin!r}"
    assert not (acao == "*" and acac == "true"), f"{where}: wildcard with credentials"
    assert acao in (None, TRUSTED), f"{where}: unexpected ACAO {acao!r}"


UNTRUSTED_ORIGINS = [
    EVIL, "null", f"{TRUSTED}.evil.issue94.test", f"{TRUSTED}:8443",
    TRUSTED.replace("http://", "https://"), f"http://evil.issue94.test/{TRUSTED}",
    "http://localhost:3000", "http://127.0.0.1:5173",
]


@pytest.mark.parametrize("origin", UNTRUSTED_ORIGINS)
def test_untrusted_origin_not_granted_on_public_route(make_client, origin):
    client, _, _ = make_client()
    resp = client.get("/api/health", headers={"Origin": origin})
    _assert_origin_not_trusted(resp, origin, "GET /api/health")


@pytest.mark.parametrize("origin", UNTRUSTED_ORIGINS)
def test_untrusted_origin_not_granted_on_credentialed_data_request(make_client, origin):
    client, _, _ = make_client()
    resp = client.get("/api/documents", headers={"Origin": origin, **AUTH,
                                                 "Cookie": "session=issue94"})
    _assert_origin_not_trusted(resp, origin, "GET /api/documents (credentialed)")


@pytest.mark.parametrize("origin", [EVIL, "null"])
@pytest.mark.parametrize("path", ["/api/documents", "/api/documents/upload", "/api/logs"])
def test_untrusted_preflight_is_not_approved(make_client, origin, path):
    client, _, _ = make_client()
    resp = client.options(path, headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST" if "upload" in path else "GET",
        "Access-Control-Request-Headers": "authorization,content-type",
    })
    _assert_origin_not_trusted(resp, origin, f"OPTIONS {path}")


def test_trusted_origin_is_granted_exactly(make_client):
    client, _, _ = make_client()
    resp = client.get("/api/health", headers={"Origin": TRUSTED})
    assert resp.headers.get("access-control-allow-origin") == TRUSTED


def test_default_configuration_rejects_foreign_origin(make_client):
    client, _, _ = make_client(cors=None)
    resp = client.get("/api/documents", headers={"Origin": EVIL, **AUTH})
    _assert_origin_not_trusted(resp, EVIL, "default CORS")


@pytest.mark.parametrize("cors", ["*", f"{TRUSTED},*", " * "])
def test_wildcard_cors_configuration_fails_closed(make_client, cors):
    try:
        client, _, _ = make_client(cors=cors)
    except Exception:
        return
    for path, headers in (("/api/health", {}), ("/api/documents", AUTH)):
        resp = client.get(path, headers={"Origin": EVIL, **headers})
        acao = resp.headers.get("access-control-allow-origin")
        assert acao not in (EVIL, "*"), f"wildcard config granted {acao!r} on {path}"


# ---------------------------------------------------------------------------
# Regression 7 -- real uploads never get mock OCR / invented legal facts
# ---------------------------------------------------------------------------
REAL_LOOKING_UPLOADS = [
    ("warranty_deed_book512_page118.pdf", b"%PDF-1.4\nsynthetic bytes standing in for a real scan"),
    ("scan_0001.png", b"\x89PNG\r\n\x1a\nsynthetic"),
    ("oil_gas_lease.txt", b"Lessor: synthetic\nLessee: synthetic\n"),
]


def _assert_no_invented_facts(resp, where):
    _assert_no_leak(resp, where)
    today = date.today().isoformat()
    assert today not in resp.text, f"{where}: emitted today's date as a document date"
    try:
        body = resp.json()
    except ValueError:
        return
    ocr = body.get("ocr") if isinstance(body, dict) else None
    if isinstance(ocr, dict):
        conf = ocr.get("confidence_score")
        assert not conf, f"{where}: mock OCR reported confidence {conf}"
        text = f"{ocr.get('raw_text', '')}\n{ocr.get('cleaned_text', '')}"
        assert not re.search(r"\b\d{4}-\d{2}-\d{2}\b", text), f"{where}: OCR text carries a date"
        assert not re.search(r"(?im)^[ \t]*-?[ \t]*parties?[ \t]*[:=][ \t]*\S", text), (
            f"{where}: invented parties")


def _assert_refused_upload(resp, where):
    assert 400 <= resp.status_code < 500, f"{where}: HTTP {resp.status_code} {resp.text[:200]}"
    _assert_no_invented_facts(resp, where)
    try:
        body = resp.json()
    except ValueError:
        return
    assert "ocr" not in body and "raw_text" not in json.dumps(body), f"{where}: OCR output on refusal"


@pytest.mark.parametrize("filename, content", REAL_LOOKING_UPLOADS,
                         ids=[n for n, _ in REAL_LOOKING_UPLOADS])
def test_real_mode_refuses_upload(make_client, filename, content):
    client, _, _ = make_client(demo=False)
    resp = client.post("/api/documents/upload", headers=AUTH,
                       files={"file": (filename, content, "application/octet-stream")})
    _assert_refused_upload(resp, f"real-mode {filename}")


def test_real_mode_ignores_spoofed_synthetic_markers(make_client):
    client, _, _ = make_client(demo=False)
    resp = client.post("/api/documents/upload", headers={**AUTH, SYNTHETIC_HEADER: "1"},
                       files={"file": ("SYNTHETIC_deed.txt", b"synthetic", "text/plain")})
    _assert_refused_upload(resp, "real-mode spoofed synthetic")


@pytest.mark.parametrize("filename, content", REAL_LOOKING_UPLOADS,
                         ids=[n for n, _ in REAL_LOOKING_UPLOADS])
def test_demo_mode_still_refuses_non_synthetic_upload(make_client, filename, content):
    client, _, _ = make_client(demo=True)
    resp = client.post("/api/documents/upload", headers=AUTH,
                       files={"file": (filename, content, "application/octet-stream")})
    _assert_refused_upload(resp, f"demo-mode real {filename}")


def test_refused_upload_is_not_persisted_or_listed(make_client):
    client, _, _ = make_client(demo=False)
    client.post("/api/documents/upload", headers=AUTH,
                files={"file": ("warranty_deed.pdf", b"%PDF-1.4 synthetic", "application/pdf")})
    listing = client.get("/api/documents", headers=AUTH)
    assert listing.status_code == 200
    assert "warranty_deed.pdf" not in listing.text
    _assert_no_invented_facts(listing, "listing after refusal")


def test_demo_synthetic_upload_is_labeled_and_fact_free(make_client):
    client, _, _ = make_client(demo=True)
    resp = client.post("/api/documents/upload", headers={**AUTH, SYNTHETIC_HEADER: "1"},
                       files={"file": ("SYNTHETIC_issue94.txt", b"synthetic", "text/plain")})
    if resp.status_code >= 400:
        _assert_refused_upload(resp, "demo synthetic (refusal is acceptable)")
        return
    assert resp.status_code == 200
    assert "SYNTHETIC" in resp.text.upper()
    _assert_no_invented_facts(resp, "demo synthetic")


@pytest.mark.parametrize("filename, size", [
    ("SYNTHETIC_payload.exe", 64), ("SYNTHETIC_payload.html", 64),
    ("SYNTHETIC_big.txt", 32 * 1024 * 1024 + 1), ("SYNTHETIC_empty.txt", 0),
])
def test_upload_type_and_size_limits(make_client, filename, size):
    client, _, _ = make_client(demo=True)
    resp = client.post("/api/documents/upload", headers={**AUTH, SYNTHETIC_HEADER: "1"},
                       files={"file": (filename, b"S" * size, "application/octet-stream")})
    _assert_refused_upload(resp, f"limits {filename}")


def test_direct_ocr_helper_refuses_real_input(make_client):
    _, _, server = make_client(demo=False)
    fn = getattr(server, "process_ocr", None)
    if fn is None:
        pytest.skip("process_ocr retired")
    try:
        out = fn(b"%PDF-1.4 synthetic", "warranty_deed.pdf")
        if inspect.isawaitable(out):
            out = asyncio.run(out)
    except Exception:
        return
    rendered = json.dumps(out, default=str)
    for marker in MOCK_FACT_MARKERS:
        assert marker not in rendered
    assert not (out or {}).get("raw_text"), "process_ocr returned text for a real input"


def test_default_bind_is_loopback(make_client, monkeypatch):
    _, _, server = make_client()
    source = Path(server.__file__).read_text(encoding="utf-8")
    assert not re.search(r"host\s*=\s*['\"]0\.0\.0\.0['\"]", source), "hard-coded 0.0.0.0 bind"
    try:
        security = importlib.import_module("backend.security_controls")
    except ImportError:
        assert "127.0.0.1" in source, "no loopback default bind found"
        return
    monkeypatch.delenv("DATABOSSX_BIND", raising=False)
    assert security.bind_host() in ("127.0.0.1", "::1", "localhost")
    monkeypatch.setenv("DATABOSSX_BIND", "0.0.0.0")
    monkeypatch.delenv("DATABOSSX_ALLOW_NONLOCAL_BIND", raising=False)
    assert security.bind_host() in ("127.0.0.1", "::1", "localhost")
