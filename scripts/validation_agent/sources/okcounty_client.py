"""
OKCountyRecords client.

Rules enforced here:
  * Dry-run is the default. Live calls require settings.live_enabled().
  * No silent paid calls: every paid retrieval is estimated, checked against the
    SpendGuard ($100 cap), and (unless auto-approve within the per-doc limit is
    configured) requires explicit approval.
  * Missing credentials → authentication failure result (never a fake success).
  * Never invents document contents; a failed retrieval is reported as such.
  * Uses only official/authenticated access; does not bypass access controls.

Network I/O is intentionally isolated in _http_get so it is trivial to stub in
tests and so nothing is fetched unless we are truly in live mode.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from config.settings import Settings
from sources.spend_guard import SpendGuard, SpendCapExceeded, money
from db.db_client import DatabaseManager, utcnow


@dataclass
class RetrievalResult:
    ok: bool
    reason: str
    reference: str
    status: str            # dry-run / blocked / auth_failure / needs_approval / retrieved / error
    cost: str = "0.00"
    content_path: Optional[str] = None


class OKCountyClient:
    def __init__(self, db: DatabaseManager, settings: Settings, guard: SpendGuard,
                 run_id: Optional[str] = None):
        self.db = db
        self.settings = settings
        self.guard = guard
        self.run_id = run_id

    def is_configured(self) -> bool:
        return bool(self.settings.okcounty_username and self.settings.okcounty_password
                    and self.settings.okcounty_base_url)

    def _log_call(self, endpoint: str, summary: str, outcome: str, cost: str = "0.00") -> None:
        self.db.insert("api_calls", {
            "run_id": self.run_id, "provider": "okcounty", "endpoint": endpoint,
            "request_summary": summary, "outcome": outcome, "cost_usd": cost,
            "created_at": utcnow(),
        })

    def search(self, reference: str) -> RetrievalResult:
        """A metadata search. Free of charge but still gated by live mode + auth."""
        if not self.settings.live_enabled():
            self._log_call("documents/search", reference, "dry-run")
            return RetrievalResult(False, "Dry-run mode — no live call made", reference, "dry-run")
        if not self.is_configured():
            self._log_call("documents/search", reference, "auth_failure")
            return RetrievalResult(False, "Missing OKCounty credentials", reference, "auth_failure")
        # Live metadata search would go here via _http_get; kept side-effect free
        # unless credentials + live mode are truly present.
        try:
            meta = self._http_get(f"{self.settings.okcounty_base_url}/documents/search",
                                  {"reference": reference})
            self._log_call("documents/search", reference, "ok")
            return RetrievalResult(True, "search ok", reference, "retrieved",
                                   content_path=None)
        except Exception as e:  # pragma: no cover - network path
            self._log_call("documents/search", reference, "error")
            return RetrievalResult(False, f"search error: {e}", reference, "error")

    def retrieve_document(self, reference: str, approved: bool = False) -> RetrievalResult:
        """Paid document retrieval. Spend-guarded; never silent."""
        if not self.settings.live_enabled():
            self._log_call("documents/retrieve", reference, "dry-run")
            return RetrievalResult(False, "Dry-run mode — paid retrieval not attempted",
                                   reference, "dry-run")
        if not self.is_configured():
            self._log_call("documents/retrieve", reference, "auth_failure")
            return RetrievalResult(False, "Missing OKCounty credentials", reference, "auth_failure")

        cost = money(self.settings.okcounty_cost_per_image)
        decision = self.guard.evaluate(cost, f"retrieve {reference}")
        if not decision.allowed:
            self.guard._log_block(decision, f"retrieve {reference}", "okcounty", "documents/retrieve")
            return RetrievalResult(False, decision.reason, reference, "blocked", str(cost))
        if decision.requires_approval and not approved:
            self._log_call("documents/retrieve", reference, "needs_approval", str(cost))
            return RetrievalResult(False,
                f"Paid retrieval (${cost}) requires approval — not auto-approved",
                reference, "needs_approval", str(cost))

        # Approved & within cap: perform retrieval, then record the charge.
        try:
            content_path = self._http_download(
                f"{self.settings.okcounty_base_url}/documents/{reference}", reference)
            self.guard.record_charge(cost, f"retrieve {reference}", "okcounty", "documents/retrieve")
            return RetrievalResult(True, "retrieved", reference, "retrieved", str(cost), content_path)
        except SpendCapExceeded as e:
            return RetrievalResult(False, str(e), reference, "blocked", str(cost))
        except Exception as e:  # pragma: no cover - network path
            self._log_call("documents/retrieve", reference, "error", "0.00")
            return RetrievalResult(False, f"retrieval error: {e}", reference, "error")

    # ---- network isolation points (stubbed in tests; only run in live mode) ----
    def _http_get(self, url: str, params: dict):  # pragma: no cover - network
        raise RuntimeError("Live HTTP disabled in this environment")

    def _http_download(self, url: str, reference: str) -> str:  # pragma: no cover - network
        raise RuntimeError("Live HTTP disabled in this environment")
