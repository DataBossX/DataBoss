"""Immutable, versioned run folders.

Guarantees:
  * The original source workbook is never opened in write mode; it is copied to
    ``input/`` and hashed as the v0 baseline under ``versions/``.
  * Every repaired workbook becomes a NEW numbered version; existing versioned
    files are never overwritten (a collision raises).
  * Every file that enters the run is SHA-256 hashed and recorded in the DB.
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from db.audit_logger import AuditLogger

SUBFOLDERS = ("input", "versions", "sources", "reports", "audit", "logs", "escalations", "exports")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


class RunManager:
    def __init__(self, outputs_dir: Path, audit: AuditLogger, run_id: Optional[str] = None):
        self.outputs_dir = Path(outputs_dir)
        self.audit = audit
        self.run_id = run_id or f"validation_run_{timestamp_slug()}"
        self.run_dir = self.outputs_dir / self.run_id
        for sub in SUBFOLDERS:
            (self.run_dir / sub).mkdir(parents=True, exist_ok=True)
        self._version_counter = 0  # v0 = baseline

    # ----------------------------------------------------------- baseline
    def ingest_baseline(self, source_workbook: Path) -> Path:
        source_workbook = Path(source_workbook)
        if not source_workbook.is_file():
            raise FileNotFoundError(f"source workbook not found: {source_workbook}")
        # Copy to input/ (read source, write copy — original untouched).
        input_copy = self.run_dir / "input" / source_workbook.name
        if input_copy.exists():
            raise FileExistsError(f"refusing to overwrite {input_copy}")
        shutil.copy2(source_workbook, input_copy)
        # v0 baseline in versions/.
        v0 = self.version_path(0, source_workbook.suffix)
        shutil.copy2(source_workbook, v0)
        digest = sha256_file(v0)
        self.audit.workbook_version(self.run_id, 0, v0.name, str(v0), digest, note="v0 baseline")
        return v0

    # ------------------------------------------------------------ versions
    def version_path(self, index: int, suffix: str = ".xlsx") -> Path:
        name = f"workbook_v{index:03d}{suffix}"
        return self.run_dir / "versions" / name

    def next_version_path(self, suffix: str = ".xlsx") -> Path:
        self._version_counter += 1
        p = self.version_path(self._version_counter, suffix)
        if p.exists():
            raise FileExistsError(f"version already exists, refusing overwrite: {p}")
        return p

    def register_version(self, path: Path, note: str) -> str:
        path = Path(path)
        digest = sha256_file(path)
        idx = int(path.stem.split("_v")[-1])
        self.audit.workbook_version(self.run_id, idx, path.name, str(path), digest, note=note)
        return digest

    # --------------------------------------------------------------- misc
    def path(self, subfolder: str, filename: str) -> Path:
        assert subfolder in SUBFOLDERS, f"unknown subfolder {subfolder}"
        return self.run_dir / subfolder / filename

    def unique_path(self, subfolder: str, filename: str) -> Path:
        """Return a non-colliding path, numbering the filename if needed."""
        base = self.path(subfolder, filename)
        if not base.exists():
            return base
        stem, suffix = base.stem, base.suffix
        i = 1
        while True:
            cand = base.with_name(f"{stem}_{i:02d}{suffix}")
            if not cand.exists():
                return cand
            i += 1
