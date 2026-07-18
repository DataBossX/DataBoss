from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    name: str
    jurisdiction_code: str
    policy_profile: str
    root_path: Path


@dataclass(frozen=True)
class SourceConnectionRecord:
    source_connection_id: int
    project_id: str
    root_path: Path
    source_type: str = "local_disk"
    access_mode: str = "read_only"


@dataclass(frozen=True)
class InventoryItem:
    asset_id: int
    asset_version_id: int
    original_path: Path
    sha256: str
    duplicate_of_asset_version_id: int | None = None


@dataclass(frozen=True)
class InventoryResult:
    source_snapshot_id: int
    manifest_hash: str
    item_count: int
    duplicate_count: int
    items: list[InventoryItem] = field(default_factory=list)
