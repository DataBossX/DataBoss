"""Shared primitives: stable IDs, hashing, timestamps, canonical JSON."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def utcnow_iso() -> str:
    """UTC timestamp, second precision, e.g. '2026-07-11T14:03:22Z'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(obj) -> str:
    """Deterministic JSON — sorted keys, no whitespace drift — for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_id(prefix: str, *parts: str) -> str:
    """Deterministic ID from content parts, e.g. stable_id('AST', path, sha256).

    Same inputs always give the same ID, so re-running an inventory never
    mints duplicate identities for the same object.
    """
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def random_id(prefix: str) -> str:
    """Non-deterministic ID for events that are genuinely unique (runs, issues)."""
    return f"{prefix}-{uuid.uuid4().hex[:16]}"
