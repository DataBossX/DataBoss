"""Provider-neutral connector contracts.

Connectors are inventory tools, not copy cannons. Every connector must support
dry-run, bounded roots, incremental cursors, checksums, retries, and read-only
mode. Credentials are referenced, never stored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ConnectorItem:
    provider_id: str
    name: str
    locator: str
    mime_type: str = ""
    byte_size: int = 0
    modified_time: str = ""
    checksum: str = ""
    is_folder: bool = False
    parents: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScanResult:
    items: list[ConnectorItem] = field(default_factory=list)
    cursor: str = ""
    dry_run: bool = True
    completeness_status: str = "COMPLETE"
    write_attempted: bool = False


class Connector(Protocol):
    connector_type: str
    access_mode: str

    def scan(self, *, dry_run: bool = True, cursor: str = "") -> ScanResult:
        ...
