"""
Immutable run manager.

Creates a timestamped run folder, copies the source workbook as an immutable v0
baseline (source is only ever opened read-only), and mints new numbered workbook
versions. Nothing versioned is ever overwritten; every file is hashed and the
hash recorded in the append-only DB.
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from db.db_client import DatabaseManager, utcnow

RUN_SUBDIRS = ("input", "versions", "sources", "reports", "audit", "logs",
               "escalations", "exports")


def sha256_file(path: str | Path, chunk: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


class RunManager:
    def __init__(self, db: DatabaseManager, outputs_dir: str | Path):
        self.db = db
        self.outputs_dir = Path(outputs_dir)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.run_id: Optional[str] = None
        self.run_folder: Optional[Path] = None

    def _stamp(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def create_run(self, workbook_path: str | Path, mode: str = "dry-run",
                   run_id: Optional[str] = None) -> str:
        wb = Path(workbook_path)
        if not wb.exists():
            raise FileNotFoundError(f"Source workbook not found: {wb}")
        stamp = self._stamp()
        base_id = run_id or f"validation_run_{stamp}"
        self.run_id = base_id
        self.run_folder = self.outputs_dir / self.run_id
        # Guarantee uniqueness — never reuse/overwrite an existing run folder,
        # and keep run_id in lockstep with the (unique) folder name so the DB
        # row is unique too.
        suffix = 1
        while self.run_folder.exists():
            self.run_id = f"{base_id}_{suffix:02d}"
            self.run_folder = self.outputs_dir / self.run_id
            suffix += 1
        for sub in RUN_SUBDIRS:
            (self.run_folder / sub).mkdir(parents=True, exist_ok=True)

        # Copy source into input/ (read-only source; copy2 preserves metadata).
        baseline_name = wb.name
        input_copy = self.run_folder / "input" / baseline_name
        shutil.copy2(wb, input_copy)
        src_hash = sha256_file(input_copy)

        # v0 immutable baseline in versions/.
        v0 = self.run_folder / "versions" / "workbook_v000.xlsx"
        shutil.copy2(wb, v0)

        self.db.insert("runs", {
            "run_id": self.run_id, "workbook_name": baseline_name,
            "workbook_sha256": src_hash, "run_folder": str(self.run_folder),
            "mode": mode, "status": "INIT", "iterations": 0, "created_at": utcnow(),
        })
        self._record_version("v000", v0, "baseline")
        return self.run_id

    def _record_version(self, label: str, path: Path, origin: str) -> None:
        self.db.insert("workbook_versions", {
            "run_id": self.run_id, "version_label": label, "file_path": str(path),
            "sha256": sha256_file(path), "size_bytes": path.stat().st_size,
            "origin": origin, "created_at": utcnow(),
        })

    def next_version_path(self) -> Path:
        """Return the next unused workbook_vNNN.xlsx path (never overwrites)."""
        versions = self.run_folder / "versions"
        existing = sorted(versions.glob("workbook_v*.xlsx"))
        nums = []
        for p in existing:
            digits = "".join(ch for ch in p.stem if ch.isdigit())
            if digits:
                nums.append(int(digits))
        nxt = (max(nums) + 1) if nums else 1
        return versions / f"workbook_v{nxt:03d}.xlsx"

    def register_version(self, produced_path: str | Path, origin: str) -> Path:
        """Record an already-correctly-named version file in place (no renumber)."""
        produced = Path(produced_path)
        if not produced.exists():
            raise FileNotFoundError(f"Version file missing: {produced}")
        label = "v" + "".join(ch for ch in produced.stem if ch.isdigit())
        self._record_version(label, produced, origin)
        return produced

    def commit_version(self, produced_path: str | Path, origin: str) -> Path:
        """Move a workbook produced elsewhere into versions/ as the next number."""
        produced = Path(produced_path)
        target = self.next_version_path()
        if target.exists():  # pragma: no cover - defensive
            raise FileExistsError(f"Refusing to overwrite {target}")
        if produced.resolve() != target.resolve():
            shutil.copy2(produced, target)
        label = "v" + "".join(ch for ch in target.stem if ch.isdigit())
        self._record_version(label, target, origin)
        return target

    def latest_version(self) -> Optional[Path]:
        versions = self.run_folder / "versions"
        existing = sorted(versions.glob("workbook_v*.xlsx"))
        return existing[-1] if existing else None

    def path(self, subdir: str) -> Path:
        return self.run_folder / subdir
