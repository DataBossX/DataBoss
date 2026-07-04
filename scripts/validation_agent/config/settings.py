"""Central configuration for the DataBossX Validation Agent.

Design rules enforced here:
  * The API spend cap can never exceed $100.00 (it may only be made stricter).
  * Max iterations can never exceed 5.
  * Secrets are never returned by ``safe_dump`` / ``__repr__``.
  * Paths are cross-platform: they honor explicit env overrides (the Windows
    canonical roots) but fall back to the package location so the agent runs
    identically on Linux/CI.
  * Dry-run is the default; live source retrieval is opt-in and gated twice
    (``live_source_mode`` AND ``dry_run is False``).
"""
from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # dotenv is optional at import time; healthcheck reports if missing.
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - only if dependency missing
    def load_dotenv(*_a, **_k):  # type: ignore
        return False

# Absolute hard ceilings. These are law and cannot be widened by env or code.
HARD_API_CAP_USD = Decimal("100.00")
HARD_MAX_ITERATIONS = 5
SECRET_ENV_KEYS = {"OKCOUNTY_USERNAME", "OKCOUNTY_PASSWORD", "OKCOUNTY_API_BASE_URL"}

# The agent root is the parent of this ``config`` package (…/validation_agent).
_PACKAGE_AGENT_ROOT = Path(__file__).resolve().parent.parent


def _to_decimal(raw: Optional[str], default: Decimal) -> Decimal:
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        return default


def _to_int(raw: Optional[str], default: int) -> int:
    try:
        return int(str(raw).strip())
    except (ValueError, TypeError):
        return default


def _to_bool(raw: Optional[str], default: bool) -> bool:
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on", "y"}


class Settings:
    """Immutable-ish settings snapshot. Read once, use everywhere."""

    def __init__(self, env_file: Optional[Path] = None) -> None:
        # Load .env if present (does not override already-exported vars).
        self.agent_root: Path = self._resolve_agent_root()
        candidate_env = env_file or (self.agent_root / ".env")
        if candidate_env and Path(candidate_env).is_file():
            load_dotenv(candidate_env, override=False)
            self.env_file_loaded: Optional[str] = str(candidate_env)
        else:
            self.env_file_loaded = None

        # Re-resolve root now that .env may define it.
        self.agent_root = self._resolve_agent_root()
        self.project_root: Path = self._resolve_project_root()

        # Financial + loop caps, clamped to the hard ceilings.
        requested_cap = _to_decimal(os.getenv("DATABOSSX_API_CAP_USD"), HARD_API_CAP_USD)
        self.api_cap_usd: Decimal = min(requested_cap, HARD_API_CAP_USD)
        if self.api_cap_usd < Decimal("0"):
            self.api_cap_usd = Decimal("0")

        requested_iter = _to_int(os.getenv("DATABOSSX_MAX_ITERATIONS"), HARD_MAX_ITERATIONS)
        self.max_iterations: int = max(1, min(requested_iter, HARD_MAX_ITERATIONS))

        # Modes.
        self.dry_run: bool = _to_bool(os.getenv("DATABOSSX_DRY_RUN"), True)
        self.live_source_mode: bool = _to_bool(os.getenv("DATABOSSX_LIVE_SOURCE_MODE"), False)
        self.auto_approve_paid: bool = _to_bool(os.getenv("DATABOSSX_AUTO_APPROVE_PAID"), False)
        self.per_doc_limit_usd: Decimal = min(
            _to_decimal(os.getenv("DATABOSSX_PER_DOC_LIMIT_USD"), Decimal("10.00")),
            self.api_cap_usd,
        )

        # Domain expectations.
        self.expected_acres: Decimal = _to_decimal(
            os.getenv("DATABOSSX_EXPECTED_ACRES"), Decimal("637.42")
        )

        # External services (secret-bearing).
        self.okcounty_username: Optional[str] = os.getenv("OKCOUNTY_USERNAME") or None
        self.okcounty_password: Optional[str] = os.getenv("OKCOUNTY_PASSWORD") or None
        self.okcounty_api_base_url: Optional[str] = os.getenv("OKCOUNTY_API_BASE_URL") or None
        self.libreoffice_path: Optional[str] = os.getenv("LIBREOFFICE_PATH") or None

        # Extra search dirs.
        self.extra_source_dirs: List[Path] = self._split_paths(
            os.getenv("DATABOSSX_EXTRA_SOURCE_DIRS")
        )
        self.extra_report_dirs: List[Path] = self._split_paths(
            os.getenv("DATABOSSX_EXTRA_REPORT_DIRS")
        )

        # Derived paths (all under the agent root — nothing clutters project root).
        self.outputs_dir: Path = self.agent_root / "outputs"
        self.db_path: Path = self.agent_root / "db" / "validation_agent.sqlite3"
        self.schema_path: Path = self.agent_root / "db" / "schema.sql"

    # ------------------------------------------------------------------ paths
    def _resolve_agent_root(self) -> Path:
        override = os.getenv("DATABOSSX_AGENT_ROOT")
        if override and Path(override).parent.exists():
            # Honor the override even if the leaf dir does not exist yet.
            return Path(override)
        return _PACKAGE_AGENT_ROOT

    def _resolve_project_root(self) -> Path:
        override = os.getenv("DATABOSSX_ROOT")
        if override and Path(override).parent.exists():
            return Path(override)
        # scripts/validation_agent -> project root is two levels up when that
        # matches; otherwise fall back to the agent root's grandparent.
        parent = self.agent_root.parent
        if parent.name == "scripts":
            return parent.parent
        return parent

    @staticmethod
    def _split_paths(raw: Optional[str]) -> List[Path]:
        if not raw:
            return []
        return [Path(p) for p in raw.split(os.pathsep) if p.strip()]

    # ------------------------------------------------------------- validation
    def credentials_present(self) -> bool:
        return bool(self.okcounty_username and self.okcounty_password and self.okcounty_api_base_url)

    def live_retrieval_allowed(self) -> bool:
        """Live paid/free retrieval requires ALL of: not dry-run, live mode, creds."""
        return (not self.dry_run) and self.live_source_mode and self.credentials_present()

    # -------------------------------------------------------------- dumping
    def safe_dump(self) -> Dict[str, Any]:
        """Config dump with secrets redacted — safe for logs, DB and UI."""

        def red(v: Optional[str]) -> str:
            return "***REDACTED***" if v else "(unset)"

        return {
            "agent_root": str(self.agent_root),
            "project_root": str(self.project_root),
            "outputs_dir": str(self.outputs_dir),
            "db_path": str(self.db_path),
            "env_file_loaded": self.env_file_loaded or "(none)",
            "api_cap_usd": str(self.api_cap_usd),
            "hard_api_cap_usd": str(HARD_API_CAP_USD),
            "max_iterations": self.max_iterations,
            "hard_max_iterations": HARD_MAX_ITERATIONS,
            "dry_run": self.dry_run,
            "live_source_mode": self.live_source_mode,
            "auto_approve_paid": self.auto_approve_paid,
            "per_doc_limit_usd": str(self.per_doc_limit_usd),
            "expected_acres": str(self.expected_acres),
            "okcounty_username": red(self.okcounty_username),
            "okcounty_password": red(self.okcounty_password),
            "okcounty_api_base_url": red(self.okcounty_api_base_url),
            "libreoffice_path": self.libreoffice_path or "(auto-detect)",
            "credentials_present": self.credentials_present(),
            "live_retrieval_allowed": self.live_retrieval_allowed(),
        }

    def __repr__(self) -> str:  # never leak secrets
        return f"Settings(agent_root={self.agent_root!s}, dry_run={self.dry_run}, cap={self.api_cap_usd})"


_CACHED: Optional[Settings] = None


def get_settings(reload: bool = False, env_file: Optional[Path] = None) -> Settings:
    global _CACHED
    if _CACHED is None or reload:
        _CACHED = Settings(env_file=env_file)
    return _CACHED
