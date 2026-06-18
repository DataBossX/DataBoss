"""Diagnostics bundle for DataBossX.

Collects reports + logs (NOT secrets) into a zip for support/handoff.

Satisfies: "diagnostics bundle excludes .env and .auth".
"""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import paths


@dataclass
class DiagnosticsResult:
    zip_path: Path
    file_count: int
    included: list[str]


def build(ts: str | None = None) -> DiagnosticsResult:
    paths.ensure_dirs()
    ts = ts or paths.timestamp()
    zip_path = paths.DIAGNOSTICS / f"DataBossX_diagnostics_{ts}.zip"

    # Only collect safe artifact dirs; re-check every file against exclusion rules.
    sources = [paths.REPORTS, paths.LOGS, paths.REVIEW_OUTPUTS]
    included: list[str] = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src in sources:
            if not src.exists():
                continue
            for path in sorted(src.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(paths.ROOT)
                # Logs live in an excluded dir but we DO want non-secret logs in
                # diagnostics, so allow .log explicitly while still blocking
                # .env/.auth/keys.
                name = path.name
                if name in (".env",) or name.endswith((".auth", ".pem")) or "credentials" in name:
                    continue
                if name.endswith(".env") or ".env." in name:
                    continue
                zf.write(path, rel.as_posix())
                included.append(rel.as_posix())
        manifest = {"created": ts, "file_count": len(included), "files": included}
        zf.writestr("diagnostics_manifest.json", json.dumps(manifest, indent=2))

    return DiagnosticsResult(zip_path, len(included), included)
