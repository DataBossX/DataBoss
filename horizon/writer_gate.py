"""Writer-gate exclusivity for a single mutable client target.

ONE MUTABLE TARGET = ONE WRITER. A mutation endpoint must refuse to run
unless every one of these signals holds at the moment of the check:

* the writer instance requesting mutation actually holds the lease for its
  seat;
* the lease has not expired;
* the writer's heartbeat is recent enough to prove it is still alive;
* the exact preimage bytes are unchanged since the lease was acquired
  (the post-acquisition unchanged-preimage check);
* the exact target identity matches what the writer acquired the lease
  against;
* no collision (a second concurrent claimant) has been observed.

Any single unknown, stale, or mismatched signal denies the gate -- unknown
is never treated as passing. Nothing here is client-specific: seat names,
instance ids, and hashes are all supplied by the caller.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Optional


def _as_utc(value: Optional[_dt.datetime]) -> Optional[_dt.datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=_dt.timezone.utc)
    return value


class WriterGateDenied(RuntimeError):
    """Raised by :func:`authorize_mutation` when the gate is not clear."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("writer gate denied: " + (", ".join(reasons) or "unknown"))


@dataclass
class WriterGateState:
    """One point-in-time observation of a writer's claim on one seat."""

    writer_seat: str
    writer_instance: str
    exact_preimage_sha256: str
    observed_preimage_sha256: str
    exact_target_id: str
    observed_target_id: str
    lease_holder: Optional[str] = None
    lease_expires_at: Optional[_dt.datetime] = None
    heartbeat_at: Optional[_dt.datetime] = None
    collision_count: int = 0
    max_heartbeat_age_seconds: float = 90.0
    now: _dt.datetime = field(default_factory=lambda: _dt.datetime.now(_dt.timezone.utc))

    def __post_init__(self) -> None:
        # A naive datetime (no tzinfo) compared against an aware one raises
        # TypeError -- turning a HOLD into an unhandled 500 instead of a
        # denial. Treat any naive input as UTC rather than guessing wrong.
        self.now = _as_utc(self.now)
        self.lease_expires_at = _as_utc(self.lease_expires_at)
        self.heartbeat_at = _as_utc(self.heartbeat_at)

    # -- individual signals --------------------------------------------------
    @property
    def lease_held_by_self(self) -> bool:
        return bool(self.lease_holder) and self.lease_holder == self.writer_instance

    @property
    def lease_unexpired(self) -> bool:
        return self.lease_expires_at is not None and self.now < self.lease_expires_at

    @property
    def heartbeat_age_seconds(self) -> Optional[float]:
        if self.heartbeat_at is None:
            return None
        return (self.now - self.heartbeat_at).total_seconds()

    @property
    def heartbeat_fresh(self) -> bool:
        age = self.heartbeat_age_seconds
        # A negative age (a heartbeat timestamped after `now`) is clock skew,
        # not proof of life -- fail closed rather than trust it.
        return age is not None and 0 <= age <= self.max_heartbeat_age_seconds

    @property
    def preimage_unchanged(self) -> bool:
        return (
            bool(self.exact_preimage_sha256)
            and bool(self.observed_preimage_sha256)
            and self.exact_preimage_sha256 == self.observed_preimage_sha256
        )

    @property
    def target_matches(self) -> bool:
        return (
            bool(self.exact_target_id)
            and bool(self.observed_target_id)
            and self.exact_target_id == self.observed_target_id
        )

    @property
    def collision_zero(self) -> bool:
        return self.collision_count == 0

    # -- combined verdict -----------------------------------------------------
    def reasons_denied(self) -> list[str]:
        reasons: list[str] = []
        if not self.lease_held_by_self:
            reasons.append("LEASE_NOT_HELD_BY_INSTANCE")
        if not self.lease_unexpired:
            reasons.append("LEASE_EXPIRED_OR_ABSENT")
        if not self.heartbeat_fresh:
            reasons.append("HEARTBEAT_STALE_OR_ABSENT")
        if not self.preimage_unchanged:
            reasons.append("PREIMAGE_CHANGED_OR_UNKNOWN")
        if not self.target_matches:
            reasons.append("TARGET_MISMATCH_OR_UNKNOWN")
        if not self.collision_zero:
            reasons.append("COLLISION_DETECTED")
        return reasons

    @property
    def passed(self) -> bool:
        return not self.reasons_denied()

    def as_dict(self) -> dict[str, Any]:
        return {
            "writer_seat": self.writer_seat,
            "writer_instance": self.writer_instance,
            "lease_held_by_self": self.lease_held_by_self,
            "lease_unexpired": self.lease_unexpired,
            "heartbeat_age_seconds": self.heartbeat_age_seconds,
            "heartbeat_fresh": self.heartbeat_fresh,
            "preimage_unchanged": self.preimage_unchanged,
            "target_matches": self.target_matches,
            "collision_count": self.collision_count,
            "collision_zero": self.collision_zero,
            "passed": self.passed,
            "reasons_denied": self.reasons_denied(),
        }


def authorize_mutation(state: WriterGateState) -> WriterGateState:
    """Return *state* if the gate is clear; raise :class:`WriterGateDenied` otherwise.

    Call this immediately before any client-mutating write, using a freshly
    observed ``state`` rather than a cached one -- a stale check is not a
    check.
    """
    reasons = state.reasons_denied()
    if reasons:
        raise WriterGateDenied(reasons)
    return state
