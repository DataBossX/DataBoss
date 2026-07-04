"""Central configuration for the DataBossX Validation & Repair Agent.

All tunables, paths, and domain constants live here so no other module hard-codes
them. Paths resolve from the ``DATABOSSX_ROOT`` environment variable when present
(the production host is ``D:/Desktop/DataBossX``); otherwise they fall back to the
repository this file ships in, so the package is runnable in CI and on the host
without edits.
"""
from __future__ import annotations

import os
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Final

# --------------------------------------------------------------------------- #
# Roots
# --------------------------------------------------------------------------- #
_MODULE_DIR: Final[Path] = Path(__file__).resolve().parent


def _resolve_root() -> Path:
    env = os.environ.get("DATABOSSX_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    # Fall back to the repo root two levels up (…/scripts/validation_agent).
    return _MODULE_DIR.parent.parent


DATABOSSX_ROOT: Final[Path] = _resolve_root()
MODULE_ROOT: Final[Path] = _MODULE_DIR
OUTPUT_DIR: Final[Path] = _MODULE_DIR / "output"

# --------------------------------------------------------------------------- #
# Domain constants — Section 31-12N-24W, Roger Mills County, OK (Prospect 25-004)
# --------------------------------------------------------------------------- #
GROSS_ACRES: Final[float] = 637.42
# Nominal per-tract acreage used by the footing gate (order = Tract 1..10).
TRACT_ACREAGE: Final[dict[int, float]] = {
    1: 80.0, 2: 160.0, 3: 40.0, 4: 80.0, 5: 38.28,
    6: 51.0, 7: 40.0, 8: 32.8, 9: 75.34, 10: 40.0,
}
TRACT_NUMBERS: Final[tuple[int, ...]] = tuple(sorted(TRACT_ACREAGE))
WELL_API: Final[str] = "35-129-22925"  # Alexander 1-31

# --------------------------------------------------------------------------- #
# Tolerances
# --------------------------------------------------------------------------- #
EPSILON: Final[float] = 1e-9        # dimensionless interest tolerance (G1, G3)
ACRE_TOL: Final[float] = 0.01       # net-acre footing tolerance (G2)

# --------------------------------------------------------------------------- #
# Loop governance
# --------------------------------------------------------------------------- #
MAX_ITERATIONS: Final[int] = 25
NO_PROGRESS_PASSES: Final[int] = 2  # identical failure set across N passes -> escalate

# --------------------------------------------------------------------------- #
# Source verification (OKCountyRecords)
# --------------------------------------------------------------------------- #
API_SPEND_CAP_USD: Final[Decimal] = Decimal("100.00")
OKCR_BASE_URL: Final[str] = "https://okcountyrecords.com/api/v1"
OKCR_API_KEY_ENV: Final[str] = "OKCR_API_KEY"  # never hard-code the key
COUNTY: Final[str] = "Roger Mills"

# --------------------------------------------------------------------------- #
# External binaries
# --------------------------------------------------------------------------- #
def soffice_binary() -> str:
    """Locate the LibreOffice headless binary."""
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    # Common Windows install path on the DataBossX host.
    win = Path(r"C:/Program Files/LibreOffice/program/soffice.exe")
    if win.exists():
        return str(win)
    raise FileNotFoundError("LibreOffice (soffice) not found on PATH.")


CURL_BINARY: Final[str] = shutil.which("curl") or "curl"

# Excel/OOXML forbidden document types for report tabs (Runsheet/Tract/Title).
FORBIDDEN_DOC_TYPES: Final[tuple[str, ...]] = (
    "mortgage", "lien", "financing statement", "ucc",
    "right of way", "right-of-way", "easement",
)


def ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR
