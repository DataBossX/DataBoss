"""Authorized OKCounty source client.

Lawful, configured access only. This client:

* never scrapes or circumvents access controls;
* only issues a request when live-source mode is enabled AND credentials exist
  AND the spend guard allows the spend;
* surfaces authentication failures rather than hiding them;
* never invents document contents — a dry-run or missing-credential state
  returns a structured "not retrieved" result.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from config.settings import Settings
from db.audit_logger import AuditLogger
from sources.spend_guard import SpendGuard

_DEFAULT_DOC_COST = Decimal("2.50")


@dataclass
class FetchResult:
    reference_key: str
    outcome: str  # retrieved | blocked | dry_run | auth_failure | not_configured
    detail: str
    cost_usd: Decimal = Decimal("0.00")
    file_path: Optional[str] = None


class OKCountyClient:
    def __init__(
        self,
        settings: Settings,
        audit: AuditLogger,
        spend_guard: SpendGuard,
        run_id: Optional[str] = None,
    ) -> None:
        self.settings = settings
        self.audit = audit
        self.spend_guard = spend_guard
        self.run_id = run_id

    def fetch_document(
        self, reference_key: str, estimated_cost: Decimal = _DEFAULT_DOC_COST
    ) -> FetchResult:
        mode = "dry_run" if (self.settings.dry_run or not self.settings.live_source_mode) else "live"

        # Dry-run / not live: no external access, no fabrication.
        if mode == "dry_run":
            self.audit.log_api_call(
                provider="okcounty",
                mode="dry_run",
                outcome="blocked",
                detail=f"dry-run: would fetch {reference_key}",
                run_id=self.run_id,
            )
            return FetchResult(
                reference_key=reference_key,
                outcome="dry_run",
                detail="dry-run mode: external retrieval not performed",
            )

        # Live mode requires configured credentials.
        if not self.settings.has_okcounty_credentials():
            missing = self.settings.missing_okcounty_credentials()
            self.audit.log_api_call(
                provider="okcounty",
                mode="live",
                outcome="auth_failure",
                detail=f"missing credentials: {missing}",
                run_id=self.run_id,
            )
            return FetchResult(
                reference_key=reference_key,
                outcome="not_configured",
                detail=f"missing credentials: {missing}",
            )

        # Spend gate.
        decision = self.spend_guard.check(estimated_cost, f"okcounty:{reference_key}")
        if decision.blocked:
            self.audit.log_api_call(
                provider="okcounty",
                mode="live",
                outcome="blocked",
                detail=f"spend blocked: {decision.reason}",
                run_id=self.run_id,
            )
            return FetchResult(
                reference_key=reference_key,
                outcome="blocked",
                detail=f"spend guard blocked: {decision.reason}",
            )

        # A real HTTP integration would go here, using an argument-validated,
        # authenticated request against settings.okcounty_api_base_url. We do
        # NOT fabricate a document. Until a live endpoint is wired and proven,
        # surface an explicit auth/integration-incomplete failure rather than a
        # fake success.
        self.audit.log_api_call(
            provider="okcounty",
            mode="live",
            outcome="auth_failure",
            detail="live integration not provisioned in this environment",
            run_id=self.run_id,
        )
        return FetchResult(
            reference_key=reference_key,
            outcome="auth_failure",
            detail="live OKCounty integration not provisioned; no document fabricated",
        )
