"""Central configuration for the DataBossX Validation Agent.

Loads paths and environment variables, enforces the hard safety limits
(API spend cap <= $100.00, max iterations <= 5), and provides
secret-redacting config dumps.

Design note on paths: production defaults target the Windows layout
(D:\\Desktop\\DataBossX\\...). On any other platform (or when those paths do
not exist) the agent root is resolved relative to THIS file so the system is
fully runnable on Linux/macOS CI without editing anything.
"""

from __future__ import annotations

import os
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# --- Locate module root (this file lives in <agent_root>/config/settings.py) ---
_THIS_FILE = Path(__file__).resolve()
_MODULE_AGENT_ROOT = _THIS_FILE.parent.parent  # <agent_root>

# Load .env from the agent root if present (never fails if absent).
load_dotenv(_MODULE_AGENT_ROOT / ".env")

# Hard ceilings that are enforced regardless of environment input.
ABSOLUTE_API_CAP_USD = Decimal("100.00")
ABSOLUTE_MAX_ITERATIONS = 5

_SECRET_KEYS = {
    "OKCOUNTY_PASSWORD",
    "OKCOUNTY_USERNAME",
    "OKCOUNTY_API_KEY",
    "password",
    "secret",
    "token",
    "api_key",
}


def _to_bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on", "y"}


def _pick_agent_root() -> Path:
    """Return a usable agent-root path.

    Prefer an explicit env override if it exists on this machine; otherwise
    prefer the Windows production default if it exists; otherwise fall back to
    the module's own directory so the agent is always runnable.
    """
    env_val = os.getenv("DATABOSSX_AGENT_ROOT", "").strip()
    if env_val:
        p = Path(env_val)
        if p.exists():
            return p.resolve()
    # Windows production default
    win_default = Path(r"D:\Desktop\DataBossX\scripts\validation_agent")
    if win_default.exists():
        return win_default
    return _MODULE_AGENT_ROOT


class Settings:
    """Immutable-ish settings snapshot. Construct once via ``get_settings()``."""

    def __init__(self) -> None:
        self.agent_root: Path = _pick_agent_root()
        env_project = os.getenv("DATABOSSX_ROOT", "").strip()
        if env_project and Path(env_project).exists():
            self.project_root: Path = Path(env_project).resolve()
        else:
            # scripts/validation_agent -> project root is two levels up
            self.project_root = self.agent_root.parent.parent

        # --- Spend cap (clamped to the absolute ceiling) ---
        raw_cap = Decimal(str(os.getenv("DATABOSSX_API_CAP_USD", "100.00")))
        if raw_cap <= 0:
            raise ValueError("DATABOSSX_API_CAP_USD must be positive.")
        self.api_cap_usd: Decimal = min(raw_cap, ABSOLUTE_API_CAP_USD).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # --- Iterations (clamped to the absolute ceiling) ---
        raw_iter = int(os.getenv("DATABOSSX_MAX_ITERATIONS", "5"))
        if raw_iter < 1:
            raise ValueError("DATABOSSX_MAX_ITERATIONS must be >= 1.")
        self.max_iterations: int = min(raw_iter, ABSOLUTE_MAX_ITERATIONS)

        # --- Modes ---
        self.dry_run: bool = _to_bool(os.getenv("DATABOSSX_DRY_RUN"), default=True)
        self.live_source: bool = _to_bool(os.getenv("DATABOSSX_LIVE_SOURCE"), default=False)
        self.auto_approve_paid: bool = _to_bool(
            os.getenv("DATABOSSX_AUTO_APPROVE_PAID"), default=False
        )
        self.per_doc_limit_usd: Decimal = Decimal(
            str(os.getenv("DATABOSSX_PER_DOC_LIMIT_USD", "5.00"))
        ).quantize(Decimal("0.01"))

        # In dry-run, live source is always forced off.
        if self.dry_run:
            self.live_source = False

        # --- Reconciliation targets ---
        self.expected_acreage: Decimal = Decimal(
            str(os.getenv("DATABOSSX_EXPECTED_ACREAGE", "637.42"))
        )

        # --- Source credentials / endpoints ---
        self.okcounty_username: str = os.getenv("OKCOUNTY_USERNAME", "")
        self.okcounty_password: str = os.getenv("OKCOUNTY_PASSWORD", "")
        self.okcounty_api_base_url: str = os.getenv("OKCOUNTY_API_BASE_URL", "")
        self.okcounty_cost_per_search: Decimal = Decimal(
            str(os.getenv("OKCOUNTY_COST_PER_SEARCH", "0.10"))
        )
        self.okcounty_cost_per_document: Decimal = Decimal(
            str(os.getenv("OKCOUNTY_COST_PER_DOCUMENT", "1.00"))
        )

        # --- LibreOffice ---
        self.libreoffice_path: str = os.getenv("LIBREOFFICE_PATH", "")

        # --- Extra scan folders ---
        self.extra_source_dirs: list[Path] = self._split_dirs(
            os.getenv("DATABOSSX_EXTRA_SOURCE_DIRS", "")
        )
        self.extra_report_dirs: list[Path] = self._split_dirs(
            os.getenv("DATABOSSX_EXTRA_REPORT_DIRS", "")
        )

        # --- Derived paths ---
        self.outputs_dir: Path = self.agent_root / "outputs"
        self.db_path: Path = self.agent_root / "outputs" / "validation_agent.db"
        self.audit_log_path: Path = self.agent_root / "outputs" / "audit.log"
        self.fixtures_dir: Path = self.agent_root / "tests" / "fixtures"

    @staticmethod
    def _split_dirs(raw: str) -> list[Path]:
        out: list[Path] = []
        for part in raw.replace(",", ";").split(";"):
            part = part.strip()
            if part:
                out.append(Path(part))
        return out

    # ------------------------------------------------------------------ #
    def okcounty_configured(self) -> bool:
        return bool(
            self.okcounty_username
            and self.okcounty_password
            and self.okcounty_api_base_url
        )

    def ensure_dirs(self) -> None:
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        """Re-assert the invariants. Raises ValueError on violation."""
        if self.api_cap_usd > ABSOLUTE_API_CAP_USD:
            raise ValueError(
                f"API cap {self.api_cap_usd} exceeds absolute ceiling "
                f"{ABSOLUTE_API_CAP_USD}."
            )
        if self.max_iterations > ABSOLUTE_MAX_ITERATIONS:
            raise ValueError(
                f"max_iterations {self.max_iterations} exceeds absolute "
                f"ceiling {ABSOLUTE_MAX_ITERATIONS}."
            )
        if self.dry_run and self.live_source:
            raise ValueError("live_source must be False when dry_run is True.")

    def safe_dump(self) -> dict[str, Any]:
        """Config dump with secrets redacted (safe to log/print)."""
        return {
            "agent_root": str(self.agent_root),
            "project_root": str(self.project_root),
            "outputs_dir": str(self.outputs_dir),
            "db_path": str(self.db_path),
            "api_cap_usd": str(self.api_cap_usd),
            "absolute_api_cap_usd": str(ABSOLUTE_API_CAP_USD),
            "max_iterations": self.max_iterations,
            "dry_run": self.dry_run,
            "live_source": self.live_source,
            "auto_approve_paid": self.auto_approve_paid,
            "per_doc_limit_usd": str(self.per_doc_limit_usd),
            "expected_acreage": str(self.expected_acreage),
            "okcounty_username": self._redact(self.okcounty_username),
            "okcounty_password": self._redact(self.okcounty_password),
            "okcounty_api_base_url": self.okcounty_api_base_url or "(unset)",
            "okcounty_configured": self.okcounty_configured(),
            "libreoffice_path": self.libreoffice_path or "(auto-detect)",
        }

    @staticmethod
    def _redact(value: str) -> str:
        if not value:
            return "(unset)"
        return "***REDACTED***"


_SETTINGS: Settings | None = None


def get_settings(refresh: bool = False) -> Settings:
    """Return the process-wide settings singleton."""
    global _SETTINGS
    if _SETTINGS is None or refresh:
        _SETTINGS = Settings()
        _SETTINGS.validate()
    return _SETTINGS


if __name__ == "__main__":
    import json

    s = get_settings()
    print(json.dumps(s.safe_dump(), indent=2))
