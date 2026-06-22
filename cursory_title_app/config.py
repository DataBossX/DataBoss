"""Central configuration for the Cursory Title App.

Local-first. Secrets come from environment / .env only — never hardcoded.
Everything is path-configurable so the app can run from a Windows .bat launcher.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is optional; env vars still work
    pass

# --- Project target: Section 31, Township 12N, Range 24W (Roger Mills County, OK)
TARGET_SECTION = os.getenv("TARGET_SECTION", "31")
TARGET_TOWNSHIP = os.getenv("TARGET_TOWNSHIP", "12N")
TARGET_RANGE = os.getenv("TARGET_RANGE", "24W")
TARGET_COUNTY = os.getenv("TARGET_COUNTY", "Roger Mills")

# --- Workbook identity guards -------------------------------------------------
# Exact tab names that MUST exist and MUST NOT be added to / renamed / reordered.
# NOTE: "Title " carries a trailing space in the real workbook. Do not "fix" it.
EXPECTED_TABS = [
    "Overview", "Title ", "PLAT", "OGLs", "Runsheet",
    "Tract 1", "Tract 2", "Tract 3", "Tract 4",
    "Tract 5", "Tract 6", "Tract 7", "Tract 8",
    "WI 1", "WI 2", "Wells",
    "Title_BACKUP", "Runsheet_BACKUP",
]
RUNSHEET_TAB = "Runsheet"

# --- Storage / local-first paths ---------------------------------------------
APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("CTA_DATA_DIR", APP_ROOT / "_data"))
OUTPUT_DIR = Path(os.getenv("CTA_OUTPUT_DIR", DATA_DIR / "output"))
BACKUP_DIR = Path(os.getenv("CTA_BACKUP_DIR", DATA_DIR / "backups"))
EVIDENCE_DIR = Path(os.getenv("CTA_EVIDENCE_DIR", DATA_DIR / "evidence"))
PAGES_DIR = Path(os.getenv("CTA_PAGES_DIR", DATA_DIR / "index_pages"))
DB_PATH = Path(os.getenv("CTA_DB_PATH", DATA_DIR / "cursory_title.db"))
AUDIT_LOG = Path(os.getenv("CTA_AUDIT_LOG", DATA_DIR / "audit.jsonl"))

# --- Model abstraction --------------------------------------------------------
# Which provider answers vision/extraction requests, in priority order.
# First configured provider wins; the rest are fallbacks.
MODEL_PROVIDER_ORDER = [
    p.strip() for p in os.getenv("CTA_MODEL_ORDER", "claude,openai").split(",") if p.strip()
]
CLAUDE_MODEL = os.getenv("CTA_CLAUDE_MODEL", "claude-opus-4-8")
OPENAI_MODEL = os.getenv("CTA_OPENAI_MODEL", "gpt-4o")

# Below this confidence, the app refuses to write authoritative values and
# routes the row to manual review (NEED/VERIFY flags only).
CONFIDENCE_REVIEW_THRESHOLD = float(os.getenv("CTA_CONFIDENCE_THRESHOLD", "0.80"))

# --- Browser ------------------------------------------------------------------
# We CONNECT to the user's already-open, logged-in Chrome/Edge over CDP.
# Start Chrome with:  chrome.exe --remote-debugging-port=9222
CDP_URL = os.getenv("CTA_CDP_URL", "http://127.0.0.1:9222")
BROWSER_DOWNLOAD_DIR = Path(os.getenv("CTA_BROWSER_DOWNLOADS", DATA_DIR / "downloads"))


def ensure_dirs() -> None:
    for d in (DATA_DIR, OUTPUT_DIR, BACKUP_DIR, EVIDENCE_DIR, PAGES_DIR,
              BROWSER_DOWNLOAD_DIR):
        d.mkdir(parents=True, exist_ok=True)
