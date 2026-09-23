"""Fail-closed controls for the legacy demo backend.

This module is import-safe without OCR/LLM clients so integrity tests can
prove authentication, CORS, demo-mode, and upload limits without starting a
live server.
"""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_CORS_ORIGINS = ("http://127.0.0.1:3000", "http://localhost:3000")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_SUFFIXES = frozenset(
    {".txt", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".md"}
)
AUTH_HEADER = "X-DataBossX-Token"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def demo_mode_enabled() -> bool:
    return _env("DATABOSSX_DEMO_MODE") == "1"


def api_token() -> str:
    return _env("DATABOSSX_API_TOKEN")


def cors_origins() -> list[str]:
    raw = _env("DATABOSSX_CORS_ORIGINS")
    if not raw:
        return list(DEFAULT_CORS_ORIGINS)
    origins = [part.strip() for part in raw.split(",") if part.strip()]
    if "*" in origins:
        raise ValueError("wildcard CORS origins are forbidden when credentials are enabled")
    return origins


def bind_host() -> str:
    host = _env("DATABOSSX_BIND_HOST", "127.0.0.1") or "127.0.0.1"
    if host in {"0.0.0.0", "::"}:
        raise ValueError("legacy backend must bind loopback only")
    return host


def authenticate(provided_token: str | None) -> tuple[bool, str]:
    expected = api_token()
    if not expected:
        return False, "unauthenticated access is disabled"
    if provided_token != expected:
        return False, "unauthorized"
    return True, "ok"


def validate_upload(filename: str | None, size: int) -> tuple[bool, str]:
    if size <= 0:
        return False, "empty upload refused"
    if size > MAX_UPLOAD_BYTES:
        return False, "file exceeds size limit"
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        return False, "file type is not allowed"
    return True, "ok"


def mock_ocr_allowed() -> tuple[bool, str]:
    if not demo_mode_enabled():
        return False, "mock OCR is disabled outside explicit synthetic/demo mode"
    return True, "demo"


def demo_ocr_payload(filename: str) -> dict:
    """Synthetic placeholder only. Never emits invented legal facts."""
    return {
        "raw_text": "",
        "cleaned_text": "",
        "confidence_score": 0.0,
        "processing_time": 0.0,
        "ocr_engine": "demo_disabled_facts",
        "synthetic": True,
        "filename": filename,
        "note": "demo mode produces no parties, dates, or legal conclusions",
    }
