"""RunManager -- immutable run folders and versioned workbook copies.

Golden Law #5: absolutely no source file overwrites.  The source workbook is
opened strictly read-only, hashed, and copied into a timestamped run folder as
the version 0 (v0) baseline.  Every subsequent repair writes a *new* vN file;
existing versions are never touched again.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..config.settings import config
from ..db.audit_logger import AuditLogger


def sha256_of(path: Path) -> str:
    """Stream-hash a file without loading it fully or opening it writable."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:  # 'rb' -- read only, never mutates the source
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class RunContext:
    run_id: str
    run_folder: Path
    versions_dir: Path
    source_path: Path
    source_sha256: str
    v0_path: Path

    def version_path(self, version: int) -> Path:
        return self.versions_dir / f"workbook_v{version}.xlsx"


class RunManager:
    def __init__(self, audit: Optional[AuditLogger] = None) -> None:
        self.audit = audit or AuditLogger()

    def create_run(self, source_workbook: str | Path, *, timestamp: str) -> RunContext:
        """Create the immutable run folder and secure the v0 baseline.

        ``timestamp`` is injected (never generated here) so runs are fully
        reproducible and the audit trail is deterministic.
        """
        source = Path(source_workbook).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Source workbook not found: {source}")

        run_id = f"validation_run_{timestamp}"
        run_folder = (config.outputs_dir / run_id).resolve()
        if run_folder.exists():
            raise FileExistsError(
                f"Run folder already exists (refusing to overwrite): {run_folder}")

        versions_dir = run_folder / "versions"
        versions_dir.mkdir(parents=True, exist_ok=False)
        (run_folder / "reports").mkdir(exist_ok=True)
        (run_folder / "escalations").mkdir(exist_ok=True)

        source_hash = sha256_of(source)
        v0_path = versions_dir / "workbook_v0.xlsx"
        # copy2 reads the source and writes a *new* file; the source is never
        # opened for writing.
        shutil.copy2(source, v0_path)

        # Integrity: the immutable copy must match the source byte-for-byte.
        if sha256_of(v0_path) != source_hash:
            raise RuntimeError("v0 baseline hash mismatch -- copy is not faithful.")

        ctx = RunContext(
            run_id=run_id,
            run_folder=run_folder,
            versions_dir=versions_dir,
            source_path=source,
            source_sha256=source_hash,
            v0_path=v0_path,
        )

        self.audit.open_run(run_id, str(source), source_hash, str(run_folder))
        self.audit.log_version(run_id, 0, str(v0_path), source_hash,
                               note="Immutable v0 baseline copy of source.")
        return ctx

    def register_version(self, ctx: RunContext, version: int, path: Path,
                         note: str = "") -> str:
        """Hash and record a freshly produced workbook version."""
        digest = sha256_of(path)
        self.audit.log_version(ctx.run_id, version, str(path), digest, note=note)
        return digest
