"""Guarded file operations for DataBossX.

Enforces the operating law: never overwrite originals, never write into
protected/excluded locations, support dry-run.

Satisfies: "dry-run copy does not write".
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import paths

# Folder name fragments that are user/source data we must never delete or overwrite.
PROTECTED_NAMES = {"horizon", "penterra"}


class GuardError(RuntimeError):
    pass


@dataclass
class CopyPlan:
    src: Path
    dst: Path
    dry_run: bool
    performed: bool


def _is_protected(path: Path) -> bool:
    lowered = {p.lower() for p in path.parts}
    return bool(lowered & PROTECTED_NAMES)


def guarded_copy(src: Path, dst: Path, *, dry_run: bool = False, overwrite: bool = False) -> CopyPlan:
    src = Path(src)
    dst = Path(dst)
    if not src.exists():
        raise GuardError(f"source does not exist: {src}")
    if dst.exists() and not overwrite:
        raise GuardError(f"refusing to overwrite existing file: {dst}")
    if _is_protected(dst):
        raise GuardError(f"refusing to write into protected area: {dst}")
    if paths.is_excluded(dst):
        raise GuardError(f"refusing to write into excluded/secret area: {dst}")

    if dry_run:
        return CopyPlan(src, dst, dry_run=True, performed=False)

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return CopyPlan(src, dst, dry_run=False, performed=True)


def guarded_delete(path: Path) -> None:
    path = Path(path)
    if _is_protected(path):
        raise GuardError(f"refusing to delete protected area: {path}")
    raise GuardError("guarded_delete is intentionally disabled; deletes require manual action")
