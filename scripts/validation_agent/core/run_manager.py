"""Immutable run folders and the versioned workbook chain.

A run is a timestamped, write-once workspace. The original workbook is copied
in as ``v000`` and never opened for writing. Every repair/recalc produces the
next ``vNNN`` file; nothing is ever overwritten. Each version is SHA-256 hashed
and recorded in the append-only audit DB.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .hashing import sha256_file

RUN_SUBDIRS = (
    "input",
    "versions",
    "sources",
    "reports",
    "audit",
    "logs",
    "escalations",
    "exports",
)


@dataclass(frozen=True)
class WorkbookVersion:
    index: int
    label: str
    path: Path
    sha256: str
    origin: str
    parent_index: Optional[int]


class RunManagerError(RuntimeError):
    pass


class RunManager:
    """Creates and manages a single immutable validation run folder."""

    def __init__(self, run_folder: Path, run_id: str) -> None:
        self.run_folder = Path(run_folder)
        self.run_id = run_id
        self._versions: List[WorkbookVersion] = []

    # ------------------------------------------------------------------ #
    @classmethod
    def create(cls, outputs_dir: Path, timestamp: Optional[str] = None) -> "RunManager":
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_id = f"validation_run_{timestamp}"
        run_folder = Path(outputs_dir) / run_id
        if run_folder.exists():
            raise RunManagerError(f"run folder already exists: {run_folder}")
        run_folder.mkdir(parents=True, exist_ok=False)
        for sub in RUN_SUBDIRS:
            (run_folder / sub).mkdir(parents=True, exist_ok=False)
        return cls(run_folder, run_id)

    # -- accessors ----------------------------------------------------- #
    @property
    def input_dir(self) -> Path:
        return self.run_folder / "input"

    @property
    def versions_dir(self) -> Path:
        return self.run_folder / "versions"

    @property
    def sources_dir(self) -> Path:
        return self.run_folder / "sources"

    @property
    def reports_dir(self) -> Path:
        return self.run_folder / "reports"

    @property
    def audit_dir(self) -> Path:
        return self.run_folder / "audit"

    @property
    def logs_dir(self) -> Path:
        return self.run_folder / "logs"

    @property
    def escalations_dir(self) -> Path:
        return self.run_folder / "escalations"

    @property
    def exports_dir(self) -> Path:
        return self.run_folder / "exports"

    @property
    def versions(self) -> List[WorkbookVersion]:
        return list(self._versions)

    def latest_version(self) -> Optional[WorkbookVersion]:
        return self._versions[-1] if self._versions else None

    # -- versioning ---------------------------------------------------- #
    def _version_filename(self, source_name: str, index: int) -> str:
        # Strip any existing _vNNN suffix so versions don't accumulate
        # (clean.xlsx -> clean_v000.xlsx -> clean_v001.xlsx, not _v000_v001).
        stem = re.sub(r"_v\d{3}$", "", Path(source_name).stem)
        suffix = Path(source_name).suffix or ".xlsx"
        return f"{stem}_v{index:03d}{suffix}"

    def ingest_source_workbook(self, source_path: Path) -> WorkbookVersion:
        """Copy the original workbook in as v000 without opening it for write."""
        source_path = Path(source_path)
        if not source_path.exists():
            raise RunManagerError(f"source workbook not found: {source_path}")
        if self._versions:
            raise RunManagerError("source workbook already ingested")

        # Preserve a pristine copy in input/ as well.
        preserved = self.input_dir / source_path.name
        shutil.copy2(source_path, preserved)

        index = 0
        dest_name = self._version_filename(source_path.name, index)
        dest = self.versions_dir / dest_name
        shutil.copy2(source_path, dest)

        version = WorkbookVersion(
            index=index,
            label=f"v{index:03d}",
            path=dest,
            sha256=sha256_file(dest),
            origin="source_copy",
            parent_index=None,
        )
        self._versions.append(version)
        return version

    def new_version_path(self, origin: str) -> Path:
        """Reserve the next version path without materialising the file yet."""
        if not self._versions:
            raise RunManagerError("cannot create a new version before ingest")
        prev = self._versions[-1]
        index = prev.index + 1
        dest_name = self._version_filename(prev.path.name, index)
        dest = self.versions_dir / dest_name
        if dest.exists():
            raise RunManagerError(f"refusing to overwrite existing version: {dest}")
        return dest

    def register_version(self, path: Path, origin: str) -> WorkbookVersion:
        """Register an already-written next-version file (repair/recalc output)."""
        if not self._versions:
            raise RunManagerError("cannot register a version before ingest")
        path = Path(path)
        if not path.exists():
            raise RunManagerError(f"version file does not exist: {path}")
        prev = self._versions[-1]
        index = prev.index + 1
        version = WorkbookVersion(
            index=index,
            label=f"v{index:03d}",
            path=path,
            sha256=sha256_file(path),
            origin=origin,
            parent_index=prev.index,
        )
        self._versions.append(version)
        return version
