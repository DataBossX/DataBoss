"""Image-spend tracker with a hard $100 cap.

Every paid document-image fetch must go through :class:`SpendTracker`. The cap
is enforced *before* spending (``can_spend``) and each purchase is appended to a
durable spend log so the total survives restarts. The tracker never lets the
running total exceed the cap.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .config import IMAGE_SPEND_CAP
from .schema import SHEETS


class SpendCapExceeded(Exception):
    pass


class SpendTracker:
    def __init__(self, cap: float = IMAGE_SPEND_CAP,
                 log_path: Optional[Path] = None) -> None:
        self.cap = float(cap)
        self.log_path = Path(log_path) if log_path else None
        self.entries: List[Dict] = []
        self.total = 0.0
        if self.log_path and self.log_path.exists():
            self._load()

    def _load(self) -> None:
        try:
            with self.log_path.open(newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    self.entries.append(row)
                    self.total += float(row.get("cost_usd", 0) or 0)
        except Exception:
            pass

    @property
    def remaining(self) -> float:
        return round(max(self.cap - self.total, 0.0), 2)

    def can_spend(self, amount: float) -> bool:
        return (self.total + float(amount)) <= self.cap + 1e-9

    def record(self, item: str, cost: float, image_id: str = "",
               source: str = "", note: str = "") -> Dict:
        """Record a purchase. Raises if it would breach the cap."""
        cost = float(cost)
        if not self.can_spend(cost):
            raise SpendCapExceeded(
                f"${cost:.2f} for '{item}' would exceed ${self.cap:.2f} cap "
                f"(spent ${self.total:.2f})"
            )
        self.total = round(self.total + cost, 2)
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
            "item": item,
            "image_id": image_id,
            "cost_usd": round(cost, 2),
            "running_total_usd": self.total,
            "cap_remaining_usd": self.remaining,
            "source": source,
            "note": note,
        }
        self.entries.append(entry)
        self._append(entry)
        return entry

    def _append(self, entry: Dict) -> None:
        if not self.log_path:
            return
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            new = not self.log_path.exists()
            with self.log_path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=SHEETS["Spend Log"])
                if new:
                    writer.writeheader()
                writer.writerow(entry)
        except OSError:
            pass

    def rows(self) -> List[Dict]:
        """Spend-log rows shaped for the workbook Spend Log sheet."""
        cols = SHEETS["Spend Log"]
        return [{c: e.get(c, "") for c in cols} for e in self.entries]

    def summary(self) -> Dict:
        return {
            "cap_usd": self.cap,
            "spent_usd": round(self.total, 2),
            "remaining_usd": self.remaining,
            "purchases": len(self.entries),
        }
