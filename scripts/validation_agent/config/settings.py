"""
Central configuration for the DataBossX Validation Agent.

Design goals:
* Path-aware: honours DATABOSSX_AGENT_ROOT when the folder exists (the Windows
  target), otherwise resolves paths from this file's location so the same code
  runs on Linux/CI unchanged.
* Hard safety ceilings: API spend cap can never exceed $100.00 and iterations
  can never exceed 5, regardless of what the environment asks for.
* Secret-safe: config dumps redact credentials.
* Zero third-party import cost so the critical path always loads.

No secrets are ever stored in source or printed.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Optional

# Try to load a .env if python-dotenv is available; never required.
try:  # pragma: no cover - trivial import guard
    from dotenv import load_dotenv
    _AGENT_DIR = Path(__file__).resolve().parents[1]
    load_dotenv(_AGENT_DIR / ".env")
except Exception:  # pragma: no cover
    pass


# ---- Hard ceilings. These are LAW and cannot be widened by env vars. ----
ABSOLUTE_SPEND_CAP_USD = Decimal("100.00")
ABSOLUTE_MAX_ITERATIONS = 5

_SECRET_KEYS = {"OKCOUNTY_USERNAME", "OKCOUNTY_PASSWORD"}


def _resolve_agent_root() -> Path:
    """Prefer the configured Windows root if it exists; else derive locally."""
    env_root = os.environ.get("DATABOSSX_AGENT_ROOT", "").strip()
    if env_root:
        p = Path(env_root)
        if p.exists():
            return p
    # Fall back to the directory that contains this module's parent.
    return Path(__file__).resolve().parents[1]


def _to_decimal(value: str, default: Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _to_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    agent_root: Path
    project_root: Path
    # caps (already clamped to absolute ceilings)
    api_cap_usd: Decimal
    max_iterations: int
    # modes
    dry_run: bool
    live_source: bool
    auto_approve_paid: bool
    per_document_limit_usd: Decimal
    expected_acreage: Decimal
    # okcounty
    okcounty_username: str
    okcounty_password: str
    okcounty_base_url: str
    okcounty_cost_per_search: Decimal
    okcounty_cost_per_image: Decimal
    # libreoffice
    libreoffice_path: str

    # ---- Derived paths ----
    @property
    def outputs_dir(self) -> Path:
        return self.agent_root / "outputs"

    @property
    def db_path(self) -> Path:
        return self.agent_root / "db" / "validation_agent.sqlite3"

    @property
    def fixtures_dir(self) -> Path:
        return self.agent_root / "tests" / "fixtures"

    def ensure_dirs(self) -> None:
        for p in (self.outputs_dir, self.db_path.parent):
            p.mkdir(parents=True, exist_ok=True)

    # ---- Safety helpers ----
    def live_enabled(self) -> bool:
        """Live source calls require BOTH live_source on AND dry_run off."""
        return self.live_source and not self.dry_run

    def safe_dump(self) -> Dict[str, Any]:
        """Config snapshot with secrets redacted. Safe to log/print."""
        d = asdict(self)
        # stringify non-JSON-native types
        for k, v in list(d.items()):
            if isinstance(v, (Path, Decimal)):
                d[k] = str(v)
        d["okcounty_username"] = "***REDACTED***" if self.okcounty_username else "(unset)"
        d["okcounty_password"] = "***REDACTED***" if self.okcounty_password else "(unset)"
        d["live_enabled"] = self.live_enabled()
        d["absolute_spend_cap_usd"] = str(ABSOLUTE_SPEND_CAP_USD)
        d["absolute_max_iterations"] = ABSOLUTE_MAX_ITERATIONS
        return d


def load_settings(env: Optional[Dict[str, str]] = None) -> Settings:
    """Build Settings from the environment, clamped to absolute ceilings."""
    e = dict(os.environ)
    if env:
        e.update(env)

    agent_root = _resolve_agent_root()
    project_root_env = e.get("DATABOSSX_ROOT", "").strip()
    project_root = Path(project_root_env) if project_root_env and Path(project_root_env).exists() \
        else agent_root.parents[1] if len(agent_root.parents) >= 2 else agent_root

    # Requested cap, clamped so it can never exceed the absolute ceiling.
    requested_cap = _to_decimal(e.get("DATABOSSX_API_CAP_USD", "100.00"), ABSOLUTE_SPEND_CAP_USD)
    api_cap = min(requested_cap, ABSOLUTE_SPEND_CAP_USD)
    if api_cap < 0:
        api_cap = Decimal("0")

    requested_iter = e.get("DATABOSSX_MAX_ITERATIONS", "5")
    try:
        max_iter = int(requested_iter)
    except (ValueError, TypeError):
        max_iter = ABSOLUTE_MAX_ITERATIONS
    max_iter = max(1, min(max_iter, ABSOLUTE_MAX_ITERATIONS))

    return Settings(
        agent_root=agent_root,
        project_root=project_root,
        api_cap_usd=api_cap,
        max_iterations=max_iter,
        dry_run=_to_bool(e.get("DATABOSSX_DRY_RUN"), True),
        live_source=_to_bool(e.get("DATABOSSX_LIVE_SOURCE"), False),
        auto_approve_paid=_to_bool(e.get("DATABOSSX_AUTO_APPROVE_PAID"), False),
        per_document_limit_usd=_to_decimal(e.get("DATABOSSX_PER_DOCUMENT_LIMIT_USD", "5.00"), Decimal("5.00")),
        expected_acreage=_to_decimal(e.get("DATABOSSX_EXPECTED_ACREAGE", "637.42"), Decimal("637.42")),
        okcounty_username=e.get("OKCOUNTY_USERNAME", "").strip(),
        okcounty_password=e.get("OKCOUNTY_PASSWORD", "").strip(),
        okcounty_base_url=e.get("OKCOUNTY_API_BASE_URL", "").strip(),
        okcounty_cost_per_search=_to_decimal(e.get("OKCOUNTY_COST_PER_SEARCH", "0.10"), Decimal("0.10")),
        okcounty_cost_per_image=_to_decimal(e.get("OKCOUNTY_COST_PER_IMAGE", "0.50"), Decimal("0.50")),
        libreoffice_path=e.get("LIBREOFFICE_PATH", "").strip(),
    )


# Module-level singleton for convenience.
settings = load_settings()
