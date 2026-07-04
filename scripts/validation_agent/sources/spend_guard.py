"""Spend guard — mathematically enforces the $100.00 cumulative cap.

All money is :class:`decimal.Decimal`. A paid call is authorized only if
``cumulative + amount <= cap``. Every decision (allowed or blocked) is written
to the append-only ``spend_ledger`` and ``api_calls`` tables. The cumulative
total is derived from the ledger itself, so it survives restarts and cannot be
silently reset.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from db.audit_logger import AuditLogger

TWO = Decimal("0.01")


class SpendCapExceeded(RuntimeError):
    pass


def _money(v) -> Decimal:
    return Decimal(str(v)).quantize(TWO, rounding=ROUND_HALF_UP)


class SpendGuard:
    def __init__(self, audit: AuditLogger, cap_usd: Decimal, run_id: Optional[str] = None):
        self.audit = audit
        self.cap = _money(cap_usd)
        # Absolute law: never above the hard ceiling.
        if self.cap > Decimal("100.00"):
            self.cap = Decimal("100.00")
        self.run_id = run_id

    def cumulative(self) -> Decimal:
        rows = self.audit.db.query(
            "SELECT amount_usd FROM spend_ledger WHERE allowed = 1")
        total = Decimal("0.00")
        for r in rows:
            total += _money(r["amount_usd"])
        return _money(total)

    def remaining(self) -> Decimal:
        return _money(self.cap - self.cumulative())

    def can_afford(self, amount_usd) -> bool:
        amt = _money(amount_usd)
        if amt < 0:
            return False
        return (self.cumulative() + amt) <= self.cap

    def authorize(self, description: str, amount_usd, *, per_doc_limit: Optional[Decimal] = None,
                  auto_approve: bool = False) -> bool:
        """Attempt to authorize a paid charge. Returns True only if allowed.

        Records the decision to the ledger either way. Raising is reserved for
        callers that treat over-cap as fatal; most callers check the bool.
        """
        amt = _money(amount_usd)
        allowed = True
        reason = "authorized"
        if amt < 0:
            allowed, reason = False, "negative amount"
        elif per_doc_limit is not None and amt > _money(per_doc_limit):
            allowed, reason = False, f"exceeds per-doc limit {per_doc_limit}"
        elif not auto_approve:
            allowed, reason = False, "manual approval required"
        elif (self.cumulative() + amt) > self.cap:
            allowed, reason = False, "would exceed cumulative cap"

        new_cumulative = self.cumulative() + (amt if allowed else Decimal("0.00"))
        self.audit.spend(self.run_id, f"{description} [{reason}]", str(amt),
                         str(_money(new_cumulative)), allowed)
        self.audit.api_call(self.run_id, "spend_guard", None, paid=True,
                            estimated_cost_usd=str(amt),
                            outcome="executed" if allowed else "blocked", detail=reason)
        return allowed

    def record_free_call(self, service: str, endpoint: Optional[str], outcome: str,
                         detail: Optional[str] = None) -> None:
        self.audit.api_call(self.run_id, service, endpoint, paid=False,
                            estimated_cost_usd="0.00", outcome=outcome, detail=detail)
