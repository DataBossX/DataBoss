"""Tamper-evident, hash-bound receipts.

Receipts are canonical JSON. ``receipt_sha256`` is the SHA-256 of the body
with that field omitted. Verification recomputes the digest; any edit fails.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .hashing import sha256_bytes


SCHEMA_ID = "dbx.engine_receipt"
SCHEMA_VERSION = "1.0.0"


class ReceiptError(ValueError):
    """Receipt is missing, malformed, or has been tampered with."""


def canonical_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_canonical(value: Any) -> str:
    return sha256_bytes(canonical_dumps(value).encode("utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _unsigned_body(body: Mapping[str, Any]) -> dict[str, Any]:
    return {key: body[key] for key in body if key != "receipt_sha256"}


def receipt_digest(body: Mapping[str, Any]) -> str:
    return sha256_canonical(_unsigned_body(body))


def seal_receipt(body: Mapping[str, Any]) -> dict[str, Any]:
    sealed = _unsigned_body(body)
    sealed["receipt_sha256"] = sha256_canonical(sealed)
    return sealed


def verify_receipt(sealed: Mapping[str, Any]) -> str:
    digest = sealed.get("receipt_sha256")
    if not digest or not isinstance(digest, str):
        raise ReceiptError("receipt_sha256 is required")
    expected = receipt_digest(sealed)
    if digest != expected:
        raise ReceiptError(f"receipt hash mismatch: expected {expected}, found {digest}")
    return expected


def write_sealed_receipt(path: str | Path, body: Mapping[str, Any]) -> dict[str, Any]:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sealed = seal_receipt(body)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(sealed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(destination)
    verify_receipt(json.loads(destination.read_text(encoding="utf-8")))
    return sealed


def read_and_verify_receipt(path: str | Path) -> dict[str, Any]:
    sealed = json.loads(Path(path).read_text(encoding="utf-8"))
    verify_receipt(sealed)
    return sealed


@dataclass(frozen=True)
class EngineReceipt:
    receipt_id: str
    kind: str
    status: str
    project_id: str | None
    input_hashes: tuple[str, ...]
    output_hashes: tuple[str, ...]
    body: dict[str, Any]

    def to_sealed(self) -> dict[str, Any]:
        return seal_receipt(self.body)


def build_engine_receipt(
    *,
    kind: str,
    status: str,
    input_hashes: list[str] | tuple[str, ...],
    output_hashes: list[str] | tuple[str, ...] = (),
    project_id: str | None = None,
    extra: Mapping[str, Any] | None = None,
    receipt_id: str | None = None,
    created_at: str | None = None,
) -> EngineReceipt:
    """Build a receipt that always binds input hashes, including failures."""
    rid = receipt_id or uuid4().hex
    body: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "receipt_id": rid,
        "kind": kind,
        "status": status,
        "project_id": project_id,
        "created_at": created_at or utc_now(),
        "input_hashes": list(input_hashes),
        "output_hashes": list(output_hashes),
    }
    if extra:
        for key, value in extra.items():
            if key in body or key == "receipt_sha256":
                raise ReceiptError(f"reserved receipt field: {key}")
            body[key] = value
    return EngineReceipt(
        receipt_id=rid,
        kind=kind,
        status=status,
        project_id=project_id,
        input_hashes=tuple(input_hashes),
        output_hashes=tuple(output_hashes),
        body=body,
    )
