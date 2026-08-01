"""Optional FastAPI surface for the Command Brain.

FastAPI is not required to run the Command Brain — :mod:`.server` provides a
stdlib loopback Command Center. This module exists for deployments that already
run the DataBossX control API and want the Command Brain mounted alongside it.

It keeps the same posture as the stdlib server: loopback by default, exact-origin
CORS, a per-session CSRF token on mutating routes, and redaction on every
response body.
"""

from __future__ import annotations

from .redaction import redact
from .service import CommandBrain


def create_app(brain: CommandBrain, *, allowed_origins=("http://127.0.0.1:8787",), csrf_token: str | None = None):
    try:
        from fastapi import Body, FastAPI, Header, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "FastAPI is not installed. Use databossx.command_brain.server.serve() for the "
            "stdlib loopback Command Center instead."
        ) from exc

    import secrets

    token = csrf_token or secrets.token_urlsafe(24)
    app = FastAPI(title="DataBossX Command Brain", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    def _require_csrf(x_csrf_token: str | None) -> None:
        if x_csrf_token != token:
            raise HTTPException(status_code=403, detail="missing or invalid CSRF token")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "ledger": brain.store.verify_ledger()}

    @app.get("/api/state")
    def state():
        return brain.command_center_state()

    @app.get("/api/csrf")
    def csrf():
        return {"csrf_token": token}

    @app.post("/api/command")
    def command(payload: dict = Body(...), x_csrf_token: str = Header(None)):
        _require_csrf(x_csrf_token)
        response = brain.handle(
            str(payload.get("transcript", ""))[:4000], channel=str(payload.get("channel", "text"))
        )
        return response.to_dict()

    @app.post("/api/approve")
    def approve(payload: dict = Body(...), x_csrf_token: str = Header(None)):
        _require_csrf(x_csrf_token)
        try:
            approval = brain.approve(
                str(payload["envelope_id"]),
                approver_id=str(payload.get("approver_id", brain.requesting_user)),
                method="authenticated_api",
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=getattr(exc, "message", str(exc))) from exc
        return approval.to_dict()

    @app.post("/api/execute")
    def execute(payload: dict = Body(...), x_csrf_token: str = Header(None)):
        _require_csrf(x_csrf_token)
        try:
            return redact(brain.execute(str(payload["envelope_id"]), str(payload["approval_id"])))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=getattr(exc, "message", str(exc))) from exc

    return app
