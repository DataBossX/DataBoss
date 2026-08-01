"""Loopback-only Command Center server (stdlib).

Exists so the Command Center is runnable on a machine with no third-party
packages installed. It binds 127.0.0.1 by default and refuses to start on a
non-loopback address unless explicitly forced, because Alpha is not authorized to
expose the application over a network.

Controls: exact-origin checks, a session cookie, a per-session CSRF token
required on every mutating request, a small fixed-window rate limit, and no
directory serving of any kind — only the two routes below and one embedded page.
"""

from __future__ import annotations

import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path

from .redaction import redact
from .service import CommandBrain

UI_PATH = Path(__file__).resolve().parent / "ui" / "command_center.html"

MAX_BODY_BYTES = 64 * 1024
RATE_LIMIT_REQUESTS = 120
RATE_LIMIT_WINDOW_SECONDS = 60


class CommandCenterState:
    """Server-side session state. Nothing security-relevant lives in the browser."""

    def __init__(self, brain: CommandBrain, host: str, port: int):
        self.brain = brain
        self.host = host
        self.port = port
        self.session_id = secrets.token_urlsafe(24)
        self.csrf_token = secrets.token_urlsafe(24)
        self.allowed_origins = {f"http://{host}:{port}", f"http://localhost:{port}"}
        self._hits: list[float] = []

    def rate_limited(self, now: float) -> bool:
        self._hits = [t for t in self._hits if now - t < RATE_LIMIT_WINDOW_SECONDS]
        self._hits.append(now)
        return len(self._hits) > RATE_LIMIT_REQUESTS


class CommandCenterHandler(BaseHTTPRequestHandler):
    server_version = "DataBossXCommandBrain/alpha"
    state: CommandCenterState = None  # set by make_server

    # -- helpers ----------------------------------------------------------
    def _send(self, status: int, payload, content_type="application/json") -> None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'",
        )
        self.send_header(
            "Set-Cookie",
            f"dbx_session={self.state.session_id}; Path=/; HttpOnly; SameSite=Strict",
        )
        self.end_headers()
        self.wfile.write(body)

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            return True  # same-origin navigation and curl on loopback
        return origin in self.state.allowed_origins

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def log_message(self, fmt, *args):  # pragma: no cover - quiet by default
        pass

    # -- routes -----------------------------------------------------------
    def do_GET(self):  # noqa: N802 - stdlib naming
        if self.path in ("/", "/index.html"):
            html = UI_PATH.read_text(encoding="utf-8").replace(
                "window.CSRF_TOKEN || \"\"", json.dumps(self.state.csrf_token)
            )
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        if self.path == "/api/state":
            payload = self.state.brain.command_center_state()
            payload["voice_note"] = (
                "SIMULATED voice transport. Live audio capture is not enabled in Command Brain Alpha."
            )
            return self._send(200, payload)
        return self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802 - stdlib naming
        import time

        if self.state.rate_limited(time.monotonic()):
            return self._send(429, {"error": "rate limited"})
        if not self._origin_ok():
            return self._send(403, {"error": "origin not allowed"})
        if self.headers.get("X-CSRF-Token") != self.state.csrf_token:
            return self._send(403, {"error": "missing or invalid CSRF token"})
        try:
            body = self._read_json()
        except ValueError as exc:
            return self._send(400, {"error": str(exc)})

        brain = self.state.brain
        try:
            if self.path == "/api/command":
                response = brain.handle(
                    str(body.get("transcript", ""))[:4000], channel=str(body.get("channel", "text"))
                )
                return self._send(200, response.to_dict())
            if self.path == "/api/approve":
                approval = brain.approve(
                    str(body["envelope_id"]), approver_id=brain.requesting_user, method="authenticated_ui"
                )
                return self._send(200, approval.to_dict())
            if self.path == "/api/execute":
                result = brain.execute(str(body["envelope_id"]), str(body["approval_id"]))
                return self._send(200, redact(result))
        except Exception as exc:  # noqa: BLE001 - surfaced as a typed refusal
            detail = getattr(exc, "to_dict", None)
            return self._send(400, detail() if detail else {"error": str(exc)})
        return self._send(404, {"error": "not found"})


def make_server(brain: CommandBrain, host: str = "127.0.0.1", port: int = 8787, allow_public: bool = False):
    """Create the loopback server. Non-loopback binds require an explicit override."""
    address = ip_address(host)
    if not address.is_loopback and not allow_public:
        raise RuntimeError(
            f"Refusing to bind {host}: Command Brain Alpha is not authorized to listen on a "
            "non-loopback address."
        )
    state = CommandCenterState(brain, host, port)
    handler = type("BoundHandler", (CommandCenterHandler,), {"state": state})
    server = ThreadingHTTPServer((host, port), handler)
    server.command_center_state = state
    return server


def serve(brain: CommandBrain, host: str = "127.0.0.1", port: int = 8787) -> None:  # pragma: no cover
    server = make_server(brain, host, port)
    print(f"DataBossX Command Center on http://{host}:{port} (loopback only)")
    server.serve_forever()
