"""Drive control-room bridge.

The publish protocol is deliberately paranoid, because desktop sync completing
is not the same thing as bytes being correct:

1. stage locally, 2. hash the staged bytes, 3. upload an immutable versioned
object, 4. **read it back from the store**, 5. compare digests, 6. only then
move the manifest pointer.

A mismatch at step 5 raises :class:`ReadbackMismatch` and the pointer is never
moved, so a partial upload can never become the current version.

Authority note: no real Drive client is wired in this lane. The
``00_AUTHORIZATION_REQUEST...NOT_YET_ACTIVE`` document confers no authority, and
the directive forbids creating or moving Drive folders without it. The port
below is exercised against an in-memory fake so the protocol is proven and the
real client can be dropped in when authorization exists.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping, Optional, Protocol

from .canonical import iso, sha256_bytes, sha256_file, utc_now
from .errors import PathNotAllowed, ReadbackMismatch, SchemaValidationError

#: Canonical control-room layout. Folders are NOT created by this module.
CONTROL_ROOM_FOLDERS = (
    "00_COMMAND_INBOX",
    "01_ACTIVE_JOBS",
    "02_DECISIONS",
    "03_RECEIPTS",
    "04_ACCEPTED_ARTIFACTS",
    "05_HOLDS_AND_AUTHORITY",
    "06_SYSTEM_SNAPSHOTS",
    "99_ARCHIVE",
)

REQUIRED_COMMAND_FIELDS = (
    "command_id", "idempotency_key", "created_at", "actor",
    "schema_version", "content_sha256", "risk_class", "status",
)


@dataclass
class DriveObject:
    file_id: str
    name: str
    parent_id: str
    version: str
    mime_type: str
    byte_size: int
    data: bytes = b""


class DriveClient(Protocol):
    """Minimal port. A real implementation must never overwrite in place."""

    def list_children(self, parent_id: str) -> list: ...
    def upload_new_version(self, *, parent_id: str, name: str, data: bytes,
                           mime_type: str) -> DriveObject: ...
    def download(self, file_id: str) -> bytes: ...
    def get_metadata(self, file_id: str) -> DriveObject: ...


class InMemoryDriveClient:
    """Deterministic fake used for tests and the demo slice.

    Supports fault injection so read-back mismatch and truncated upload are
    exercised as real code paths rather than assumed to work.
    """

    def __init__(self):
        self._objects: dict = {}
        self._children: dict = {}
        self._counter = 0
        self.corrupt_next_readback = False
        self.truncate_next_upload = False

    def list_children(self, parent_id: str) -> list:
        return [self._objects[fid] for fid in self._children.get(parent_id, [])]

    def upload_new_version(self, *, parent_id: str, name: str, data: bytes, mime_type: str) -> DriveObject:
        self._counter += 1
        payload = data[: max(0, len(data) - 8)] if self.truncate_next_upload else data
        self.truncate_next_upload = False
        file_id = f"drvfile_{self._counter:08d}"
        obj = DriveObject(
            file_id=file_id, name=name, parent_id=parent_id, version=f"v{self._counter}",
            mime_type=mime_type, byte_size=len(payload), data=payload,
        )
        self._objects[file_id] = obj
        self._children.setdefault(parent_id, []).append(file_id)
        return obj

    def download(self, file_id: str) -> bytes:
        data = self._objects[file_id].data
        if self.corrupt_next_readback:
            self.corrupt_next_readback = False
            return data + b"\x00corrupted"
        return data

    def get_metadata(self, file_id: str) -> DriveObject:
        return self._objects[file_id]


@dataclass
class PublishResult:
    logical_id: str
    local_sha256: str
    drive_file_id: str
    drive_version: str
    drive_parent_id: str
    drive_mime_type: str
    byte_size: int
    readback_sha256: str
    readback_at: str
    verified: bool
    manifest_pointer_updated: bool


@dataclass
class Manifest:
    """Pointer table. Only advanced after a verified read-back."""

    entries: dict = field(default_factory=dict)

    def current(self, logical_id: str) -> Optional[Mapping]:
        return self.entries.get(logical_id)

    def advance(self, logical_id: str, entry: Mapping) -> None:
        self.entries[logical_id] = dict(entry)


class DriveBridge:
    def __init__(self, client: DriveClient, *, staging_dir: str, manifest: Optional[Manifest] = None):
        self.client = client
        self.staging_dir = staging_dir
        self.manifest = manifest or Manifest()
        os.makedirs(staging_dir, exist_ok=True)

    # ----------------------------------------------------------------- import
    def validate_command_file(self, raw: bytes, *, declared_sha256: str) -> dict:
        """Validate a Drive command before it becomes a database record.

        A file appearing in a folder is never sufficient to execute. The hash
        must match, the schema must be complete, and the caller still has to
        create a canonical record afterwards.
        """
        import json

        actual = sha256_bytes(raw)
        if actual != declared_sha256:
            raise ReadbackMismatch(
                f"command file hash {actual} does not match declared {declared_sha256}"
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise SchemaValidationError(f"command file is not valid JSON: {exc}") from exc

        missing = [f for f in REQUIRED_COMMAND_FIELDS if f not in payload]
        if missing:
            raise SchemaValidationError(f"command file missing required fields: {missing}")
        if payload.get("risk_class") == "PROHIBITED":
            raise SchemaValidationError("command file declares a prohibited risk class")
        return payload

    # ---------------------------------------------------------------- publish
    def stage(self, logical_id: str, data: bytes) -> str:
        """Write bytes into the staging area under a validated relative name."""
        if "/" in logical_id or "\\" in logical_id or ".." in logical_id:
            raise PathNotAllowed(f"logical id {logical_id!r} may not contain path separators")
        path = os.path.join(self.staging_dir, f"{logical_id}.staged")
        tmp = path + ".tmp"
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)  # atomic within the staging directory
        return path

    def publish(
        self,
        *,
        logical_id: str,
        data: bytes,
        parent_id: str,
        name: str,
        mime_type: str = "application/json",
    ) -> PublishResult:
        """Stage, hash, upload, read back, verify, then advance the pointer."""
        staged_path = self.stage(logical_id, data)
        local_sha = sha256_file(staged_path)

        obj = self.client.upload_new_version(
            parent_id=parent_id, name=name, data=data, mime_type=mime_type
        )

        # The verification that actually matters: bytes from the store, not
        # from memory, not from a sync status flag.
        readback = self.client.download(obj.file_id)
        readback_sha = sha256_bytes(readback)
        readback_at = iso(utc_now())
        verified = readback_sha == local_sha

        if not verified:
            # Pointer stays where it was. The bad version is left in place for
            # forensics rather than deleted.
            raise ReadbackMismatch(
                f"Drive read-back mismatch for {logical_id}: uploaded {local_sha}, "
                f"read back {readback_sha}. Manifest pointer NOT advanced."
            )

        entry = {
            "logical_id": logical_id,
            "sha256": local_sha,
            "drive_file_id": obj.file_id,
            "drive_version": obj.version,
            "drive_parent_id": obj.parent_id,
            "drive_mime_type": obj.mime_type,
            "byte_size": obj.byte_size,
            "readback_sha256": readback_sha,
            "readback_at": readback_at,
        }
        self.manifest.advance(logical_id, entry)

        return PublishResult(
            logical_id=logical_id,
            local_sha256=local_sha,
            drive_file_id=obj.file_id,
            drive_version=obj.version,
            drive_parent_id=obj.parent_id,
            drive_mime_type=obj.mime_type,
            byte_size=obj.byte_size,
            readback_sha256=readback_sha,
            readback_at=readback_at,
            verified=True,
            manifest_pointer_updated=True,
        )

    # ------------------------------------------------------------ reconcile
    def reconcile(self, parent_id: str) -> dict:
        """Periodic sweep that does not trust change notifications.

        Notification channels drop events and expire. Reconciliation compares
        the manifest against what the store actually holds, so a missed event
        is eventually corrected instead of silently losing a version.
        """
        seen = {obj.file_id: obj for obj in self.client.list_children(parent_id)}
        tracked = {e["drive_file_id"] for e in self.manifest.entries.values()}
        return {
            "parent_id": parent_id,
            "objects_in_store": len(seen),
            "tracked_in_manifest": len(tracked),
            "untracked_file_ids": sorted(set(seen) - tracked),
            "missing_from_store": sorted(tracked - set(seen)),
            "reconciled_at": iso(utc_now()),
        }


def plan_control_room(existing_children: Mapping[str, str], parent_id: str) -> dict:
    """Compute an idempotent folder plan WITHOUT creating anything.

    Returns what *would* be created and which names collide with folders that
    already exist, so a human can settle naming before any Drive mutation.
    """
    present = set(existing_children)
    to_create = [name for name in CONTROL_ROOM_FOLDERS if name not in present]
    conflicts = []
    if "receipts" in present and "03_RECEIPTS" not in present:
        conflicts.append({
            "existing": "receipts",
            "proposed": "03_RECEIPTS",
            "resolution": "OWNER DECISION REQUIRED - do not auto-rename or duplicate.",
        })
    return {
        "parent_id": parent_id,
        "already_present": sorted(present & set(CONTROL_ROOM_FOLDERS)),
        "would_create": to_create,
        "conflicts": conflicts,
        "created": [],
        "authority": "NOT_GRANTED - no folder was created or moved.",
    }
