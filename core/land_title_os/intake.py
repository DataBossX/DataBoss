"""Intake wiring (Move #11 → #3): land every inventory run in the master
asset database instead of a one-off CSV.

``ingest_inventory_csv`` consumes the grocery pipeline's stage-A
``output/file_inventory.csv`` (columns: rel_path, name, ext, size_bytes,
modified, sha256, likely_type, processing_status, abs_path) and registers
each file in an ``AssetInventory`` without re-hashing, so a pipeline run on
the operator's machine feeds the master database directly.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .assets import Asset, AssetInventory
from .util import stable_id, utcnow_iso


def ingest_inventory_csv(inventory: AssetInventory, csv_path: str | Path,
                         project_id: str | None = None,
                         security_class: str = "client-confidential") -> int:
    """Register every row of a stage-A inventory CSV. Returns rows ingested."""
    count = 0
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            location = row.get("abs_path") or row.get("rel_path") or ""
            digest = row.get("sha256") or None
            if not location:
                continue
            inventory._upsert(Asset(
                asset_id=stable_id("AST", location, digest or ""),
                location=location,
                sha256=digest,
                size_bytes=int(row["size_bytes"]) if row.get("size_bytes") else None,
                file_type=(row.get("ext") or "").lstrip(".").lower() or None,
                project_id=project_id,
                status="SOURCE",
                security_class=security_class,
                version=row.get("modified") or None,
                last_verified=utcnow_iso(),
            ))
            count += 1
    inventory.assign_duplicate_groups()
    return count
