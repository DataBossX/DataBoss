"""Spend guard: mathematically enforces the $100.00 cumulative API/document cap.

Every prospective paid call must be pre-authorized here. The guard uses Decimal
arithmetic (no float drift), records an append-only spend-ledger entry for both
approved and blocked attempts, and NEVER lets cumulative spend exceed the cap.
No paid call happens without going through :meth:`authorize`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from config.settings import ABSOLUTE_API_CAP_USD


def _q(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class SpendDecision:
    approved: bool
    amount: Decimal
    cumulative_before: Decimal
    cumulative_after: Decimal
    cap: Decimal
    reason: str


class SpendCapExceeded(RuntimeError):
    pass


class SpendGuard:
    def __init__(self, db=None, run_id: str | None = None,
                 cap_usd: Decimal | float | str = ABSOLUTE_API_CAP_USD,
                 per_doc_limit: Decimal | float | str | None = None,
                 auto_approve: bool = False):
        self.cap = min(_q(cap_usd), ABSOLUTE_API_CAP_USD)
        self.per_doc_limit = _q(per_doc_limit) if per_doc_limit is not None else None
        self.auto_approve = bool(auto_approve)
        self.db = db
        self.run_id = run_id
        # Seed cumulative from the durable ledger if a DB is attached.
        self._cumulative = _q(db.cumulative_spend(run_id)) if db else Decimal("0.00")

    @property
    def cumulative(self) -> Decimal:
        return self._cumulative

    def remaining(self) -> Decimal:
        return (self.cap - self._cumulative).quantize(Decimal("0.01"))

    def can_afford(self, amount) -> bool:
        return (self._cumulative + _q(amount)) <= self.cap

    def evaluate(self, amount, *, examiner_approved: bool = False) -> SpendDecision:
        """Decide whether a paid call may proceed — WITHOUT recording spend.

        Approval requires that (a) it fits under the cumulative cap AND
        (b) either the examiner approved it, or auto-approve is on and the
        amount is under the per-document limit.
        """
        amt = _q(amount)
        before = self._cumulative
        after = (before + amt).quantize(Decimal("0.01"))

        if amt < 0:
            return SpendDecision(False, amt, before, before, self.cap,
                                 "Negative spend rejected.")
        if after > self.cap:
            return SpendDecision(
                False, amt, before, before, self.cap,
                f"Cap block: {before} + {amt} = {after} exceeds cap {self.cap}.",
            )
        # Under cap. Now the approval policy.
        if examiner_approved:
            return SpendDecision(True, amt, before, after, self.cap,
                                 "Examiner-approved.")
        if self.auto_approve:
            if self.per_doc_limit is not None and amt > self.per_doc_limit:
                return SpendDecision(
                    False, amt, before, before, self.cap,
                    f"Auto-approve denied: {amt} exceeds per-doc limit "
                    f"{self.per_doc_limit}.",
                )
            return SpendDecision(True, amt, before, after, self.cap,
                                 "Auto-approved under per-doc limit.")
        return SpendDecision(False, amt, before, before, self.cap,
                             "No approval: interactive approval required.")

    def authorize(self, amount, description: str, kind: str = "document",
                  *, examiner_approved: bool = False) -> SpendDecision:
        """Evaluate AND commit the decision to the append-only ledger.

        On approval, cumulative spend is advanced. On block, a blocked entry is
        still recorded (failed retrieval is never hidden). Cumulative can never
        exceed the cap by construction.
        """
        decision = self.evaluate(amount, examiner_approved=examiner_approved)
        if decision.approved:
            # Double-check the invariant before committing.
            if decision.cumulative_after > self.cap:
                raise SpendCapExceeded(
                    f"Refusing to exceed cap: {decision.cumulative_after} > "
                    f"{self.cap}"
                )
            self._cumulative = decision.cumulative_after
        if self.db is not None:
            self.db.record_spend(
                self.run_id, kind, description,
                float(decision.amount),
                float(self._cumulative),
                approved=decision.approved,
            )
        return decision
