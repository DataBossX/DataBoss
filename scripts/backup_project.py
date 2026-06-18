#!/usr/bin/env python3
"""Create a timestamped local backup archive of the project source.

Excludes secrets, dependencies, build output, caches, logs, databases and
backups so the archive is safe to keep and reasonably small.

Usage:
    python scripts/backup_project.py [output_dir]
Default output dir: <repo>/backups
"""
from __future__ import annotations

import sys
import tarfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "build", "dist",
    ".next", "out", "coverage", ".cache", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "backups", "downloads", "images", "logs",
}
EXCLUDE_SUFFIXES = {
    ".env", ".key", ".pem", ".crt", ".db", ".sqlite", ".sqlite3",
    ".log", ".zip", ".tar", ".tar.gz", ".tgz",
}
EXCLUDE_NAMES = {"master.key", "credentials.json", "secrets.json"}


def included(path: Path) -> bool:
    rel_parts = path.relative_to(ROOT).parts
    if any(part in EXCLUDE_DIRS for part in rel_parts):
        return False
    if path.name in EXCLUDE_NAMES:
        return False
    if path.name.endswith(".env") and not path.name.endswith(".env.example"):
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    return True


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT / "backups")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = out_dir / f"databossx-backup-{stamp}.tar.gz"

    count = 0
    with tarfile.open(archive, "w:gz") as tar:
        for path in ROOT.rglob("*"):
            if path.is_file() and included(path):
                tar.add(path, arcname=str(path.relative_to(ROOT)))
                count += 1

    size_mb = archive.stat().st_size / (1024 * 1024)
    print(f"Backup created: {archive}")
    print(f"  files: {count}   size: {size_mb:.2f} MB")
    print("  (secrets, deps, build output, logs and databases excluded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
