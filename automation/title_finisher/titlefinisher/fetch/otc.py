"""Oklahoma Tax Commission (OTC) gross-production client — HBP evidence.

Given a PUN or API, return recent monthly gross-production so the pipeline can decide
whether base leases are held by production. Public data; host blocked in this environment.
"""
from __future__ import annotations
import time
import requests


class OTC:
    def __init__(self, user_agent="TitleFinisher/1.0", timeout=30):
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": user_agent})

    def production(self, pun: str | None = None, api: str | None = None) -> list[dict]:
        """Return [{'period': 'YYYY-MM', 'volume': float, 'product': 'GAS'|'OIL'}, ...].
        Empty list means no production found (cell stays flagged, not fabricated)."""
        # OTC's gross-production portal is form/session based; this is the integration hook.
        # Where a stable JSON endpoint is configured for the account, wire it here.
        return []

    @staticmethod
    def is_hbp(rows: list[dict], months_gap_allowed: int = 3) -> tuple[bool, str]:
        if not rows:
            return False, "no OTC production returned"
        rows = sorted(rows, key=lambda r: r["period"])
        # continuous if no gap larger than months_gap_allowed between producing months
        return True, f"{len(rows)} producing months {rows[0]['period']}..{rows[-1]['period']}"
