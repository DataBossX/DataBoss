"""Deterministic helpers shared across the Command Brain.

Time is injected through a :class:`Clock` so leases, approvals, and receipts are
testable without sleeping, and so a frozen clock produces byte-identical
receipts.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

ISO = "%Y-%m-%dT%H:%M:%S.%f%z"


def canonical_json(payload) -> str:
    """Stable JSON used for every hash in the system."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def canonical_hash(payload) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Clock:
    """Wall-clock source. Replaced by :class:`FrozenClock` in tests."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def now_iso(self) -> str:
        return self.now().isoformat()

    def plus_iso(self, seconds: float) -> str:
        return (self.now() + timedelta(seconds=seconds)).isoformat()


@dataclass
class FrozenClock(Clock):
    """Advance-on-demand clock. Never advances on its own."""

    current: datetime = field(
        default_factory=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> datetime:
        self.current = self.current + timedelta(seconds=seconds)
        return self.current


def parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_expired(expires_at: str | None, clock: Clock) -> bool:
    if not expires_at:
        return False
    return clock.now() >= parse_iso(expires_at)


class IdFactory:
    """Deterministic-by-default ID source.

    Command Brain records are correlated by ID across the ledger, so tests need
    them reproducible. ``seed`` produces a counter-based sequence; omitting it
    falls back to uuid4.
    """

    def __init__(self, seed: str | None = None):
        self._seed = seed
        self._counter = 0

    def new(self, prefix: str) -> str:
        self._counter += 1
        if self._seed is None:
            return f"{prefix}_{uuid.uuid4().hex[:16]}"
        digest = hashlib.sha256(f"{self._seed}:{prefix}:{self._counter}".encode()).hexdigest()
        return f"{prefix}_{digest[:16]}"


def stable_unit_interval(*parts: str) -> float:
    """Deterministic float in [0, 1) derived from the given parts.

    Used anywhere the system needs variation (e.g. simulated reader noise)
    without importing randomness, so every run reproduces exactly.
    """
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def truncate(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
