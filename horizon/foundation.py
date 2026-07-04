"""The Horizon Foundation: scan, unzip, SHA256-dedup, and quarantine.

Implements mission section 1 with the Zero-Destruction law in force:

* Sources are only ever *read* and *copied*; nothing is overwritten.
* Archives are extracted into ``temp_raw`` (a managed folder), never in place.
* Byte-for-byte duplicates (identical SHA256) are detected and the *lower*
  fidelity copies are **moved** (not deleted) to ``trash`` so a human can undo.
* The highest-fidelity representative of each duplicate group is kept.

"Highest fidelity" is a deterministic ranking: prefer richer file types
(xlsx > csv > pdf ...), then larger size, then more recent mtime, then the
shortest/cleanest path -- so the choice is reproducible, not arbitrary.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .audit import AuditLog
from .config import HorizonConfig

ARCHIVE_EXT = {".zip"}
FIDELITY_RANK = {
    ".xlsx": 100, ".xlsm": 95, ".xls": 90,
    ".csv": 70, ".tsv": 68, ".txt": 40,
    ".pdf": 60, ".docx": 55, ".doc": 50,
    ".png": 30, ".tif": 32, ".tiff": 32, ".jpg": 28, ".jpeg": 28,
}


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    """Streaming SHA256 so very large workbooks don't blow up memory."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


@dataclass
class FileRecord:
    path: Path
    rel: str
    ext: str
    size: int
    mtime: _dt.datetime
    sha256: str = ""

    def fidelity(self) -> tuple:
        """Higher tuple sorts as higher fidelity."""
        return (
            FIDELITY_RANK.get(self.ext, 10),
            self.size,
            self.mtime.timestamp(),
            -len(self.rel),  # shorter/cleaner path wins ties
        )


@dataclass
class CleanupResult:
    scanned: List[FileRecord] = field(default_factory=list)
    extracted: List[Path] = field(default_factory=list)
    kept: List[FileRecord] = field(default_factory=list)
    quarantined: List[FileRecord] = field(default_factory=list)
    duplicate_groups: int = 0


def unzip_archives(cfg: HorizonConfig, audit: AuditLog) -> List[Path]:
    """Extract every archive under root into ``temp_raw`` (never in place)."""
    cfg.temp_raw.mkdir(parents=True, exist_ok=True)
    extracted: List[Path] = []
    for dirpath, _dirs, files in os.walk(cfg.root):
        if cfg.is_managed(Path(dirpath)):
            continue
        for fn in files:
            p = Path(dirpath) / fn
            if p.suffix.lower() not in ARCHIVE_EXT:
                continue
            dest = cfg.temp_raw / (p.stem + "_" + sha256_of(p)[:8])
            try:
                dest.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(p) as zf:
                    skipped = _safe_extractall(zf, dest)
                extracted.append(dest)
                note = f"{p.name} -> {dest.relative_to(cfg.root)}"
                if skipped:
                    note += f" (skipped {skipped} unsafe path(s))"
                    audit.warn("unzip_unsafe", note)
                else:
                    audit.info("unzip", note)
            except (zipfile.BadZipFile, OSError) as exc:
                audit.warn("unzip_failed", f"{p.name}: {exc}")
    return extracted


def _safe_extractall(zf: zipfile.ZipFile, dest: Path) -> int:
    """Extract ``zf`` into ``dest``, refusing any member that would escape it.

    Guards against Zip-Slip: a malicious entry name like ``../../evil`` (or an
    absolute path) would otherwise let ``extractall`` write outside ``dest``.
    Returns the count of members skipped for being unsafe.
    """
    dest_root = dest.resolve()
    skipped = 0
    for member in zf.namelist():
        target = (dest / member).resolve()
        if target == dest_root or dest_root in target.parents:
            zf.extract(member, dest)
        else:
            skipped += 1
    return skipped


def scan(cfg: HorizonConfig, audit: Optional[AuditLog] = None) -> List[FileRecord]:
    """Recursively inventory every non-managed file, computing its SHA256."""
    records: List[FileRecord] = []
    for dirpath, _dirs, files in os.walk(cfg.root):
        d = Path(dirpath)
        # Skip trash / final reports / backups, but *do* include temp_raw so
        # unzipped payloads participate in dedup.
        if any(_is_within(d, m) for m in (cfg.trash, cfg.final_reports, cfg.backups)):
            continue
        for fn in files:
            p = d / fn
            try:
                st = p.stat()
                rec = FileRecord(
                    path=p,
                    rel=str(p.relative_to(cfg.root)),
                    ext=p.suffix.lower(),
                    size=st.st_size,
                    mtime=_dt.datetime.fromtimestamp(st.st_mtime),
                    sha256=sha256_of(p),
                )
                records.append(rec)
            except OSError as exc:
                if audit:
                    audit.warn("scan_skip", f"{p}: {exc}")
    if audit:
        audit.info("scan", f"inventoried {len(records)} files under {cfg.root}")
    return records


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def dedupe(records: List[FileRecord], cfg: HorizonConfig, audit: AuditLog,
           move: bool = True) -> CleanupResult:
    """Group by SHA256; keep the highest-fidelity file, quarantine the rest.

    When ``move`` is False (dry-run) the duplicates are *identified and reported*
    but not moved -- the source tree is left completely read-only.
    """
    result = CleanupResult(scanned=list(records))
    by_hash: Dict[str, List[FileRecord]] = {}
    for rec in records:
        by_hash.setdefault(rec.sha256, []).append(rec)

    if move:
        cfg.trash.mkdir(parents=True, exist_ok=True)
    for digest, group in by_hash.items():
        group.sort(key=lambda r: r.fidelity(), reverse=True)
        keeper = group[0]
        result.kept.append(keeper)
        if len(group) == 1:
            continue
        result.duplicate_groups += 1
        verb = "would keep" if not move else "keep"
        audit.info("dup_group", f"sha={digest[:12]} n={len(group)} {verb}={keeper.rel}")
        for dup in group[1:]:
            if not move:
                audit.info("dup_would_trash", f"{dup.rel} (dry-run: not moved)")
                result.quarantined.append(dup)
                continue
            if _quarantine(dup, cfg, audit):
                result.quarantined.append(dup)
    return result


def _quarantine(rec: FileRecord, cfg: HorizonConfig, audit: AuditLog) -> bool:
    """Move a duplicate into ``trash`` preserving its relative layout. Never
    deletes -- moving to trash is reversible."""
    dest = cfg.trash / rec.rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    # avoid clobbering an existing quarantined file of the same name
    if dest.exists():
        dest = dest.with_name(f"{dest.stem}_{rec.sha256[:8]}{dest.suffix}")
    try:
        shutil.move(str(rec.path), str(dest))
        audit.info("quarantine_dup", f"{rec.rel} -> trash/{dest.relative_to(cfg.trash)}")
        return True
    except OSError as exc:
        audit.warn("quarantine_failed", f"{rec.rel}: {exc}")
        return False


def snapshot_backup(cfg: HorizonConfig, audit: AuditLog) -> Path:
    """The Snapshot Rule: copy the whole root to a sibling ``*_Backups`` tree
    *before* any cleanup mutates the workspace. Copy-only, source untouched."""
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = cfg.backups / stamp
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for dirpath, _dirs, files in os.walk(cfg.root):
        d = Path(dirpath)
        if cfg.is_managed(d):
            continue
        for fn in files:
            src = d / fn
            try:
                rel = src.relative_to(cfg.root)
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
                copied += 1
            except OSError as exc:
                audit.warn("backup_skip", f"{src}: {exc}")
    audit.info("snapshot_backup", f"copied {copied} files -> {dest}")
    return dest


def run_cleanup(cfg: HorizonConfig, audit: AuditLog, backup: bool = True,
                dry_run: bool = False) -> CleanupResult:
    """Full foundation pass: snapshot -> unzip -> scan -> dedupe.

    In ``dry_run`` mode the tree is left strictly read-only: no snapshot copy, no
    archive extraction, and duplicates are reported but not moved to trash.
    """
    if dry_run:
        # Only create the folders needed to *scan*; do not mutate sources.
        records = scan(cfg, audit)
        result = dedupe(records, cfg, audit, move=False)
        result.extracted = []
        audit.info(
            "cleanup_dry_run",
            f"scanned={len(result.scanned)} kept={len(result.kept)} "
            f"would_trash={len(result.quarantined)} dup_groups={result.duplicate_groups}",
        )
        return result

    cfg.ensure_workspace()
    if backup:
        snapshot_backup(cfg, audit)
    extracted = unzip_archives(cfg, audit)
    records = scan(cfg, audit)
    result = dedupe(records, cfg, audit)
    result.extracted = extracted
    audit.info(
        "cleanup_done",
        f"scanned={len(result.scanned)} kept={len(result.kept)} "
        f"quarantined={len(result.quarantined)} dup_groups={result.duplicate_groups}",
    )
    return result
