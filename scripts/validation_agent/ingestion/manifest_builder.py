"""Persist a workbook manifest to disk (JSON) and hash it."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from .workbook_ingestor import WorkbookManifest


def build_and_write(manifest: WorkbookManifest, dest_dir: str | Path,
                    filename: str = "workbook_manifest.json") -> Path:
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    payload = manifest.to_dict()
    text = json.dumps(payload, indent=2, default=str)
    manifest.manifest_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    # Re-serialise including the hash of the pre-hash body.
    payload["manifest_sha256"] = manifest.manifest_sha256
    out = dest / filename
    # Never overwrite an existing manifest — number if needed.
    i = 1
    while out.exists():
        out = dest / f"{Path(filename).stem}_{i:02d}.json"
        i += 1
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out
