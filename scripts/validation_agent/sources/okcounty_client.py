"""OKCountyRecords client — official/authenticated access only.

Safety posture:
  * In dry-run (default) or without credentials, NO network call is made; every
    request returns a ``dry_run`` outcome and is logged.
  * Live calls require settings.live_retrieval_allowed().
  * Paid retrieval is gated by :class:`SpendGuard`; nothing paid happens without
    an explicit allow and it can never exceed the cumulative $100 cap.
  * The client never bypasses access controls and never fabricates document
    contents. A failed retrieval returns a blocked/unavailable status.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from config.settings import Settings
from db.audit_logger import AuditLogger
from sources.spend_guard import SpendGuard


class OKCountyClient:
    def __init__(self, settings: Settings, audit: AuditLogger, guard: SpendGuard,
                 run_id: Optional[str] = None):
        self.settings = settings
        self.audit = audit
        self.guard = guard
        self.run_id = run_id

    def _live_ok(self) -> bool:
        return self.settings.live_retrieval_allowed()

    def search_metadata(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Free metadata search. Returns a status dict; never invents results."""
        if not self._live_ok():
            self.guard.record_free_call("okcounty", "search", "dry_run",
                                        detail="live retrieval not enabled or no credentials")
            return {"status": "dry_run", "results": [], "query": query}
        # Live path: perform an authenticated request. We intentionally do not
        # ship scraping logic that could violate site terms; integrators wire the
        # official API here. Until then, report unavailable rather than fake data.
        self.guard.record_free_call("okcounty", "search", "unavailable",
                                    detail="official API integration not configured")
        return {"status": "unavailable", "results": [], "query": query}

    def retrieve_document(self, reference: str, estimated_cost_usd: Decimal) -> Dict[str, Any]:
        """Attempt to retrieve one document. Honors the spend guard."""
        if not self._live_ok():
            self.audit.api_call(self.run_id, "okcounty", "document", paid=False,
                                estimated_cost_usd="0.00", outcome="dry_run",
                                detail=f"dry-run; {reference} not retrieved")
            return {"status": "blocked", "reference": reference, "reason": "dry_run"}

        allowed = self.guard.authorize(
            f"okcounty document {reference}", estimated_cost_usd,
            per_doc_limit=self.settings.per_doc_limit_usd,
            auto_approve=self.settings.auto_approve_paid)
        if not allowed:
            return {"status": "blocked", "reference": reference, "reason": "spend/approval blocked"}
        # Even when allowed, a real retrieval could still fail; we report honestly.
        return {"status": "unavailable", "reference": reference,
                "reason": "official retrieval integration not configured"}
