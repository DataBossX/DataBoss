"""Backup hash manifests and restore verification (Move #9).

"Backups are not verified until DataBossX proves it can restore them."
A manifest records every file's SHA-256 and size; ``verify_restore``
compares a restored (or backup) copy against the manifest and reports
missing, changed, and extra files. An empty report list means the copy is
byte-identical to what the manifest recorded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .util import sha256_file, utcnow_iso

EXCLUDE_DIRS = (".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache")


@dataclass
class RestoreProblem:
    kind: str            # missing | changed | extra
    path: str            # manifest-relative path

    def describe(self) -> str:
        return f"{self.kind}: {self.path}"


def create_manifest(root: str | Path, manifest_path: str | Path,
                    exclude_dirs: tuple = EXCLUDE_DIRS) -> dict:
    """Hash every file under root into a manifest JSON. Read-only on root."""
    root = Path(root)
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_dir() or any(part in exclude_dirs for part in p.parts):
            continue
        rel = p.relative_to(root).as_posix()
        files[rel] = {"sha256": sha256_file(p), "size": p.stat().st_size}
    manifest = {"root": str(root.resolve()), "created_at": utcnow_iso(),
                "file_count": len(files), "files": files}
    mp = Path(manifest_path)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_restore(restored_root: str | Path, manifest_path: str | Path,
                   exclude_dirs: tuple = EXCLUDE_DIRS) -> list[RestoreProblem]:
    """Compare a restored copy against a manifest. Empty list = verified."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    restored_root = Path(restored_root)
    problems: list[RestoreProblem] = []

    present = set()
    for p in sorted(restored_root.rglob("*")):
        if p.is_dir() or any(part in exclude_dirs for part in p.parts):
            continue
        present.add(p.relative_to(restored_root).as_posix())

    for rel, rec in manifest["files"].items():
        target = restored_root / rel
        if rel not in present:
            problems.append(RestoreProblem("missing", rel))
        elif sha256_file(target) != rec["sha256"]:
            problems.append(RestoreProblem("changed", rel))
    for rel in sorted(present - set(manifest["files"])):
        problems.append(RestoreProblem("extra", rel))
    return problems
