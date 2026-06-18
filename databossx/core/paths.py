"""Central path + timestamp helpers for DataBossX.

Single source of truth for where artifacts live so every tool writes to a
predictable, gitignore-able location. No secrets ever live here.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

# Project root = two levels up from this file (databossx/core/paths.py -> repo root)
ROOT = Path(__file__).resolve().parents[2]

REPORTS = ROOT / "reports"
LOGS = ROOT / "logs"
BACKUPS = ROOT / "backups"
DIAGNOSTICS = ROOT / "diagnostics"
ROLLBACK = ROOT / "rollback"
MEMORY = ROOT / "memory"
REVIEW_OUTPUTS = ROOT / "review_outputs"

# Directories that must never be backed up, mapped, or committed.
# Matched by path-part name anywhere in the tree.
EXCLUDED_DIR_NAMES = {
    ".git", ".auth", ".venv", "venv", "node_modules", "__pycache__",
    "backups", "rollback", "diagnostics", "logs", ".cache", "dist", "build",
    "cookies", ".next", ".idea", ".vscode", "memory",
}

# File patterns that must never be backed up, mapped, or committed.
EXCLUDED_FILE_GLOBS = (
    ".env", "*.env", ".env.*", "*.auth", "*.pem", "*token.json*",
    "*credentials.json*", "*.sqlite3", "*.db", "*.log", "*.zip",
)

ALL_ARTIFACT_DIRS = (REPORTS, LOGS, BACKUPS, DIAGNOSTICS, ROLLBACK, MEMORY, REVIEW_OUTPUTS)


def timestamp() -> str:
    """Filesystem-safe UTC timestamp: YYYYMMDD_HHMMSS."""
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dirs() -> None:
    for d in ALL_ARTIFACT_DIRS:
        d.mkdir(parents=True, exist_ok=True)


def is_excluded(path: Path) -> bool:
    """True if path is inside an excluded dir or matches an excluded file glob.

    Exception: an .env.example file is allowed (it is a safe template).
    """
    parts = set(path.parts)
    if parts & EXCLUDED_DIR_NAMES:
        return True
    name = path.name
    if name.endswith(".example"):
        return False
    for pattern in EXCLUDED_FILE_GLOBS:
        if path.match(pattern):
            return True
    return False
