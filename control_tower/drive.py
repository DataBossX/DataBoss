"""Drive access wrapped with lease/fence guards and exact-byte recovery."""

from .constants import (
    POLLED_FOLDER_ID,
    ControlTowerError,
    FencingViolation,
    LeaseExpired,
    ReadbackMismatch,
)
from .safety import (
    assert_pollable,
    assert_read_allowed,
    assert_uploadable,
    assert_write_allowed,
    canonical_drive_url,
    canonical_json_bytes,
    redact_tree,
    sha256_hex,
    stamp_hold,
    verify_readback,
)


class DriveOutage(ControlTowerError):
    """The Drive surface was unreachable. Spooled evidence is retained."""


class DriveClient(object):
    """The interface the tower depends on. Implementations must not overwrite."""

    is_offline = False

    def list_children(self, folder_id):
        raise NotImplementedError

    def get_metadata(self, file_id):
        raise NotImplementedError

    def download(self, file_id):
        raise NotImplementedError

    def create(self, folder_id, name, payload, mime_type):
        raise NotImplementedError

    def find_by_name(self, folder_id, name):
        matches = self.find_all_by_name(folder_id, name)
        return matches[0] if matches else None

    def find_all_by_name(self, folder_id, name):
        return [item for item in self.list_children(folder_id) if item.get("title") == name]


class OfflineDriveClient(DriveClient):
    """Strict in-memory Drive used only by synthetic tests and canaries."""

    is_offline = True

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

    def find_all_by_name(self, folder_id, name):
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
            if f["parentId"] == folder_id and f["title"] == name
        ]

    def find_by_name(self, folder_id, name):
        matches = self.find_all_by_name(folder_id, name)
        return matches[0] if matches else None

    def create(self, folder_id, name, payload, mime_type):
        self._check_outage()
        if self.find_all_by_name(folder_id, name):
            raise ControlTowerError(
                "append-only: a file named {0} already exists".format(name)
            )
        self._seq += 1
        file_id = "OFFLINE{0:016d}".format(self._seq)
        return self.seed(file_id, folder_id, name, payload, mime_type)


class SafeDriveWriter(object):
    """Spool first, require the current lease/fence, upload and verify.

    Live clients can never write unless this writer is bound by the durable
    runner to the exact durable store used by its lease/fencing registry. The
    offline client remains usable for synthetic self-tests, including the
    legacy runner. Pending spool records are resumed with
    :meth:`recover_record`, which adopts one exact existing Drive object or
    uploads only when absent. Recovery may be bound to a digest persisted in
    durable claim state, so stale or altered spool bytes fail closed.
    """

    def __init__(self, client, spool, leases=None):
        self.client = client
        self.spool = spool
        self.leases = leases
        self._durable_runner_store = None

    @property
    def durable_runner_bound(self):
        return (
            self._durable_runner_store is not None
            and self.leases is not None
            and self._durable_runner_store is getattr(self.leases, "store", None)
        )

    def bind_durable_runner(self, store):
        if store is None:
            raise LeaseExpired("durable runner binding requires a durable store")
        if self.leases is None or store is not getattr(self.leases, "store", None):
            raise LeaseExpired("durable runner binding does not match lease state")
        self._durable_runner_store = store
        return True

    def poll_queue(self):
        folder_id = assert_pollable(POLLED_FOLDER_ID)
        return self.client.list_children(folder_id)

    def read(self, file_id, expected_parent=None):
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

    def _require_lease(self, lease, now):
        effective_now = now if now is not None else 0
        if self.client.is_offline and self.leases is None:
            if lease is None:
                return None
            if not lease.is_valid(effective_now):
                raise LeaseExpired(
                    "offline lease {0} expired at {1}; now is {2}".format(
                        lease.lease_id, lease.expires_at, effective_now
                    )
                )
            return lease
        if not self.client.is_offline and not self.durable_runner_bound:
            raise LeaseExpired("live writer is not bound to the durable control store")
        if self.leases is None:
            raise LeaseExpired("live writer has no lease registry")
        if not self.client.is_offline and getattr(self.leases, "store", None) is None:
            raise LeaseExpired("live writer lease registry is not durable")
        if lease is None:
            raise LeaseExpired("protected write requires a lease")
        return self.leases.require_valid(lease, effective_now)

    def _named_matches(self, folder_id, name):
        matches = self.client.find_all_by_name(folder_id, name)
        if len(matches) > 1:
            raise ControlTowerError(
                "duplicate Drive objects named {0} in folder {1}".format(name, folder_id)
            )
        return matches

    def _verify_match(self, match, folder_id, name, payload, digest):
        if match.get("parentId") != folder_id or match.get("title") != name:
            raise ControlTowerError("Drive match identity changed during reconciliation")
        returned = self.client.download(match["id"])
        readback_digest = verify_readback(payload, returned)
        if readback_digest != digest:
            raise ReadbackMismatch("existing Drive object has mismatched bytes")
        return {
            "event": "UPLOAD_VERIFIED",
            "name": name,
            "folder_id": folder_id,
            "drive_id": match["id"],
            "canonical_url": canonical_drive_url(match["id"]),
            "uploaded_bytes": len(payload),
            "readback_bytes": len(returned),
            "sha256": digest,
            "readback_sha256": readback_digest,
            "byte_exact_match": True,
        }

    def _record_orphan(self, folder_id, name, digest, created, reason):
        event = {
            "event": "ORPHAN_CREATED_AFTER_AUTHORITY_LOSS",
            "name": name,
            "folder_id": folder_id,
            "drive_id": None if created is None else created.get("id"),
            "sha256": digest,
            "reason": str(reason),
            "reconciliation_required": True,
        }
        self.spool.append(event)
        return event

    def emit_record(self, folder_id, name, record, lease=None, now=None):
        """Emit a new record. Existing spool names remain collision-safe."""
        assert_write_allowed(folder_id)
        self._require_lease(lease, now)
        safe = stamp_hold(redact_tree(record))
        payload = canonical_json_bytes(safe)
        digest = assert_uploadable(payload, filename=name, mime_type="application/json")
        spooled = self.spool.put_record(name, payload)
        try:
            return self._upload_or_adopt(
                folder_id, name, payload, digest, spooled, lease=lease, now=now
            )
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

    def recover_record(
        self, folder_id, name, lease=None, now=None, expected_sha256=None
    ):
        """Resume one spooled record, optionally bound to durable-state digest."""
        assert_write_allowed(folder_id)
        self._require_lease(lease, now)
        payload = self.spool.read_record(name)
        digest = assert_uploadable(payload, filename=name, mime_type="application/json")
        if expected_sha256 is not None and digest != expected_sha256:
            raise ReadbackMismatch(
                "spooled record digest {0} does not match durable expected {1}".format(
                    digest, expected_sha256
                )
            )
        spooled = self.spool.verify_record(name, payload)
        try:
            return self._upload_or_adopt(
                folder_id, name, payload, digest, spooled, lease=lease, now=now
            )
        except DriveOutage:
            self.spool.append(
                {
                    "event": "RECOVERY_PENDING_DRIVE_OUTAGE",
                    "name": name,
                    "folder_id": folder_id,
                    "sha256": digest,
                    "bytes": len(payload),
                }
            )
            raise

    def _upload_or_adopt(self, folder_id, name, payload, digest, spooled, lease=None, now=None):
        # Network-window fencing: every external boundary is bracketed by a
        # fresh durable lease/fence read. A race-created object is retained as
        # an explicit orphan and can never advance terminal state.
        self._require_lease(lease, now)
        matches = self._named_matches(folder_id, name)
        if matches:
            result = self._verify_match(matches[0], folder_id, name, payload, digest)
            self._require_lease(lease, now)
            result["event"] = "UPLOAD_RECOVERED_EXACT_MATCH"
            self.spool.append(result)
            return result

        self._require_lease(lease, now)
        created = None
        try:
            created = self.client.create(folder_id, name, payload, "application/json")
        except ControlTowerError:
            # Another process may have won the create race. Reconcile once and
            # accept only one exact object; otherwise propagate the failure.
            matches = self._named_matches(folder_id, name)
            if not matches:
                raise
            result = self._verify_match(matches[0], folder_id, name, payload, digest)
            self._require_lease(lease, now)
            result["event"] = "UPLOAD_RECOVERED_AFTER_CREATE_RACE"
            self.spool.append(result)
            return result

        try:
            self._require_lease(lease, now)
            matches = self._named_matches(folder_id, name)
            if len(matches) != 1 or matches[0].get("id") != created.get("id"):
                raise ControlTowerError("Drive create did not converge to one stable object")
            result = self._verify_match(matches[0], folder_id, name, payload, digest)
            self._require_lease(lease, now)
        except (LeaseExpired, FencingViolation) as exc:
            self._record_orphan(folder_id, name, digest, created, exc)
            raise
        result["spool_path"] = spooled["path"]
        self.spool.append(result)
        return result

    @staticmethod
    def digest_of(record):
        return sha256_hex(canonical_json_bytes(record))
