"""Build an immutable JSON manifest object from ingestion + classification and
hash it. The manifest is the single source of structural truth for validators.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from ingestion.workbook_ingestor import ingest_workbook
from ingestion.sheet_classifier import classify_workbook


def build_manifest(workbook_path: Path) -> Dict[str, Any]:
    ingest = ingest_workbook(workbook_path)
    classification = classify_workbook(ingest["sheets"])
    manifest = {
        "schema": "databossx.validation_agent.manifest/1",
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "ingestion": ingest,
        "classification": classification,
    }
    manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return manifest


def write_manifest(manifest: Dict[str, Any], dest: Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return dest
