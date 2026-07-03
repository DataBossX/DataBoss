"""Configuration + Golden-Rule constants for TitleFinisher."""
from __future__ import annotations
import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # dotenv optional
    pass

# The exact 19-sheet structure a compliant NHE cursory workbook must keep (byte-identical
# names, this order, all visible). Note the trailing space in "Title ".
REQUIRED_SHEETS = [
    "Overview", "Title ", "OGL", "PLAT", "Runsheet",
    "Tract 1", "Tract 2", "Tract 3", "Tract 4", "Tract 5",
    "Tract 6", "Tract 7", "Tract 8", "Tract 9", "Tract 10",
    "WI 1", "WI 2", "Well 1", "rawdata",
]

# Instrument types that must NEVER appear as rows/owners on Runsheet, Tract, or Title
# (the report's hard content-exclusion rule). Administrative items like Change of Address
# or Affidavit are NOT in this set — the examiner keeps those.
REMOVAL_EXCLUDED_RX = (
    r"(?i)mortgage|release of mortgage|\bMTG\b|\blien\b|\bUCC\b|financing (stmt|statement)|"
    r"right.of.way|\bROW\b|easement|subordination|partial release"
)

# Broader set the source-in resolver must NOT treat as a vesting (grantee-side) instrument.
NON_VESTING_RX = REMOVAL_EXCLUDED_RX + r"|change of address"

# Back-compat alias.
EXCLUDED_TYPE_RX = REMOVAL_EXCLUDED_RX

YELLOW = "FFFF00"  # source-in-gap highlight convention


@dataclass
class Config:
    okcr_api_key: str = field(default_factory=lambda: os.getenv("OKCR_API_KEY", ""))
    user_agent: str = field(default_factory=lambda: os.getenv(
        "REQUEST_USER_AGENT", "TitleFinisher/1.0"))
    county: str = field(default_factory=lambda: os.getenv("COUNTY", "Roger Mills"))
    twprge: str = field(default_factory=lambda: os.getenv("TWPRGE", "12N-24W"))
    section: str = field(default_factory=lambda: os.getenv("SECTION", "31"))
    tesseract_cmd: str = field(default_factory=lambda: os.getenv("TESSERACT_CMD", ""))

    def require_key(self) -> None:
        if not self.okcr_api_key:
            raise SystemExit(
                "OKCR_API_KEY is not set. Copy .env.example to .env and add your "
                "okcountyrecords.com API key, or export OKCR_API_KEY.")
