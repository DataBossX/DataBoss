"""Exact-byte canonical startup reconstruction for the durable runner."""

import json
from typing import Any, Dict, Iterable, Mapping, Optional

from .constants import ControlTowerError
from .safety import canonical_json_bytes, sha256_hex

NONCANONICAL_SECTION32_SHA256 = (
    "24055B0A6F345C82E42AC720DE156C2FA59719F2B7E43D8F3D72F31A651177A4"
)
NONCANONICAL_CLASSIFICATION = "NONCANONICAL_OUTPUT_PRESERVE_NO_PROMOTION"


def reject_noncanonical_package(record: Optional[Mapping[str, Any]]) -> None:
    """Reject the known noncanonical package before any authority mutation."""
    record = record or {}
    digest = str(record.get("candidate_sha256") or record.get("sha256") or "").upper()
    classification = str(record.get("classification") or "")
    if digest == NONCANONICAL_SECTION32_SHA256 or classification == NONCANONICAL_CLASSIFICATION:
        raise ControlTowerError("noncanonical Section 32 package is observation-only")


class CanonicalStartupReconstructor(object):
    """Verify pinned Drive objects, then reconstruct durable facts once.

    Each pin binds parent, ID, title, bytes, hash, schema and semantic kind.
    Verification completes for the entire set before one durable transaction;
    duplicates or changed bytes therefore derive no partial authority.
    """

    def __init__(
        self,
        client: Any,
        store: Any,
        pins: Iterable[Mapping[str, Any]],
    ) -> None:
        self.client = client
        self.store = store
        self.pins = tuple(pins or ())
        self._result: Optional[Dict[str, Any]] = None

    def ensure_reconstructed(self) -> Dict[str, Any]:
        if self._result is not None:
            return dict(self._result)
        verified = []
        retired = []
        records = []
        for pin in self.pins:
            reject_noncanonical_package(pin)
            folder_id = pin["parent_id"]
            title = pin["name"]
            matches = [
                item
                for item in self.client.list_children(folder_id)
                if item.get("title") == title
            ]
            if len(matches) != 1:
                raise ControlTowerError(
                    "canonical reconstruction requires exactly one {0}/{1}".format(
                        folder_id, title
                    )
                )
            meta = matches[0]
            if meta.get("id") != pin["file_id"] or meta.get("parentId") != folder_id:
                raise ControlTowerError("canonical reconstruction identity mismatch")
            payload = self.client.download(meta["id"])
            if len(payload) != int(pin["bytes"]):
                raise ControlTowerError("canonical reconstruction byte-size mismatch")
            digest = sha256_hex(payload)
            if digest.upper() != str(pin["sha256"]).upper():
                raise ControlTowerError("canonical reconstruction hash mismatch")
            try:
                decoded = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                raise ControlTowerError("canonical reconstruction payload is not JSON") from None
            if decoded.get("schema") != pin["schema"]:
                raise ControlTowerError("canonical reconstruction schema mismatch")
            semantic = pin.get("semantic_identity")
            if semantic and decoded.get("semantic_identity") != semantic:
                raise ControlTowerError("canonical reconstruction semantic mismatch")
            if pin.get("kind") == "retired_command":
                retired.append(pin["command_id"])
            elif pin.get("kind") == "terminal_receipt":
                records.append(decoded)
            verified.append({"file_id": meta["id"], "sha256": digest, "bytes": len(payload)})

        fingerprint = sha256_hex(canonical_json_bytes(verified))
        result = self.store.reconcile_canonical_once(
            fingerprint, records, retired_command_ids=retired
        )
        result.update(
            {
                "verified": len(verified),
                "pins_sha256": fingerprint,
            }
        )
        self._result = result
        return dict(result)
