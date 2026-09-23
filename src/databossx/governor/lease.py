from __future__ import annotations

from datetime import datetime, timedelta, timezone

from databossx.database import DataBossDatabase


class StaleWriter(RuntimeError):
    pass


def acquire_lease(db: DataBossDatabase, scope: str, worker_id: str, ttl_seconds: int = 900) -> int:
    row = db.fetchone(
        "SELECT COALESCE(MAX(fence), 0) AS fence FROM writer_leases WHERE scope = ?",
        (scope,),
    )
    next_fence = int(row["fence"]) + 1 if row else 1
    expires = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
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
    if row["expires_at"] <= datetime.now(timezone.utc).isoformat():
        raise StaleWriter("expired lease")
