"""Single-writer leases and fencing tokens.

A *lane* is anything that can only have one writer at a time: a worktree, a
workbook, an artifact family. Acquiring a lane mints a monotonically increasing
fencing token. A worker that resumes after a pause presents its token; if the
lane has since moved on, the token is stale and the write is refused even though
the worker still believes it holds the lease.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import FencingTokenError, LeaseError, WriterCollision
from .util import Clock, is_expired


@dataclass(frozen=True)
class Lease:
    lease_id: str
    lane_id: str
    worker_id: str
    fencing_token: int
    acquired_at: str
    expires_at: str

    def to_dict(self) -> dict:
        return {
            "lease_id": self.lease_id,
            "lane_id": self.lane_id,
            "worker_id": self.worker_id,
            "fencing_token": self.fencing_token,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
        }


class LeaseManager:
    def __init__(self, store, clock: Clock | None = None):
        self.store = store
        self.clock = clock or store.clock

    # -- internals --------------------------------------------------------
    def _active_row(self, lane_id: str):
        rows = self.store.fetchall(
            """
            SELECT * FROM cb_leases
             WHERE lane_id = ? AND released_at IS NULL
             ORDER BY fencing_token DESC
            """,
            (lane_id,),
        )
        for row in rows:
            if not is_expired(row["expires_at"], self.clock):
                return row
        return None

    def _next_token(self, lane_id: str) -> int:
        row = self.store.fetchone(
            "SELECT last_token FROM cb_lane_tokens WHERE lane_id = ?", (lane_id,)
        )
        token = (row["last_token"] if row else 0) + 1
        self.store.execute(
            "INSERT OR REPLACE INTO cb_lane_tokens (lane_id, last_token) VALUES (?, ?)",
            (lane_id, token),
        )
        return token

    # -- API --------------------------------------------------------------
    def acquire(self, lane_id: str, worker_id: str, ttl_seconds: int = 900) -> Lease:
        active = self._active_row(lane_id)
        if active is not None:
            if active["worker_id"] == worker_id:
                raise WriterCollision(
                    f"Worker {worker_id!r} already holds lane {lane_id!r}; "
                    "reuse the existing lease rather than acquiring twice.",
                    detail={"lane_id": lane_id, "worker_id": worker_id},
                )
            raise WriterCollision(
                f"Lane {lane_id!r} is already leased by {active['worker_id']!r}. "
                "Two writers may not share a worktree or artifact lane.",
                detail={
                    "lane_id": lane_id,
                    "held_by": active["worker_id"],
                    "expires_at": active["expires_at"],
                },
            )
        token = self._next_token(lane_id)
        lease_id = self.store.new_id("lease")
        acquired_at = self.clock.now_iso()
        expires_at = self.clock.plus_iso(ttl_seconds)
        self.store.execute(
            """
            INSERT INTO cb_leases (
                lease_id, lane_id, worker_id, fencing_token, acquired_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (lease_id, lane_id, worker_id, token, acquired_at, expires_at),
        )
        lease = Lease(lease_id, lane_id, worker_id, token, acquired_at, expires_at)
        self.store.audit("lease.acquired", "lane", lane_id, lease.to_dict())
        return lease

    def validate(self, lease: Lease) -> Lease:
        row = self.store.fetchone("SELECT * FROM cb_leases WHERE lease_id = ?", (lease.lease_id,))
        if row is None:
            raise LeaseError(
                f"Lease {lease.lease_id!r} is unknown.", detail={"lease_id": lease.lease_id}
            )
        if row["released_at"] is not None:
            raise LeaseError(
                f"Lease {lease.lease_id!r} has been released.", detail={"lease_id": lease.lease_id}
            )
        if is_expired(row["expires_at"], self.clock):
            raise LeaseError(
                f"Lease {lease.lease_id!r} expired at {row['expires_at']}.",
                detail={"lease_id": lease.lease_id, "expires_at": row["expires_at"]},
            )
        token_row = self.store.fetchone(
            "SELECT last_token FROM cb_lane_tokens WHERE lane_id = ?", (lease.lane_id,)
        )
        current = token_row["last_token"] if token_row else 0
        if lease.fencing_token < current:
            raise FencingTokenError(
                f"Fencing token {lease.fencing_token} is stale for lane {lease.lane_id!r}; "
                f"current token is {current}.",
                detail={
                    "lane_id": lease.lane_id,
                    "presented_token": lease.fencing_token,
                    "current_token": current,
                },
            )
        return lease

    def heartbeat(self, lease: Lease, ttl_seconds: int = 900) -> Lease:
        self.validate(lease)
        expires_at = self.clock.plus_iso(ttl_seconds)
        self.store.execute(
            "UPDATE cb_leases SET expires_at = ? WHERE lease_id = ?",
            (expires_at, lease.lease_id),
        )
        return Lease(
            lease.lease_id,
            lease.lane_id,
            lease.worker_id,
            lease.fencing_token,
            lease.acquired_at,
            expires_at,
        )

    def release(self, lease: Lease) -> None:
        self.store.execute(
            "UPDATE cb_leases SET released_at = ? WHERE lease_id = ?",
            (self.clock.now_iso(), lease.lease_id),
        )
        self.store.audit("lease.released", "lane", lease.lane_id, lease.to_dict())

    def steal_expired(self, lane_id: str, worker_id: str, ttl_seconds: int = 900) -> Lease:
        """Take over a lane whose lease has expired, bumping the fencing token.

        The previous holder's token becomes stale, so a late write from the
        stalled worker is refused by :meth:`validate`.
        """
        if self._active_row(lane_id) is not None:
            raise WriterCollision(
                f"Lane {lane_id!r} still has a live lease.", detail={"lane_id": lane_id}
            )
        self.store.execute(
            "UPDATE cb_leases SET released_at = ? WHERE lane_id = ? AND released_at IS NULL",
            (self.clock.now_iso(), lane_id),
        )
        return self.acquire(lane_id, worker_id, ttl_seconds)

    def active_lanes(self) -> list[dict]:
        rows = self.store.fetchall(
            "SELECT * FROM cb_leases WHERE released_at IS NULL ORDER BY lane_id, fencing_token DESC"
        )
        return [dict(row) for row in rows if not is_expired(row["expires_at"], self.clock)]
