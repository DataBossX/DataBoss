"""Read-only Google Drive connector.

Default backend is a local Drive-export mirror so tests and air-gapped machines
can scan without account-wide credentials. A live Google client is optional and
still cannot write, delete, or share.

Scope intent: ``drive.file`` / user-selected files. Never store access tokens
in the database — only a credential_ref.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..hashing import sha256_file
from ..policy import PolicyDecision, PolicyEngine
from .base import ConnectorItem, ScanResult


class DriveWriteRefused(RuntimeError):
    pass


_MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


@dataclass(frozen=True)
class DriveConnection:
    root_locator: str
    credential_ref: str = ""
    backend: str = "local_mirror"  # local_mirror | google_api
    page_token: str = ""


class GoogleDriveConnector:
    connector_type = "google_drive"
    access_mode = "read_only"

    def __init__(
        self,
        connection: DriveConnection,
        *,
        policy: PolicyEngine | None = None,
        api_list: Callable[[str], list[dict]] | None = None,
    ):
        self.connection = connection
        self.policy = policy or PolicyEngine()
        self.api_list = api_list

    def scan(self, *, dry_run: bool = True, cursor: str = "") -> ScanResult:
        decision = self.policy.allow_connector_scan(self.connector_type, self.access_mode)
        if not decision.allowed:
            raise DriveWriteRefused(decision.reason)
        if self.connection.backend == "google_api":
            return self._scan_google(dry_run=dry_run, cursor=cursor)
        return self._scan_local_mirror(dry_run=dry_run, cursor=cursor)

    def _scan_local_mirror(self, *, dry_run: bool, cursor: str) -> ScanResult:
        root = Path(self.connection.root_locator).expanduser()
        if not root.is_dir():
            raise ValueError(f"Drive mirror root does not exist: {root}")
        items: list[ConnectorItem] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            stat = path.stat()
            relative = path.relative_to(root)
            parent = "" if path.parent == root else str(path.parent.relative_to(root))
            items.append(
                ConnectorItem(
                    provider_id=str(relative).replace("\\", "/"),
                    name=path.name,
                    locator=str(path),
                    mime_type=_guess_mime(path),
                    byte_size=stat.st_size,
                    modified_time=str(int(stat.st_mtime)),
                    checksum="" if dry_run else sha256_file(path),
                    is_folder=False,
                    parents=(parent,),
                )
            )
        return ScanResult(
            items=items,
            cursor=cursor or "mirror:complete",
            dry_run=dry_run,
            completeness_status="COMPLETE",
            write_attempted=False,
        )

    def _scan_google(self, *, dry_run: bool, cursor: str) -> ScanResult:
        if self.api_list is None:
            raise RuntimeError(
                "google_api backend requires an injected read-only list function; "
                "credentials are never stored in the connector"
            )
        raw_items = self.api_list(cursor or self.connection.page_token)
        items = [_item_from_google_row(row) for row in raw_items]
        last = raw_items[-1] if raw_items else {}
        token = last.get("nextPageToken") if isinstance(last, dict) else None
        next_cursor = str(token or "google:complete")
        return ScanResult(
            items=items,
            cursor=next_cursor,
            dry_run=dry_run,
            completeness_status="COMPLETE" if next_cursor in {"", "google:complete"} else "PARTIAL",
            write_attempted=False,
        )

    def refuse_write(self, capability: str = "drive.write") -> PolicyDecision:
        decision = self.policy.decide(capability, write=True, connector_type=self.connector_type)
        if decision.allowed:  # pragma: no cover - policy is fail-closed
            raise DriveWriteRefused("policy unexpectedly allowed a Drive write")
        return decision

    def export_manifest(self, scan: ScanResult) -> str:
        payload = {
            "connector": self.connector_type,
            "backend": self.connection.backend,
            "dry_run": scan.dry_run,
            "cursor": scan.cursor,
            "items": [
                {
                    "provider_id": item.provider_id,
                    "name": item.name,
                    "locator": item.locator,
                    "byte_size": item.byte_size,
                    "checksum": item.checksum,
                }
                for item in scan.items
            ],
        }
        return json.dumps(payload, indent=2, sort_keys=True)


def _item_from_google_row(row: dict) -> ConnectorItem:
    mime_type = str(row.get("mimeType", ""))
    return ConnectorItem(
        provider_id=str(row.get("id", "")),
        name=str(row.get("name", "")),
        locator=f"gdrive://{row.get('id', '')}",
        mime_type=mime_type,
        byte_size=int(row.get("size", 0) or 0),
        modified_time=str(row.get("modifiedTime", "")),
        checksum=str(row.get("md5Checksum", "")),
        is_folder=mime_type.endswith("folder"),
        parents=tuple(row.get("parents") or ()),
    )


def _guess_mime(path: Path) -> str:
    return _MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")
