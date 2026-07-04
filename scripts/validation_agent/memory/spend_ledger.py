"""Append-only API spend ledger enforcing the hard $100 cap (Golden Law + C5)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from .. import config


class SpendCapExceeded(RuntimeError):
    """Raised when a charge would cross the configured API spend cap."""


class SpendLedger:
    def __init__(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        cap: Decimal = config.API_SPEND_CAP_USD,
    ) -> None:
        self._conn = conn
        self._run_id = run_id
        self._cap = cap

    def spent(self) -> Decimal:
        cur = self._conn.execute(
            "SELECT COALESCE(SUM(CAST(cost_usd AS REAL)), 0) AS s "
            "FROM spend_ledger WHERE run_id=?",
            (self._run_id,),
        )
        return Decimal(str(cur.fetchone()["s"])).quantize(Decimal("0.01"))

    def remaining(self) -> Decimal:
        return (self._cap - self.spent()).quantize(Decimal("0.01"))

    def can_afford(self, cost: Decimal) -> bool:
        return self.spent() + Decimal(cost) <= self._cap

    def charge(
        self, cost: Decimal, evidence_hash: Optional[str] = None, note: str = ""
    ) -> None:
        cost = Decimal(cost)
        if self.spent() + cost > self._cap:
            raise SpendCapExceeded(
                f"charge ${cost} would exceed cap ${self._cap} "
                f"(spent ${self.spent()})"
            )
        self._conn.execute(
            "INSERT INTO spend_ledger(ts, run_id, cost_usd, evidence_hash, note) "
            "VALUES(?,?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(),
                self._run_id,
                str(cost),
                evidence_hash,
                note,
            ),
        )
        self._conn.commit()
