"""Immutable manifest assembly.

Combines the workbook structure and sheet classification into a single JSON
document, writes it to the run's audit folder, and returns the manifest plus
its SHA-256 hash. The manifest is write-once.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.hashing import sha256_text
from .sheet_classifier import ClassificationReport
from .workbook_ingestor import WorkbookStructure


def build_manifest(
    structure: WorkbookStructure,
    classification: ClassificationReport,
    run_id: str,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    manifest: Dict[str, Any] = {
        "manifest_version": 1,
        "run_id": run_id,
        "generated_at": generated_at,
        "workbook": structure.to_dict(),
        "classification": classification.to_dict(),
    }
    return manifest


def write_manifest(manifest: Dict[str, Any], dest_dir: Path) -> Dict[str, Any]:
    """Write manifest JSON + its hash. Never overwrites an existing manifest."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    body = json.dumps(manifest, indent=2, sort_keys=True, default=str)
    digest = sha256_text(body)

    manifest_path = dest_dir / "manifest.json"
    if manifest_path.exists():
        # immutability: version the filename rather than overwrite
        stamp = manifest.get("generated_at", "").replace(":", "").replace(".", "")
        manifest_path = dest_dir / f"manifest_{stamp}.json"
    manifest_path.write_text(body, encoding="utf-8")
    (dest_dir / (manifest_path.stem + ".sha256")).write_text(digest, encoding="utf-8")

    return {"path": str(manifest_path), "sha256": digest}
