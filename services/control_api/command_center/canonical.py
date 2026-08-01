"""Canonical serialization, hashing, identifiers, and clock.

Hash stability is a control primitive here: approvals, envelopes, and receipts
are all bound by SHA-256 over a canonical JSON encoding, so the encoding must
never drift. Sorted keys, no insignificant whitespace, UTF-8, and rejection of
non-finite floats give the same bytes for the same logical object.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import os
import secrets
from decimal import Decimal
from fractions import Fraction
from typing import Any


def utc_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def iso(ts: _dt.datetime) -> str:
    """RFC 3339 in UTC with a trailing Z, second-stable across platforms."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=_dt.timezone.utc)
    return ts.astimezone(_dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_iso(text: str) -> _dt.datetime:
    cleaned = text.replace("Z", "+00:00")
    parsed = _dt.datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc)


class _CanonicalEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:  # noqa: D102
        if isinstance(o, _dt.datetime):
            return iso(o)
        if isinstance(o, Fraction):
            # Exact title arithmetic must never become binary floating point.
            return {"__fraction__": [o.numerator, o.denominator]}
        if isinstance(o, Decimal):
            return {"__decimal__": str(o)}
        if isinstance(o, (set, frozenset)):
            return sorted(o)
        raise TypeError(f"{type(o).__name__} is not canonically serializable")


def _reject_non_finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite float cannot be canonically encoded")
    if isinstance(value, dict):
        for item in value.values():
            _reject_non_finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_non_finite(item)


def canonical_json(obj: Any) -> str:
    """Deterministic JSON text used for every hash binding in the kernel."""
    _reject_non_finite(obj)
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        cls=_CanonicalEncoder,
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of(obj: Any) -> str:
    return sha256_text(canonical_json(obj))


def content_hash(payload: dict, exclude: str = "content_sha256") -> str:
    """Hash a payload excluding its own hash field, so it can carry the result."""
    trimmed = {k: v for k, v in payload.items() if k != exclude}
    return sha256_of(trimmed)


def sha256_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(16)}"


def new_nonce() -> str:
    return secrets.token_hex(16)


def constant_time_equals(left: str, right: str) -> bool:
    return secrets.compare_digest(left, right)


def stable_env_id(name: str, default: str) -> str:
    return os.environ.get(name, default)
