"""One-writer lease / fence enforcement.

One mutable production target = one writer. A lease binds (target, writer) with
an expiry and a fence token that must strictly increase, so a stale writer that
wakes up late cannot commit over a newer one.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path


class LeaseError(RuntimeError):
    pass


class CollisionError(LeaseError):
    pass


@dataclass
class Lease:
    target: str
    writer: str
    fence: int
    acquired_at: float
    expires_at: float
    preimage_sha256: str = ""

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at


class LeaseStore:
    """File-backed lease. Acquisition is atomic via O_CREAT|O_EXCL."""

    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, target: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in target)
        return self.dir / f"{safe}.lease.json"

    def read(self, target: str) -> Lease | None:
        p = self._path(target)
        if not p.exists():
            return None
        return Lease(**json.loads(p.read_text()))

    def acquire(self, target: str, writer: str, *, ttl: float = 900.0,
                preimage_sha256: str = "") -> Lease:
        p = self._path(target)
        cur = self.read(target)
        if cur and not cur.expired:
            if cur.writer != writer:
                raise CollisionError(
                    f"target {target!r} is already leased by {cur.writer!r} "
                    f"(fence {cur.fence}, {cur.expires_at - time.time():.0f}s left)")
            return self.renew(target, writer, ttl=ttl)

        fence = (cur.fence + 1) if cur else 1
        lease = Lease(target=target, writer=writer, fence=fence,
                      acquired_at=time.time(), expires_at=time.time() + ttl,
                      preimage_sha256=preimage_sha256)
        tmp = p.with_suffix(".tmp")
        try:
            fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as e:
            raise CollisionError(f"concurrent acquisition on {target!r}") from e
        with os.fdopen(fd, "w") as fh:
            json.dump(asdict(lease), fh)
        os.replace(tmp, p)
        return lease

    def renew(self, target: str, writer: str, *, ttl: float = 900.0) -> Lease:
        cur = self.read(target)
        if cur is None:
            raise LeaseError(f"no lease to renew for {target!r}")
        if cur.writer != writer:
            raise CollisionError(f"{writer!r} cannot renew a lease held by {cur.writer!r}")
        cur.expires_at = time.time() + ttl
        self._path(target).write_text(json.dumps(asdict(cur)))
        return cur

    def release(self, target: str, writer: str) -> None:
        cur = self.read(target)
        if cur is None:
            return
        if cur.writer != writer:
            raise CollisionError(f"{writer!r} cannot release a lease held by {cur.writer!r}")
        # Keep the record so the fence keeps increasing; mark it expired.
        cur.expires_at = 0.0
        self._path(target).write_text(json.dumps(asdict(cur)))

    def guard_commit(self, target: str, writer: str, fence: int,
                     preimage_sha256: str = "") -> None:
        """Raise unless this writer still legitimately owns the target."""
        cur = self.read(target)
        if cur is None:
            raise LeaseError(f"no lease held for {target!r}")
        if cur.writer != writer:
            raise CollisionError(f"target {target!r} now held by {cur.writer!r}")
        if cur.expired:
            raise LeaseError(f"lease on {target!r} expired; re-acquire before committing")
        if fence < cur.fence:
            raise CollisionError(f"stale fence {fence} < current {cur.fence}")
        if preimage_sha256 and cur.preimage_sha256 and preimage_sha256 != cur.preimage_sha256:
            raise CollisionError(
                f"preimage drift: {preimage_sha256} != leased {cur.preimage_sha256}")

    def writer_count(self, target: str) -> int:
        cur = self.read(target)
        return 0 if cur is None or cur.expired else 1
