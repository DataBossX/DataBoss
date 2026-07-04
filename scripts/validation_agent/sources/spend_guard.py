"""
Spend guard — mathematically enforces the $100.00 cumulative API/document cap.

All arithmetic uses Decimal (never float). Cumulative spend is derived from the
append-only spend_ledger, so it cannot be understated by editing state. Every
estimate, charge, and block is written to the ledger and api_calls tables.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from config.settings import Settings, ABSOLUTE_SPEND_CAP_USD
from db.db_client import DatabaseManager, utcnow

CENTS = Decimal("0.01")


def money(x) -> Decimal:
    return Decimal(str(x)).quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass
class SpendDecision:
    allowed: bool
    reason: str
    amount: Decimal
    cumulative_before: Decimal
    cumulative_after: Decimal
    cap: Decimal
    requires_approval: bool = False


class SpendCapExceeded(RuntimeError):
    pass


class SpendGuard:
    def __init__(self, db: DatabaseManager, settings: Settings, run_id: Optional[str] = None):
        self.db = db
        self.settings = settings
        self.run_id = run_id
        # Effective cap is the smaller of the configured cap and the absolute law.
        self.cap = min(money(settings.api_cap_usd), money(ABSOLUTE_SPEND_CAP_USD))

    # ---- cumulative spend from the ledger (charges only) ----
    def cumulative(self) -> Decimal:
        rows = self.db.query(
            "SELECT amount_usd FROM spend_ledger WHERE kind = 'charge'")
        total = Decimal("0.00")
        for r in rows:
            total += money(r["amount_usd"])
        return money(total)

    def remaining(self) -> Decimal:
        return money(self.cap - self.cumulative())

    # ---- decision logic ----
    def evaluate(self, amount, description: str = "") -> SpendDecision:
        amount = money(amount)
        before = self.cumulative()
        after = money(before + amount)
        if amount < 0:
            return SpendDecision(False, "Negative amount refused", amount, before, before, self.cap)
        if after > self.cap:
            return SpendDecision(False,
                                 f"Would exceed cap: {before} + {amount} = {after} > {self.cap}",
                                 amount, before, after, self.cap)
        # Approval policy for paid calls (live mode only).
        requires_approval = False
        if amount > 0:
            if not self.settings.auto_approve_paid:
                requires_approval = True
            elif amount > money(self.settings.per_document_limit_usd):
                requires_approval = True
        return SpendDecision(True, "within cap", amount, before, after, self.cap, requires_approval)

    def can_spend(self, amount) -> bool:
        return self.evaluate(amount).allowed

    # ---- ledger writes ----
    def record_estimate(self, amount, description: str = "") -> int:
        amount = money(amount)
        return self.db.insert("spend_ledger", {
            "run_id": self.run_id, "kind": "estimate",
            "amount_usd": str(amount), "cumulative_usd": str(self.cumulative()),
            "description": description, "created_at": utcnow(),
        })

    def record_charge(self, amount, description: str = "", provider: str = "okcounty",
                      endpoint: str = "") -> Decimal:
        """Record an actual paid charge. Refuses (and logs a block) if over cap."""
        decision = self.evaluate(amount, description)
        if not decision.allowed:
            self._log_block(decision, description, provider, endpoint)
            raise SpendCapExceeded(decision.reason)
        new_cumulative = decision.cumulative_after
        self.db.insert("spend_ledger", {
            "run_id": self.run_id, "kind": "charge",
            "amount_usd": str(decision.amount), "cumulative_usd": str(new_cumulative),
            "description": description, "created_at": utcnow(),
        })
        self.db.insert("api_calls", {
            "run_id": self.run_id, "provider": provider, "endpoint": endpoint,
            "request_summary": description, "outcome": "ok",
            "cost_usd": str(decision.amount), "created_at": utcnow(),
        })
        return new_cumulative

    def _log_block(self, decision: SpendDecision, description: str,
                   provider: str, endpoint: str) -> None:
        self.db.insert("spend_ledger", {
            "run_id": self.run_id, "kind": "blocked",
            "amount_usd": str(decision.amount), "cumulative_usd": str(decision.cumulative_before),
            "description": f"BLOCKED: {description} — {decision.reason}", "created_at": utcnow(),
        })
        self.db.insert("api_calls", {
            "run_id": self.run_id, "provider": provider, "endpoint": endpoint,
            "request_summary": description, "outcome": "blocked",
            "cost_usd": str(decision.amount), "created_at": utcnow(),
        })
