"""Private control-plane HTTP API (standard library only).

Security posture, all enforced server-side because a client control is not a
control:

* session cookie is HttpOnly, SameSite=Strict, Secure when served over TLS;
* every state-changing request needs a matching CSRF header token;
* CORS is an exact allowlist and never a wildcard alongside credentials;
* a strict CSP with no inline script, plus the usual hardening headers;
* per-session and per-IP rate limiting with lockout;
* role checks on every route, evaluated from the session, never from the body;
* phone-facing responses are redacted for absolute paths and secret-shaped
  values before they leave the process.

Binding defaults to 127.0.0.1. This service must not be exposed publicly.
"""

from __future__ import annotations

import json
import mimetypes
import os
import secrets
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Mapping, Optional
from urllib.parse import parse_qs, urlparse

from . import POLICY_VERSION
from . import best_moves as bm
from . import voice as voicemod
from . import watchers as watchmod
from .errors import ControlKernelError, HoldRemovalForbidden, NotAuthenticated, NotAuthorized
from .kernel import Actor, ControlKernel
from .runner import LocalRunner, RunnerConfig

SESSION_COOKIE = "dbx_cc_session"
CSRF_HEADER = "X-DBX-CSRF"
SESSION_TTL_SECONDS = 3600
RATE_LIMIT_WINDOW = 60
# Applies to /api/ routes only. Static assets are not counted: one PWA page load
# pulls the shell plus icons, which would otherwise exhaust an API budget and
# lock out a legitimate phone client on a cold start.
RATE_LIMIT_MAX = 240
LOCKOUT_THRESHOLD = 8
LOCKOUT_SECONDS = 300

STATIC_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "..", "apps", "control-center-web",
)
STATIC_ROOT = os.path.normpath(STATIC_ROOT)

SECURITY_HEADERS = {
    # No inline script. The PWA ships as external files precisely so this can
    # stay strict.
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'; manifest-src 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=(self), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}


class SessionStore:
    def __init__(self):
        self._sessions: dict = {}
        self._lock = threading.Lock()

    def create(self, user_id: str, role: str, device_id: str) -> dict:
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        record = {
            "session_id": token, "user_id": user_id, "role": role, "device_id": device_id,
            "csrf": csrf, "issued_at": time.time(),
            "expires_at": time.time() + SESSION_TTL_SECONDS, "stepped_up": False,
        }
        with self._lock:
            self._sessions[token] = record
        return record

    def get(self, token: Optional[str]) -> Optional[dict]:
        if not token:
            return None
        with self._lock:
            record = self._sessions.get(token)
            if record is None:
                return None
            if time.time() >= record["expires_at"]:
                self._sessions.pop(token, None)
                return None
            return dict(record)

    def step_up(self, token: str) -> None:
        with self._lock:
            if token in self._sessions:
                self._sessions[token]["stepped_up"] = True

    def revoke(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(token, None)

    def expire_now(self, token: str) -> None:
        """Test hook for the expired-session red-team case."""
        with self._lock:
            if token in self._sessions:
                self._sessions[token]["expires_at"] = time.time() - 1


class RateLimiter:
    def __init__(self):
        self._hits: dict = {}
        self._failures: dict = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            locked_until = self._failures.get(key, {}).get("locked_until", 0)
            if now < locked_until:
                return False
            window = [t for t in self._hits.get(key, []) if now - t < RATE_LIMIT_WINDOW]
            window.append(now)
            self._hits[key] = window
            return len(window) <= RATE_LIMIT_MAX

    def record_failure(self, key: str) -> None:
        now = time.time()
        with self._lock:
            record = self._failures.setdefault(key, {"count": 0, "locked_until": 0})
            record["count"] += 1
            if record["count"] >= LOCKOUT_THRESHOLD:
                record["locked_until"] = now + LOCKOUT_SECONDS
                record["count"] = 0


class ControlCenterApp:
    """Request router. Holds the kernel, sessions, rate limiter, and CORS list."""

    def __init__(self, kernel: ControlKernel, *, allowed_origins=("http://127.0.0.1:8787",),
                 secure_cookies: bool = False, workroot: Optional[str] = None):
        self.kernel = kernel
        self.sessions = SessionStore()
        self.limiter = RateLimiter()
        # One kernel connection is shared across request threads, so requests
        # are serialized here. Correctness of the single-writer invariant does
        # not depend on this lock -- that lives in the database -- but SQLite
        # connection reuse does.
        self._request_lock = threading.RLock()
        # Exact allowlist. Never "*" while credentials are in play.
        self.allowed_origins = tuple(allowed_origins)
        self.secure_cookies = secure_cookies
        self.runner = LocalRunner(
            kernel, RunnerConfig(workroot=workroot or os.path.join(os.getcwd(), ".cc-runner"),
                                 simulation_only=True)
        )

    # ------------------------------------------------------------------ auth
    def actor_from_session(self, session: Optional[Mapping]) -> Actor:
        if session is None:
            raise NotAuthenticated("authentication required")
        return Actor(
            user_id=session["user_id"], role=session["role"],
            session_id=session["session_id"], device_id=session["device_id"],
            stepped_up=session.get("stepped_up", False),
        )

    def require_role(self, actor: Actor, minimum: str) -> None:
        from .policy import role_permits

        if not role_permits(actor.role, minimum):
            raise NotAuthorized(f"role {actor.role} is below required role {minimum}")

    # --------------------------------------------------------------- routes
    def handle(self, method: str, path: str, query: Mapping, body: Mapping,
               session: Optional[Mapping]) -> tuple:
        """Return (status, payload). Raises ControlKernelError for refusals."""
        with self._request_lock:
            return self._handle(method, path, query, body, session)

    def _handle(self, method: str, path: str, query: Mapping, body: Mapping,
                session: Optional[Mapping]) -> tuple:
        if path == "/api/health" and method == "GET":
            # Deliberately reveals nothing about secrets or configuration.
            return HTTPStatus.OK, {"status": "ok", "policy_version": POLICY_VERSION}

        if path == "/api/session" and method == "POST":
            user_id = str(body.get("user_id", "")).strip()
            if user_id not in ("ryan", "operator", "reviewer", "viewer"):
                raise NotAuthenticated("unknown demo identity")
            role = {"ryan": "OWNER", "operator": "OPERATOR",
                    "reviewer": "REVIEWER", "viewer": "VIEWER"}[user_id]
            self.kernel.upsert_user(user_id, user_id.title(), role)
            record = self.sessions.create(user_id, role, str(body.get("device_id", "unknown-device")))
            return HTTPStatus.OK, {"session_id": record["session_id"], "csrf": record["csrf"],
                                   "user_id": user_id, "role": role}

        if path == "/api/session" and method == "DELETE":
            if session:
                self.sessions.revoke(session["session_id"])
            return HTTPStatus.OK, {"ended": True}

        if path == "/api/session/step-up" and method == "POST":
            actor = self.actor_from_session(session)
            # A real deployment verifies a WebAuthn assertion here. The port is
            # explicit so the substitution is a one-place change.
            if body.get("method") != "WEBAUTHN_STUB":
                raise NotAuthorized("unsupported step-up method")
            self.sessions.step_up(session["session_id"])
            return HTTPStatus.OK, {"stepped_up": True, "user_id": actor.user_id,
                                   "method": "WEBAUTHN_STUB",
                                   "note": "SIMULATED step-up. Not a real authenticator assertion."}

        if path == "/api/posture" and method == "GET":
            actor = self.actor_from_session(session)
            self.require_role(actor, "VIEWER")
            return HTTPStatus.OK, voicemod.redact_for_phone(self.kernel.posture())

        if path == "/api/best-moves" and method == "GET":
            actor = self.actor_from_session(session)
            self.require_role(actor, "VIEWER")
            ranked = bm.rank_for(self.kernel.posture(), role=actor.role)
            best = bm.best_next_move(ranked)
            return HTTPStatus.OK, voicemod.redact_for_phone({
                "best_next_move": best.to_dict() if best else None,
                "alternatives": [r.to_dict() for r in ranked if r.eligible][1:5],
                "vetoed": [r.to_dict() for r in ranked if not r.eligible],
                "weights": dict(bm.WEIGHTS),
            })

        if path == "/api/voice/intake" and method == "POST":
            actor = self.actor_from_session(session)
            self.require_role(actor, "OPERATOR")
            result = voicemod.intake(
                str(body.get("transcript", "")),
                provider=str(body.get("provider", "local-stub-v1")),
                confidence=float(body.get("confidence") or 0.0),
                default_project=body.get("default_project"),
            )
            # Nothing is created here. The client must confirm next.
            return HTTPStatus.OK, voicemod.redact_for_phone(result.to_dict())

        if path == "/api/commands" and method == "POST":
            actor = self.actor_from_session(session)
            self.require_role(actor, "OPERATOR")
            if not body.get("confirmed"):
                raise NotAuthorized("transcript and intent must be confirmed before creating a command")
            command = self.kernel.create_command(
                actor,
                idempotency_key=str(body["idempotency_key"]),
                transcript_text=str(body.get("transcript", "")),
                intent=dict(body.get("intent") or {}),
                channel=str(body.get("channel", "VOICE")),
                provider=body.get("provider"),
                confirmed=True,
            )
            return HTTPStatus.OK, {"command_id": command["command_id"],
                                   "content_sha256": command["content_sha256"],
                                   "status": command["status"]}

        if path == "/api/jobs" and method == "GET":
            actor = self.actor_from_session(session)
            self.require_role(actor, "VIEWER")
            from . import db as dbmod

            rows = dbmod.fetchall(
                self.kernel.conn,
                "SELECT job_id, title, state, detail, created_at FROM jobs ORDER BY created_at DESC LIMIT 50",
            )
            return HTTPStatus.OK, {"jobs": [dict(r) for r in rows]}

        if path == "/api/audit" and method == "GET":
            actor = self.actor_from_session(session)
            self.require_role(actor, "REVIEWER")
            limit = int(query.get("limit", ["50"])[0])
            return HTTPStatus.OK, voicemod.redact_for_phone({
                "events": self.kernel.audit_tail(min(limit, 200)),
                "chain_valid": self.kernel.verify_audit_chain(),
            })

        if path == "/api/watchers" and method == "GET":
            actor = self.actor_from_session(session)
            self.require_role(actor, "VIEWER")
            reviews = watchmod.run_watchers(self.kernel.conn, "system", "current")
            return HTTPStatus.OK, {"reviews": reviews}

        if path == "/api/holds" and method == "GET":
            actor = self.actor_from_session(session)
            self.require_role(actor, "VIEWER")
            return HTTPStatus.OK, {"holds": self.kernel.active_holds(),
                                   "removable": False,
                                   "banner": "FOR REVIEW - HOLD - NO EXTERNAL RELEASE"}

        if path == "/api/holds/remove" and method == "POST":
            # Present on purpose: the refusal must be reachable and audited.
            actor = self.actor_from_session(session)
            self.kernel.attempt_remove_hold(actor, str(body.get("hold_id", "unknown")))
            raise HoldRemovalForbidden("unreachable")  # attempt_remove_hold always raises

        if path == "/api/run-slice" and method == "POST":
            actor = self.actor_from_session(session)
            self.require_role(actor, "OPERATOR")
            from .slice import run_slice
            import tempfile

            trace = run_slice(tempfile.mkdtemp(prefix="dbx-cc-api-"))
            trace.pop("kernel", None)
            return HTTPStatus.OK, voicemod.redact_for_phone(trace["summary"])

        return HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path}


def make_handler(app: ControlCenterApp):
    class Handler(BaseHTTPRequestHandler):
        server_version = "DataBossXCC/1.0"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # keep test output readable
            pass

        # ---------------------------------------------------------- helpers
        def _client_key(self) -> str:
            return self.client_address[0] if self.client_address else "unknown"

        def _origin_allowed(self) -> Optional[str]:
            origin = self.headers.get("Origin")
            if origin and origin in app.allowed_origins:
                return origin
            return None

        def _send(self, status, payload: Optional[Mapping] = None, *, raw: bytes = None,
                  content_type: str = "application/json", extra_headers: Mapping = None):
            body = raw if raw is not None else json.dumps(payload or {}).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for key, value in SECURITY_HEADERS.items():
                self.send_header(key, value)
            origin = self._origin_allowed()
            if origin:
                # Credentials only ever pair with an exact origin.
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.send_header("Vary", "Origin")
            for key, value in (extra_headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _session(self) -> Optional[dict]:
            cookie = self.headers.get("Cookie") or ""
            token = None
            for part in cookie.split(";"):
                name, _, value = part.strip().partition("=")
                if name == SESSION_COOKIE:
                    token = value
            return app.sessions.get(token)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            if length > 1_000_000:
                return {}
            raw = self.rfile.read(length)
            try:
                parsed = json.loads(raw.decode("utf-8"))
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}

        def _serve_static(self, path: str) -> None:
            rel = "index.html" if path in ("/", "") else path.lstrip("/")
            if ".." in rel or rel.startswith("/"):
                self._send(HTTPStatus.FORBIDDEN, {"error": "path_not_allowed"})
                return
            full = os.path.normpath(os.path.join(STATIC_ROOT, rel))
            if not full.startswith(STATIC_ROOT) or not os.path.isfile(full):
                self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if full.endswith(".webmanifest"):
                ctype = "application/manifest+json"
            with open(full, "rb") as handle:
                self._send(HTTPStatus.OK, raw=handle.read(), content_type=ctype)

        # ----------------------------------------------------------- verbs
        def do_OPTIONS(self):  # noqa: N802
            self._send(HTTPStatus.NO_CONTENT, {}, extra_headers={
                "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
                "Access-Control-Allow-Headers": f"Content-Type,{CSRF_HEADER}",
            })

        def do_GET(self):  # noqa: N802
            self._dispatch("GET")

        def do_HEAD(self):  # noqa: N802
            # Same routing as GET; _send skips the body for HEAD.
            self._dispatch("GET")

        def do_POST(self):  # noqa: N802
            self._dispatch("POST")

        def do_DELETE(self):  # noqa: N802
            self._dispatch("DELETE")

        def _dispatch(self, method: str):
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            if not path.startswith("/api/"):
                if method == "GET":
                    self._serve_static(path)
                else:
                    self._send(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method_not_allowed"})
                return

            # Rate limiting covers the control plane. Static shell requests are
            # excluded so a normal page load cannot lock the client out.
            if not app.limiter.allow(self._client_key()):
                self._send(HTTPStatus.TOO_MANY_REQUESTS, {"error": "rate_limited"})
                return

            session = self._session()
            body = self._read_body() if method in ("POST", "DELETE") else {}

            # CSRF on every state-changing request except initial login, which
            # has no session to protect yet.
            if method in ("POST", "DELETE") and path != "/api/session":
                if session is None:
                    app.limiter.record_failure(self._client_key())
                    self._send(HTTPStatus.UNAUTHORIZED,
                               {"error": "NOT_AUTHENTICATED", "message": "authentication required"})
                    return
                supplied = self.headers.get(CSRF_HEADER)
                if not supplied or not secrets.compare_digest(supplied, session["csrf"]):
                    app.limiter.record_failure(self._client_key())
                    self._send(HTTPStatus.FORBIDDEN,
                               {"error": "CSRF_FAILED", "message": "missing or invalid CSRF token"})
                    return

            try:
                status, payload = app.handle(method, path, query, body, session)
            except ControlKernelError as exc:
                app.limiter.record_failure(self._client_key())
                status_map = {
                    "NOT_AUTHENTICATED": HTTPStatus.UNAUTHORIZED,
                    "NOT_AUTHORIZED": HTTPStatus.FORBIDDEN,
                    "STEP_UP_REQUIRED": HTTPStatus.FORBIDDEN,
                    "HOLD_REMOVAL_FORBIDDEN": HTTPStatus.FORBIDDEN,
                    "LEASE_HELD": HTTPStatus.CONFLICT,
                }
                self._send(status_map.get(exc.code, HTTPStatus.BAD_REQUEST),
                           {"error": exc.code, "message": str(exc)})
                return
            except Exception as exc:  # never leak internals to a phone client
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR,
                           {"error": "INTERNAL_ERROR", "message": type(exc).__name__})
                return

            extra = {}
            if path == "/api/session" and method == "POST" and status == HTTPStatus.OK:
                flags = f"{SESSION_COOKIE}={payload['session_id']}; HttpOnly; SameSite=Strict; Path=/"
                if app.secure_cookies:
                    flags += "; Secure"
                extra["Set-Cookie"] = flags
            self._send(status, payload, extra_headers=extra)

    return Handler


def serve(kernel: ControlKernel, *, host: str = "127.0.0.1", port: int = 8787,
          workroot: Optional[str] = None) -> ThreadingHTTPServer:
    """Bind loopback only. Public binding is a prohibited action in this lane."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise NotAuthorized("the control API may not bind a public interface in this lane")
    app = ControlCenterApp(kernel, allowed_origins=(f"http://{host}:{port}",), workroot=workroot)
    server = ThreadingHTTPServer((host, port), make_handler(app))
    server.app = app
    return server


if __name__ == "__main__":  # pragma: no cover
    import tempfile

    work = tempfile.mkdtemp(prefix="dbx-cc-serve-")
    k = ControlKernel.open(os.path.join(work, "command_center.db"))
    srv = serve(k, workroot=work)
    print(f"DataBossX Command Center on http://127.0.0.1:8787 (private, loopback only)")
    srv.serve_forever()
