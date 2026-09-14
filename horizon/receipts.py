"""Hash-bound run receipts for Horizon controlled loops."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


class ReceiptError(ValueError):
    """Receipt is missing a digest or no longer matches its body."""


def canonical_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def receipt_digest(body: Mapping[str, Any]) -> str:
    payload = {key: body[key] for key in body if key != "receipt_sha256"}
    return hashlib.sha256(canonical_dumps(payload).encode("utf-8")).hexdigest()


def seal_receipt(body: Mapping[str, Any]) -> dict[str, Any]:
    sealed = {key: body[key] for key in body if key != "receipt_sha256"}
    sealed["receipt_sha256"] = receipt_digest(sealed)
    return sealed


def verify_receipt(sealed: Mapping[str, Any]) -> str:
    digest = sealed.get("receipt_sha256")
    if not digest or not isinstance(digest, str):
        raise ReceiptError("receipt_sha256 is required")
    expected = receipt_digest(sealed)
    if digest != expected:
        raise ReceiptError(f"receipt hash mismatch: expected {expected}, found {digest}")
    return expected
