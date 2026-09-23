"""Read-only local folder connector."""

from __future__ import annotations

from pathlib import Path

from ..hashing import sha256_file
from .base import ConnectorItem, ScanResult


SKIP_DIRS = {".git", ".pytest_cache", "__pycache__", "node_modules", "runtime", "output", ".venv", "venv"}


class LocalFolderConnector:
    connector_type = "local_disk"
    access_mode = "read_only"

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"local connector root does not exist: {self.root}")

    def scan(self, *, dry_run: bool = True, cursor: str = "") -> ScanResult:
        items: list[ConnectorItem] = []
        for path in sorted(self.root.rglob("*")):
            if path.is_dir() or any(part in SKIP_DIRS for part in path.parts):
                continue
            items.append(
                ConnectorItem(
                    provider_id=str(path.relative_to(self.root)),
                    name=path.name,
                    locator=str(path),
                    byte_size=path.stat().st_size,
                    checksum="" if dry_run else sha256_file(path),
                    is_folder=False,
                )
            )
        return ScanResult(
            items=items,
            cursor=cursor or "local:complete",
            dry_run=dry_run,
            completeness_status="COMPLETE",
            write_attempted=False,
        )
