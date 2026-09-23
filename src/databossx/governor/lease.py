from __future__ import annotations

from datetime import datetime, timedelta, timezone

from databossx.database import DataBossDatabase


class StaleWriter(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def acquire_lease(db: DataBossDatabase, scope: str, worker_id: str, ttl_seconds: int = 900) -> int:
    current = db.fetchone(
        """
        SELECT worker_id, fence, expires_at
          FROM writer_leases
         WHERE scope = ?
         ORDER BY fence DESC
         LIMIT 1
        """,
        (scope,),
    )
    if (
        current is not None
        and current["expires_at"] > _utc_now().isoformat()
        and current["worker_id"] != worker_id
    ):
        raise StaleWriter("scope already leased")
    next_fence = int(current["fence"]) + 1 if current else 1
    expires = (_utc_now() + timedelta(seconds=ttl_seconds)).isoformat()
    db.execute(
        """
        INSERT INTO writer_leases (scope, worker_id, fence, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (scope, worker_id, next_fence, expires),
    )
    return next_fence


def assert_lease(db: DataBossDatabase, scope: str, worker_id: str, fence: int) -> None:
    row = db.fetchone(
        """
        SELECT worker_id, fence, expires_at
          FROM writer_leases
         WHERE scope = ?
         ORDER BY fence DESC
         LIMIT 1
        """,
        (scope,),
    )
    if row is None:
        raise StaleWriter("no lease")
    if int(row["fence"]) != fence or row["worker_id"] != worker_id:
        raise StaleWriter("stale writer")
    if row["expires_at"] <= _utc_now().isoformat():
        raise StaleWriter("expired lease")
