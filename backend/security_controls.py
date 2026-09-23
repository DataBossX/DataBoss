"""Fail-closed controls for the legacy demo backend.

This module is standalone so tests can import it without optional OCR/LLM
clients. The demo backend is scheduled for retirement; until then it must
never process real client uploads or invent legal facts.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_BIND = "127.0.0.1"
DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_UPLOAD_SUFFIXES = {".txt", ".md", ".pdf", ".png", ".jpg", ".jpeg"}
PUBLIC_PATHS = {"/api/health", "/healthz", "/docs", "/openapi.json", "/redoc"}
PROTECTED_PREFIXES = ("/api/documents", "/api/logs", "/api/analytics")


class SecurityError(Exception):
    def __init__(self, code: str, message: str = "request rejected"):
        super().__init__(message)
        self.code = code
        self.message = message


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def demo_mode_enabled() -> bool:
    return env_flag("DATABOSSX_DEMO_MODE", False)


def auth_token() -> str:
    return (os.getenv("DATABOSSX_DEMO_TOKEN") or "").strip()


def cors_origins() -> list[str]:
    raw = os.getenv("DATABOSSX_CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS))
    origins = [part.strip() for part in raw.split(",") if part.strip()]
    if "*" in origins:
        raise SecurityError("WILDCARD_CORS_FORBIDDEN", "wildcard CORS is not allowed")
    return origins or list(DEFAULT_CORS_ORIGINS)


def bind_host() -> str:
    host = (os.getenv("DATABOSSX_BIND") or DEFAULT_BIND).strip() or DEFAULT_BIND
    if host in {"0.0.0.0", "::", "[::]"} and not env_flag("DATABOSSX_ALLOW_NONLOCAL_BIND"):
        return DEFAULT_BIND
    return host


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS


def is_protected_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in PROTECTED_PREFIXES)


def _lower_headers(headers: dict[str, str] | None) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in (headers or {}).items()}


def authorized(headers: dict[str, str] | None) -> bool:
    token = auth_token()
    if not token:
        return False
    headers = _lower_headers(headers)
    bearer = headers.get("authorization", "")
    if bearer.lower().startswith("bearer ") and bearer.split(" ", 1)[1].strip() == token:
        return True
    return headers.get("x-databossx-demo-token", "").strip() == token


def is_synthetic_upload(filename: str | None, headers: dict[str, str] | None) -> bool:
    name = Path(filename or "").name
    headers = _lower_headers(headers)
    if headers.get("x-databossx-synthetic", "").strip() == "1":
        return True
    return name.upper().startswith("SYNTHETIC_")


def validate_upload(filename: str | None, size: int, headers: dict[str, str] | None) -> None:
    if size <= 0 or size > MAX_UPLOAD_BYTES:
        raise SecurityError("UPLOAD_REJECTED")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise SecurityError("UPLOAD_REJECTED")
    if not demo_mode_enabled():
        raise SecurityError("REAL_UPLOAD_REFUSED")
    if not is_synthetic_upload(filename, headers):
        raise SecurityError("REAL_UPLOAD_REFUSED")


def mock_ocr_allowed(filename: str | None, headers: dict[str, str] | None) -> bool:
    return demo_mode_enabled() and is_synthetic_upload(filename, headers)


def synthetic_ocr_placeholder(filename: str) -> str:
    return (
        "SYNTHETIC_DEMO_PLACEHOLDER\n"
        "This is not a legal document, title opinion, or extracted fact.\n"
        f"source_filename={Path(filename).name}\n"
        "parties=\n"
        "dates=\n"
        "legal_description=\n"
    )
