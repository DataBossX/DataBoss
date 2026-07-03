"""Builds and persists the immutable ingestion manifest JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.run_manager import sha256_bytes


def build_manifest(workbook_manifest, classification: dict) -> dict[str, Any]:
    """Merge structural manifest + classification into one dict."""
    data = workbook_manifest.to_dict()
    data["classification"] = classification
    return data


def write_manifest(run_dir: str | Path, manifest: dict[str, Any]) -> tuple[Path, str]:
    """Write manifest JSON into the run's audit folder (never overwrites)."""
    audit_dir = Path(run_dir) / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / "manifest.json"
    n = 1
    while path.exists():
        path = audit_dir / f"manifest_{n:03d}.json"
        n += 1
    payload = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    path.write_bytes(payload)
    return path, sha256_bytes(payload)
