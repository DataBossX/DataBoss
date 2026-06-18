"""Central, typed configuration for the DataBossX backend.

Single source of truth for runtime settings, loaded from environment variables
with safe defaults. Kept dependency-light (stdlib only) so it can be imported
and unit-tested without the heavy LLM/OCR stack.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Set


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, float(default)))


@dataclass(frozen=True)
class Settings:
    """Resolved backend settings. Construct via :meth:`from_env`."""

    # Database
    db_path: str = "./databossx.db"

    # CORS
    cors_origins: List[str] = field(default_factory=lambda: ["http://localhost:3000"])

    # Uploads
    max_upload_bytes: int = 25 * 1024 * 1024
    # Empty set means "allow any extension". Defaults to common document/image
    # types appropriate for an OCR pipeline.
    allowed_upload_extensions: Set[str] = field(
        default_factory=lambda: {
            ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff",
            ".bmp", ".gif", ".webp", ".txt",
        }
    )

    # Rate limiting (per client IP, sliding window) for write endpoints
    rate_limit_max: int = 60
    rate_limit_window_sec: float = 60.0

    # Logging
    log_path: str = "logs/databossx.log"
    log_level: str = "INFO"

    # LLM provider keys (presence only; never logged)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    @property
    def allow_credentials(self) -> bool:
        # Per the CORS spec, credentials cannot be combined with a wildcard.
        return "*" not in self.cors_origins

    @property
    def max_upload_mb(self) -> int:
        return self.max_upload_bytes // (1024 * 1024)

    @classmethod
    def from_env(cls) -> "Settings":
        cors_raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000")
        cors = _split_csv(cors_raw) or ["http://localhost:3000"]

        ext_raw = os.getenv("ALLOWED_UPLOAD_EXTENSIONS")
        if ext_raw is not None:
            exts = {
                (e if e.startswith(".") else f".{e}").lower()
                for e in _split_csv(ext_raw)
            }
        else:
            exts = cls.__dataclass_fields__[
                "allowed_upload_extensions"
            ].default_factory()  # type: ignore[attr-defined]

        return cls(
            db_path=os.getenv("SQLITE_DB_PATH", "./databossx.db"),
            cors_origins=cors,
            max_upload_bytes=int(_env_float("MAX_UPLOAD_MB", 25.0) * 1024 * 1024),
            allowed_upload_extensions=exts,
            rate_limit_max=_env_int("RATE_LIMIT_MAX", 60),
            rate_limit_window_sec=_env_float("RATE_LIMIT_WINDOW_SEC", 60.0),
            log_path=os.getenv("LOG_PATH", "logs/databossx.log"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        )

    def validate(self) -> List[str]:
        """Return a list of human-readable warnings (non-fatal)."""
        warnings: List[str] = []
        if self.max_upload_bytes <= 0:
            warnings.append("MAX_UPLOAD_MB resolved to <= 0; uploads will fail.")
        if "*" in self.cors_origins and len(self.cors_origins) > 1:
            warnings.append("CORS wildcard '*' mixed with explicit origins.")
        if self.rate_limit_max <= 0:
            warnings.append("RATE_LIMIT_MAX <= 0; rate limiting disabled.")
        if not any(
            [self.openai_api_key, self.anthropic_api_key, self.gemini_api_key]
        ):
            warnings.append(
                "No LLM API keys configured; analysis features are disabled."
            )
        return warnings

    def configured_providers(self) -> List[str]:
        providers = []
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.gemini_api_key:
            providers.append("gemini")
        return providers
