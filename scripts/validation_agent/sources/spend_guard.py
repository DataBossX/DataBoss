"""APISpendGuard -- the $100 hard mathematical ceiling (Golden Law #6).

Before any paid retrieval, the guard:
    1. Checks whether the document is free-to-view (cost 0 -> always allowed).
    2. Estimates the cost of the fetch.
    3. Reads the cumulative spend from the append-only ledger.
    4. Blocks the fetch if ``spent + estimate`` would exceed the cap, logging
       the decision either way.

There is no code path that spends money without first passing ``authorize`` and
recording the decision, so a silent paid call is impossible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config.settings import config
from ..db.audit_logger import AuditLogger


@dataclass
class SpendDecision:
    allowed: bool
    reason: str
    estimated_cost: float
    already_spent: float
    projected_total: float
    cap: float
    free_to_view: bool


class APISpendGuard:
    def __init__(self, audit: Optional[AuditLogger] = None,
                 cap: Optional[float] = None) -> None:
        self.audit = audit or AuditLogger()
        self.cap = cap if cap is not None else config.api_hard_cap_usd

    def already_spent(self) -> float:
        return self.audit.total_spend()

    def remaining(self) -> float:
        return round(self.cap - self.already_spent(), 4)

    def authorize(self, estimated_cost: float, *, free_to_view: bool = False,
                  run_id: Optional[str] = None, description: str = "") -> SpendDecision:
        spent = self.already_spent()
        if free_to_view or estimated_cost <= 0:
            decision = SpendDecision(
                allowed=True, reason="Free-to-view document; no charge.",
                estimated_cost=0.0, already_spent=spent, projected_total=spent,
                cap=self.cap, free_to_view=True)
            self._log(run_id, decision, description)
            return decision

        # Compare the *unrounded* projection so a sub-cent overage can never be
        # rounded down to exactly the cap and slip through the hard ceiling.
        raw_projected = spent + estimated_cost
        projected = round(raw_projected, 4)
        if raw_projected > self.cap:
            decision = SpendDecision(
                allowed=False,
                reason=(f"Blocked: projected ${projected:.2f} would exceed the "
                        f"${self.cap:.2f} cap (spent ${spent:.2f})."),
                estimated_cost=estimated_cost, already_spent=spent,
                projected_total=projected, cap=self.cap, free_to_view=False)
            self._log(run_id, decision, description)
            return decision

        decision = SpendDecision(
            allowed=True,
            reason=(f"Allowed: ${estimated_cost:.2f} within cap "
                    f"(spent ${spent:.2f}, projected ${projected:.2f})."),
            estimated_cost=estimated_cost, already_spent=spent,
            projected_total=projected, cap=self.cap, free_to_view=False)
        self._log(run_id, decision, description)
        return decision

    def commit_spend(self, amount: float, description: str,
                     run_id: Optional[str] = None) -> None:
        """Record an actually-incurred charge on the append-only ledger.

        Guarded so a caller cannot push cumulative spend past the cap even if
        the estimate was low.
        """
        if amount <= 0:
            return
        projected = self.already_spent() + amount
        if projected > self.cap:
            raise RuntimeError(
                f"Refusing to record ${amount:.2f}: would breach ${self.cap:.2f} cap.")
        self.audit.log_spend(run_id, amount, description)

    def _log(self, run_id: Optional[str], decision: SpendDecision,
             description: str) -> None:
        self.audit.event(
            "spend_decision",
            f"{'ALLOW' if decision.allowed else 'BLOCK'}: {decision.reason}",
            run_id=run_id,
            data={"description": description, "estimated_cost": decision.estimated_cost,
                  "already_spent": decision.already_spent,
                  "projected_total": decision.projected_total, "cap": decision.cap,
                  "free_to_view": decision.free_to_view})
