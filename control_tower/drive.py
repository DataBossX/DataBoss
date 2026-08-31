"""Drive access, wrapped so that every write is guarded and verified.

The tower never talks to a Drive SDK directly. It talks to a client interface,
which lets the whole control kernel be exercised offline and lets the canary
inject outages and corruption deliberately rather than waiting for them.
"""

import os

from .constants import (
    POLLED_FOLDER_ID,
    ControlTowerError,
    ReadbackMismatch,
)
from .safety import (
    assert_output_allowed,
    assert_pollable,
    assert_read_allowed,
    assert_uploadable,
    assert_write_allowed,
    canonical_drive_url,
    canonical_json_bytes,
    make_sha256_sidecar,
    redact_tree,
    sha256_hex,
    stamp_hold,
    verify_readback,
)


class DriveOutage(ControlTowerError):
    """The Drive surface was unreachable. Spooled evidence is retained."""


class DriveClient(object):
    """The interface the tower depends on. Implementations must not overwrite."""

    def list_children(self, folder_id):
        raise NotImplementedError

    def get_metadata(self, file_id):
        raise NotImplementedError

    def download(self, file_id):
        raise NotImplementedError

    def create(self, folder_id, name, payload, mime_type):
        raise NotImplementedError

    def find_by_name(self, folder_id, name):
        raise NotImplementedError


class OfflineDriveClient(DriveClient):
    """An in-memory Drive used by the selftest and the offline canary.

    It is intentionally strict: ``create`` refuses to replace an existing name,
    mirroring the append-only rule that the real control package relies on.
    """

    def __init__(self):
        self._files = {}
        self._seq = 0
        self.outage = False
        self.corrupt_readback = False

    def _check_outage(self):
        if self.outage:
            raise DriveOutage("simulated Drive outage")

    def seed(self, file_id, folder_id, name, payload=b"", mime_type="application/json"):
        self._files[file_id] = {
            "id": file_id,
            "parentId": folder_id,
            "title": name,
            "payload": bytes(payload),
            "mimeType": mime_type,
        }
        return self._files[file_id]

    def list_children(self, folder_id):
        self._check_outage()
        return [
            {
                "id": f["id"],
                "parentId": f["parentId"],
                "title": f["title"],
                "mimeType": f["mimeType"],
                "fileSize": str(len(f["payload"])),
            }
            for f in self._files.values()
            if f["parentId"] == folder_id
        ]

    def get_metadata(self, file_id):
        self._check_outage()
        found = self._files.get(file_id)
        if found is None:
            raise ControlTowerError("no such file: {0}".format(file_id))
        return {
            "id": found["id"],
            "parentId": found["parentId"],
            "title": found["title"],
            "mimeType": found["mimeType"],
            "fileSize": str(len(found["payload"])),
        }

    def download(self, file_id):
        self._check_outage()
        found = self._files.get(file_id)
        if found is None:
            raise ControlTowerError("no such file: {0}".format(file_id))
        if self.corrupt_readback:
            return found["payload"] + b"x"
        return found["payload"]

    def find_by_name(self, folder_id, name):
        self._check_outage()
        for f in self._files.values():
            if f["parentId"] == folder_id and f["title"] == name:
                return dict(f)
        return None

    def create(self, folder_id, name, payload, mime_type):
        self._check_outage()
        if self.find_by_name(folder_id, name) is not None:
            raise ControlTowerError(
                "append-only: a file named {0} already exists".format(name)
            )
        self._seq += 1
        file_id = "OFFLINE{0:016d}".format(self._seq)
        return self.seed(file_id, folder_id, name, payload, mime_type)


class SafeDriveWriter(object):
    """Spool first, then upload, then read back and compare exact bytes.

    Ordering matters. The spool write happens before the network call, so a
    Drive outage can never destroy evidence -- at worst the record is durable
    locally and marked pending, and a later run can complete it without
    overwriting anything.
    """

    def __init__(self, client, spool, leases=None, heartbeats=None, stop_flag=None):
        self.client = client
        self.spool = spool
        self.leases = leases
        self.heartbeats = heartbeats
        self.stop_flag = stop_flag

    def poll_queue(self):
        """Read the one canonical queue folder. Titles carry no authority."""
        if self.stop_flag is not None:
            self.stop_flag.require_not_stopped()
        folder_id = assert_pollable(POLLED_FOLDER_ID)
        return self.client.list_children(folder_id)

    def read(self, file_id, expected_parent=None):
        if self.stop_flag is not None:
            self.stop_flag.require_not_stopped()
        meta = self.client.get_metadata(file_id)
        if expected_parent is not None:
            assert_read_allowed(expected_parent)
            if meta.get("parentId") != expected_parent:
                raise ControlTowerError(
                    "file {0} is not in the expected folder".format(file_id)
                )
        else:
            assert_read_allowed(meta.get("parentId"))
        return meta, self.client.download(file_id)

    def emit_record(
        self,
        folder_id,
        name,
        record,
        lease=None,
        now=None,
        allowed_outputs=None,
        stop_flag=None,
        emit_sidecar=False,
    ):
        """Emit one control record with full durability and verification."""
        active_stop = stop_flag or self.stop_flag
        if active_stop is not None:
            active_stop.require_not_stopped()

        assert_write_allowed(folder_id)
        assert_output_allowed(folder_id, allowed_outputs)

        current_time = now if now is not None else 0
        if self.leases is not None and lease is not None:
            self.leases.require_valid(lease, current_time)
            if self.heartbeats is not None:
                self.heartbeats.pulse(lease.lease_id, current_time)

        safe = stamp_hold(redact_tree(record))
        payload = canonical_json_bytes(safe)
        digest = assert_uploadable(payload, filename=name, mime_type="application/json")

        # Durability before the network. A collision here is an error, never a
        # silent replacement.
        spooled = self.spool.put_record(name, payload)

        try:
            created = self.client.create(folder_id, name, payload, "application/json")
        except DriveOutage:
            self.spool.append(
                {
                    "event": "UPLOAD_PENDING_DRIVE_OUTAGE",
                    "name": name,
                    "folder_id": folder_id,
                    "sha256": digest,
                    "bytes": len(payload),
                    "spool_path": spooled["path"],
                }
            )
            raise

        returned = self.client.download(created["id"])
        readback_digest = verify_readback(payload, returned)
        if readback_digest != digest:  # pragma: no cover - defence in depth
            raise ReadbackMismatch("digest changed between upload and readback")

        result = {
            "event": "UPLOAD_VERIFIED",
            "name": name,
            "folder_id": folder_id,
            "drive_id": created["id"],
            "canonical_url": canonical_drive_url(created["id"]),
            "uploaded_bytes": len(payload),
            "readback_bytes": len(returned),
            "sha256": digest,
            "readback_sha256": readback_digest,
            "byte_exact_match": True,
        }
        self.spool.append(result)

        if emit_sidecar:
            sidecar_name = name + ".sha256"
            sidecar_payload = make_sha256_sidecar(name, payload).encode("utf-8")
            sidecar_spooled = self.spool.put_record(sidecar_name, sidecar_payload)
            try:
                sidecar_created = self.client.create(
                    folder_id, sidecar_name, sidecar_payload, "text/plain"
                )
                sidecar_returned = self.client.download(sidecar_created["id"])
                sidecar_readback_digest = verify_readback(sidecar_payload, sidecar_returned)
                sidecar_result = {
                    "event": "UPLOAD_VERIFIED",
                    "name": sidecar_name,
                    "folder_id": folder_id,
                    "drive_id": sidecar_created["id"],
                    "canonical_url": canonical_drive_url(sidecar_created["id"]),
                    "uploaded_bytes": len(sidecar_payload),
                    "readback_bytes": len(sidecar_returned),
                    "sha256": sha256_hex(sidecar_payload),
                    "readback_sha256": sidecar_readback_digest,
                    "byte_exact_match": True,
                }
                self.spool.append(sidecar_result)
                result["sidecar"] = sidecar_result
            except DriveOutage:
                self.spool.append(
                    {
                        "event": "UPLOAD_PENDING_DRIVE_OUTAGE",
                        "name": sidecar_name,
                        "folder_id": folder_id,
                        "sha256": sha256_hex(sidecar_payload),
                        "bytes": len(sidecar_payload),
                        "spool_path": sidecar_spooled["path"],
                    }
                )
                raise

        return result

    def emit_record_with_sidecar(
        self,
        folder_id,
        name,
        record,
        lease=None,
        now=None,
        allowed_outputs=None,
        stop_flag=None,
    ):
        """Emit a record and its corresponding .sha256 sidecar."""
        return self.emit_record(
            folder_id,
            name,
            record,
            lease=lease,
            now=now,
            allowed_outputs=allowed_outputs,
            stop_flag=stop_flag,
            emit_sidecar=True,
        )

    def recover_pending_uploads(self):
        """Scan spool journal for pending uploads caused by outages and complete them."""
        pending = self.spool.get_pending_uploads()
        recovered = []
        for item in pending:
            name = item["name"]
            folder_id = item["folder_id"]
            spool_path = item["spool_path"]
            if not os.path.exists(spool_path):
                continue
            with open(spool_path, "rb") as f:
                payload = f.read()
            mime_type = "text/plain" if name.endswith(".sha256") else "application/json"
            created = self.client.create(folder_id, name, payload, mime_type)
            returned = self.client.download(created["id"])
            readback_digest = verify_readback(payload, returned)
            res = {
                "event": "UPLOAD_VERIFIED",
                "name": name,
                "folder_id": folder_id,
                "drive_id": created["id"],
                "canonical_url": canonical_drive_url(created["id"]),
                "uploaded_bytes": len(payload),
                "readback_bytes": len(returned),
                "sha256": sha256_hex(payload),
                "readback_sha256": readback_digest,
                "byte_exact_match": True,
                "recovered_from_outage": True,
            }
            self.spool.append(res)
            recovered.append(res)
        return recovered

    @staticmethod
    def digest_of(record):
        return sha256_hex(canonical_json_bytes(record))
