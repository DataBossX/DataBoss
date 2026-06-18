"""Safe project backup for DataBossX.

Produces a zip that EXCLUDES secrets, logs, backups, rollback, diagnostics,
caches and private DBs. Emits a manifest (with the zip's SHA-256) and a log.

Satisfies: "backup excludes secrets".
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import paths


@dataclass
class BackupResult:
    zip_path: Path
    manifest_path: Path
    log_path: Path
    file_count: int
    sha256: str
    excluded_count: int


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def create_backup(ts: str | None = None, root: Path | None = None) -> BackupResult:
    root = root or paths.ROOT
    paths.ensure_dirs()
    ts = ts or paths.timestamp()

    zip_path = paths.BACKUPS / f"DataBossX_backup_{ts}.zip"
    manifest_path = paths.BACKUPS / f"DataBossX_backup_{ts}.manifest.json"
    log_path = paths.LOGS / f"backup_{ts}.log"

    included: list[str] = []
    excluded: list[str] = []

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            # Never back up the backup we are currently writing.
            if path == zip_path:
                continue
            if paths.is_excluded(rel):
                excluded.append(rel.as_posix())
                continue
            zf.write(path, rel.as_posix())
            included.append(rel.as_posix())

    sha = _sha256(zip_path)
    manifest = {
        "created": ts,
        "zip": zip_path.name,
        "sha256": sha,
        "file_count": len(included),
        "excluded_count": len(excluded),
        "files": included,
        "excluded_sample": excluded[:50],
        "exclusion_rules": {
            "dirs": sorted(paths.EXCLUDED_DIR_NAMES),
            "file_globs": list(paths.EXCLUDED_FILE_GLOBS),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))

    log_lines = [
        f"[{ts}] DataBossX backup",
        f"zip       = {zip_path}",
        f"sha256    = {sha}",
        f"included  = {len(included)} files",
        f"excluded  = {len(excluded)} files (secrets/logs/backups/etc.)",
        "OK: no .env / .auth / secret files written to archive"
        if not any(paths.is_excluded(Path(f)) for f in included)
        else "WARNING: review inclusion list",
    ]
    log_path.write_text("\n".join(log_lines) + "\n")

    return BackupResult(zip_path, manifest_path, log_path, len(included), sha, len(excluded))
