"""Economic enforcement. Every paid external call passes through here.

Hard cap: $100.00. If cumulative spend + proposed spend exceeds the cap, the
request is blocked, ``SPEND_CAP_REACHED`` is logged, and the caller must route
to escalation. There are no silent paid calls: every allowed and blocked
decision is written to the append-only ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from config.settings import Settings
from db.audit_logger import AuditLogger

_CENTS = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class SpendDecision:
    allowed: bool
    reason: str
    proposed_amount_usd: Decimal
    cumulative_before_usd: Decimal
    cumulative_after_usd: Decimal
    cap_usd: Decimal

    @property
    def blocked(self) -> bool:
        return not self.allowed


class SpendGuard:
    """Gatekeeper for all paid source usage."""

    def __init__(self, settings: Settings, audit: AuditLogger, run_id: Optional[str] = None) -> None:
        self.settings = settings
        self.audit = audit
        self.run_id = run_id
        self.cap = _money(settings.api_cap_usd)

    def cumulative_spend(self) -> Decimal:
        return _money(self.audit.cumulative_spend(self.run_id))

    def _policy_permits_paid(self, proposed: Decimal) -> Optional[str]:
        """Return a block reason string if policy forbids the paid call, else None."""
        if not self.settings.live_source_mode or self.settings.dry_run:
            return "POLICY_DRY_RUN"
        if not self.settings.has_okcounty_credentials():
            return "MISSING_CREDENTIALS"
        if not self.settings.auto_approve_paid_docs:
            # Manual per-doc approval required unless within the auto limit.
            if proposed > self.settings.per_document_auto_approval_limit_usd:
                return "MANUAL_APPROVAL_REQUIRED"
        return None

    def check(self, proposed_amount_usd: Decimal, description: str) -> SpendDecision:
        """Evaluate a proposed paid call. Logs the decision. Never spends here."""
        proposed = _money(Decimal(proposed_amount_usd))
        if proposed < 0:
            proposed = Decimal("0.00")
        cumulative = self.cumulative_spend()
        projected = _money(cumulative + proposed)

        # Cap check is absolute and first.
        if projected > self.cap:
            reason = "SPEND_CAP_REACHED"
            decision = SpendDecision(
                allowed=False,
                reason=reason,
                proposed_amount_usd=proposed,
                cumulative_before_usd=cumulative,
                cumulative_after_usd=cumulative,
                cap_usd=self.cap,
            )
            self.audit.log_spend(
                decision="BLOCKED",
                proposed_amount_usd=proposed,
                amount_usd=Decimal("0.00"),
                reason=reason,
                description=description,
                run_id=self.run_id,
            )
            return decision

        # Policy check (dry-run, credentials, approval).
        policy_block = self._policy_permits_paid(proposed) if proposed > 0 else None
        if policy_block:
            decision = SpendDecision(
                allowed=False,
                reason=policy_block,
                proposed_amount_usd=proposed,
                cumulative_before_usd=cumulative,
                cumulative_after_usd=cumulative,
                cap_usd=self.cap,
            )
            self.audit.log_spend(
                decision="BLOCKED",
                proposed_amount_usd=proposed,
                amount_usd=Decimal("0.00"),
                reason=policy_block,
                description=description,
                run_id=self.run_id,
            )
            return decision

        decision = SpendDecision(
            allowed=True,
            reason="ALLOWED",
            proposed_amount_usd=proposed,
            cumulative_before_usd=cumulative,
            cumulative_after_usd=projected,
            cap_usd=self.cap,
        )
        return decision

    def commit(self, amount_usd: Decimal, description: str) -> Decimal:
        """Record an actually-incurred cost after an allowed call succeeded.

        Re-checks the cap defensively; refuses to commit an overspend.
        """
        amount = _money(Decimal(amount_usd))
        cumulative = self.cumulative_spend()
        if _money(cumulative + amount) > self.cap:
            self.audit.log_spend(
                decision="BLOCKED",
                proposed_amount_usd=amount,
                amount_usd=Decimal("0.00"),
                reason="SPEND_CAP_REACHED",
                description=f"commit refused: {description}",
                run_id=self.run_id,
            )
            raise SpendCapExceeded(
                f"commit of {amount} would exceed cap {self.cap} "
                f"(cumulative {cumulative})"
            )
        self.audit.log_spend(
            decision="ALLOWED",
            proposed_amount_usd=amount,
            amount_usd=amount,
            reason="COMMITTED",
            description=description,
            run_id=self.run_id,
        )
        return _money(cumulative + amount)


class SpendCapExceeded(RuntimeError):
    pass
