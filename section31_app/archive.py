"""Archive all non-final files; leave only the final workbook in the main folder.

After a successful export the main Roger Mills folder should contain exactly one
spreadsheet -- the final report. Everything else (candidate workbooks, loose
images, prior exports) is *moved* (never deleted) into the managed subfolders so
nothing is ever lost and the folder reads clean.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List

from .config import FINAL_WORKBOOK_NAME, Section31Config
from .logbook import LogBook

_WORKBOOK_EXT = {".xlsx", ".xlsm", ".xls"}
_IMAGE_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def _dest_for(cfg: Section31Config, path: Path) -> Path:
    ext = path.suffix.lower()
    if ext in _WORKBOOK_EXT:
        return cfg.candidates_dir
    if ext in _IMAGE_EXT:
        return cfg.images_dir
    return cfg.archive_dir


def _unique(dest_dir: Path, name: str) -> Path:
    target = dest_dir / name
    if not target.exists():
        return target
    stem, suffix = Path(name).stem, Path(name).suffix
    i = 1
    while True:
        cand = dest_dir / f"{stem}__{i}{suffix}"
        if not cand.exists():
            return cand
        i += 1


def archive_non_final(cfg: Section31Config, log: LogBook | None = None) -> Dict[str, List[str]]:
    """Move every top-level non-final file into its managed subfolder.

    Only files sitting directly in the main folder are touched; the managed
    subfolders are left alone. Returns a manifest of what moved where.
    """
    log = log or LogBook()
    moved: Dict[str, List[str]] = {}
    if not cfg.root.exists():
        return moved

    for entry in list(cfg.root.iterdir()):
        if entry.is_dir():
            continue
        if entry.name == FINAL_WORKBOOK_NAME:
            continue  # the one file that stays
        # skip our own logs/notes that belong at root? -> move to _archive/_logs
        dest_dir = _dest_for(cfg, entry)
        if entry.suffix.lower() in (".log", ".txt") and "spend" not in entry.name.lower():
            dest_dir = cfg.logs_dir
        try:
            target = _unique(dest_dir, entry.name)
            shutil.move(str(entry), str(target))
            moved.setdefault(dest_dir.name, []).append(entry.name)
            log.info(f"archived {entry.name} -> {dest_dir.name}/")
        except OSError as exc:
            log.warn(f"could not archive {entry.name}: {type(exc).__name__}")
    return moved


def verify_clean(cfg: Section31Config) -> bool:
    """True when the main folder holds only the final workbook + subfolders."""
    if not cfg.root.exists():
        return False
    loose = [p for p in cfg.root.iterdir()
             if p.is_file() and p.name != FINAL_WORKBOOK_NAME]
    return not loose and cfg.final_workbook.exists()
