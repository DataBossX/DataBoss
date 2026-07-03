"""Immutable, versioned run folders.

A run folder is created once per validation run under ``outputs/`` and never
mutated in place. Source workbooks are copied to a v0 baseline (the original is
opened read-only). Each repaired/recalculated workbook is written as a new,
never-overwritten version file. Every file is hashed and recorded in the DB.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


RUN_SUBDIRS = (
    "input", "versions", "sources", "reports",
    "audit", "logs", "escalations", "exports",
)


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class RunContext:
    run_id: str
    run_dir: Path
    baseline_path: Path | None = None
    baseline_hash: str | None = None
    versions: list[Path] = field(default_factory=list)

    def subdir(self, name: str) -> Path:
        return self.run_dir / name


class RunManager:
    """Creates and manages one immutable run folder."""

    def __init__(self, outputs_dir: str | Path, timestamp: str | None = None):
        self.outputs_dir = Path(outputs_dir)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        # Timestamp is injected for deterministic tests; otherwise generated.
        self.timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = f"validation_run_{self.timestamp}"
        self.run_dir = self.outputs_dir / self.run_id
        if self.run_dir.exists():
            # Never clobber an existing run; disambiguate with a counter.
            n = 1
            while (self.outputs_dir / f"{self.run_id}_{n:02d}").exists():
                n += 1
            self.run_id = f"{self.run_id}_{n:02d}"
            self.run_dir = self.outputs_dir / self.run_id
        self._create_skeleton()
        self.ctx = RunContext(run_id=self.run_id, run_dir=self.run_dir)

    def _create_skeleton(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=False)
        for sub in RUN_SUBDIRS:
            (self.run_dir / sub).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    def ingest_baseline(self, source_workbook: str | Path) -> tuple[Path, str]:
        """Copy the source workbook to input/ and versions/ as the v0 baseline.

        The original file is only ever *read* (shutil.copy2 opens read-only on
        the source). Returns (baseline_version_path, sha256).
        """
        src = Path(source_workbook)
        if not src.exists():
            raise FileNotFoundError(f"Source workbook not found: {src}")
        src_hash = sha256_file(src)
        suffix = src.suffix or ".xlsx"

        # Keep a pristine copy of the raw input.
        input_copy = self.run_dir / "input" / src.name
        if not input_copy.exists():
            shutil.copy2(src, input_copy)

        # v0 baseline in versions/
        baseline = self.run_dir / "versions" / f"workbook_v0{suffix}"
        if baseline.exists():
            raise FileExistsError(f"Baseline already exists: {baseline}")
        shutil.copy2(src, baseline)

        self.ctx.baseline_path = baseline
        self.ctx.baseline_hash = src_hash
        self.ctx.versions = [baseline]
        return baseline, src_hash

    def next_version_path(self, suffix: str = ".xlsx") -> Path:
        """Return the path for the next workbook version (never overwrites)."""
        existing = sorted(
            (self.run_dir / "versions").glob("workbook_v[0-9][0-9][0-9]*")
        )
        n = len(existing) + 1
        path = self.run_dir / "versions" / f"workbook_v{n:03d}{suffix}"
        while path.exists():
            n += 1
            path = self.run_dir / "versions" / f"workbook_v{n:03d}{suffix}"
        return path

    def register_version(self, path: Path) -> None:
        self.ctx.versions.append(path)

    def latest_version(self) -> Path | None:
        return self.ctx.versions[-1] if self.ctx.versions else None

    def unique_export_path(self, name: str) -> Path:
        """Return an export path, numbering the name if it already exists."""
        exports = self.run_dir / "exports"
        candidate = exports / name
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        n = 1
        while (exports / f"{stem}_{n:03d}{suffix}").exists():
            n += 1
        return exports / f"{stem}_{n:03d}{suffix}"
