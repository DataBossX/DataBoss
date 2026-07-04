"""Configuration loader: paths, environment, thresholds, and the $100 cap.

Everything the system treats as a constant lives here so the audit trail can
record the exact configuration a run executed under.  Nothing here reaches out
to a network or a paid API -- it only reads local environment and disk.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Repo-relative anchor.  The architect's blueprint references a Windows path
# (D:/Desktop/DataBossX/scripts/validation_agent); inside this repository that
# maps to the directory this package lives in.  The env var lets an operator
# override it on the real Windows deployment without editing code.
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ROOT = Path(os.getenv("DATABOSSX_ROOT", str(_PACKAGE_ROOT)))


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    # --- Filesystem layout -------------------------------------------------
    root: Path = _DEFAULT_ROOT
    outputs_dir: Path = field(default_factory=lambda: _DEFAULT_ROOT / "outputs")
    db_path: Path = field(default_factory=lambda: _DEFAULT_ROOT / "outputs" / "validation_memory.db")
    schema_path: Path = field(default_factory=lambda: _PACKAGE_ROOT / "db" / "schema.sql")

    # --- The $100 hard mathematical ceiling (Golden Law #6) ----------------
    api_hard_cap_usd: float = field(default_factory=lambda: _get_float("DATABOSSX_API_CAP", 100.00))
    okcounty_cost_per_image: float = field(default_factory=lambda: _get_float("OKCOUNTY_COST_PER_IMAGE", 1.00))
    okcounty_cost_per_search: float = field(default_factory=lambda: _get_float("OKCOUNTY_COST_PER_SEARCH", 0.00))

    # --- OKCountyRecords endpoint (user's own subscription) ----------------
    okcounty_base_url: str = field(default_factory=lambda: os.getenv(
        "OKCOUNTY_API_BASE_URL", "https://api.okcountyrecords.com"))
    okcounty_username_env: str = "OKCOUNTY_USERNAME"
    okcounty_password_env: str = "OKCOUNTY_PASSWORD"
    # Fallback county for source lookups when a row/sheet does not name one.
    default_county: str = field(default_factory=lambda: os.getenv(
        "DATABOSSX_COUNTY", ""))
    curl_binary: str = field(default_factory=lambda: os.getenv("DATABOSSX_CURL", "curl"))
    curl_user_agent: str = field(default_factory=lambda: os.getenv(
        "DATABOSSX_UA", "Mozilla/5.0 (DataBossX-ValidationAgent/1.0)"))

    # --- LibreOffice headless recalculation --------------------------------
    soffice_binary: str = field(default_factory=lambda: os.getenv("DATABOSSX_SOFFICE", "soffice"))
    recalc_timeout_sec: int = field(default_factory=lambda: _get_int("DATABOSSX_RECALC_TIMEOUT", 180))

    # --- Perfection loop control (Section 4) -------------------------------
    max_iterations: int = field(default_factory=lambda: _get_int("DATABOSSX_MAX_ITER", 5))

    # --- Static validation thresholds (Section 5) --------------------------
    # Total gross acreage the tract footing must reconcile to, exactly.
    expected_total_acreage: float = field(default_factory=lambda: _get_float(
        "DATABOSSX_TOTAL_ACRES", 637.42))
    # Denominator used to snap fractions to exact rational math (1/N granularity
    # covers the standard mineral-interest denominators without float drift).
    interest_tolerance: float = field(default_factory=lambda: _get_float(
        "DATABOSSX_INTEREST_TOL", 1e-9))
    acreage_tolerance: float = field(default_factory=lambda: _get_float(
        "DATABOSSX_ACRE_TOL", 0.005))
    # Number of core tracts the classifier expects (Section 5, Gate 2).
    expected_tract_count: int = field(default_factory=lambda: _get_int(
        "DATABOSSX_TRACT_COUNT", 10))

    def okcounty_username(self) -> str:
        return os.getenv(self.okcounty_username_env, "")

    def okcounty_password(self) -> str:
        return os.getenv(self.okcounty_password_env, "")

    def okcounty_configured(self) -> bool:
        return bool(self.okcounty_username() and self.okcounty_password())


config = Settings()
