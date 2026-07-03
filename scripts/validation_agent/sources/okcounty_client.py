"""OKCountyRecords client (official, authenticated access only).

This client performs NO paid action unless the :class:`SpendGuard` has approved
it and live-source mode is enabled. It never bypasses access controls, never
fabricates document contents, and logs every request and every blocked request.
In dry-run mode it is inert.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

try:
    import requests
except Exception:  # pragma: no cover - requests always in requirements
    requests = None


@dataclass
class SourceSearchResult:
    reference_key: str
    doc_type: str
    county: str
    download_url: str
    estimated_cost: Decimal
    metadata: dict


class OKCountyClient:
    def __init__(self, settings, db=None, run_id: str | None = None,
                 spend_guard=None):
        self.settings = settings
        self.db = db
        self.run_id = run_id
        self.spend_guard = spend_guard
        self.base_url = (settings.okcounty_api_base_url or "").rstrip("/")
        self._session = requests.Session() if requests else None
        if self._session and settings.okcounty_username:
            self._session.auth = (
                settings.okcounty_username, settings.okcounty_password
            )
            self._session.headers.update(
                {"User-Agent": "DataBossX-ValidationAgent/1.0"}
            )

    def is_available(self) -> bool:
        return bool(
            self.settings.live_source
            and self.settings.okcounty_configured()
            and self._session is not None
        )

    def _log_call(self, endpoint: str, meta: dict, outcome: str, cost: float) -> None:
        if self.db:
            self.db.record_api_call(
                self.run_id, "okcounty", endpoint, meta, outcome, cost
            )

    def search(self, reference_key: str, county: str = "",
               doc_type: str = "") -> Optional[SourceSearchResult]:
        """Search for a document. Returns None if unavailable/not found.

        A search itself may carry a small cost; it is gated through the spend
        guard exactly like a document retrieval.
        """
        if not self.is_available():
            self._log_call("search", {"reference_key": reference_key},
                           "blocked", 0.0)
            return None
        cost = self.settings.okcounty_cost_per_search
        if self.spend_guard:
            decision = self.spend_guard.authorize(
                cost, f"OKCounty search {reference_key}", kind="search"
            )
            if not decision.approved:
                self._log_call("search", {"reference_key": reference_key,
                                          "reason": decision.reason},
                               "blocked", 0.0)
                return None
        try:
            resp = self._session.get(
                f"{self.base_url}/documents/search",
                params={"reference": reference_key, "county": county,
                        "type": doc_type},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:  # network / auth failure — never fabricate
            self._log_call("search", {"reference_key": reference_key,
                                      "error": str(e)}, "error", float(cost))
            return None
        results = data.get("results") or []
        if not results:
            self._log_call("search", {"reference_key": reference_key},
                           "ok", float(cost))
            return None
        r = results[0]
        self._log_call("search", {"reference_key": reference_key}, "ok",
                       float(cost))
        return SourceSearchResult(
            reference_key=reference_key,
            doc_type=r.get("type", doc_type),
            county=r.get("county", county),
            download_url=r.get("download_url", ""),
            estimated_cost=Decimal(str(r.get("cost",
                                   self.settings.okcounty_cost_per_document))),
            metadata=r,
        )

    def retrieve(self, result: SourceSearchResult, cache,
                 examiner_approved: bool = False) -> Optional[tuple]:
        """Retrieve a document. Returns (path, sha256, cost) or None if blocked.

        The paid retrieval is authorized through the spend guard; a blocked
        retrieval returns None and is logged (never hidden, never invented).
        """
        if not self.is_available():
            self._log_call("retrieve", {"reference_key": result.reference_key},
                           "blocked", 0.0)
            return None
        if self.spend_guard:
            decision = self.spend_guard.authorize(
                result.estimated_cost,
                f"OKCounty document {result.reference_key}",
                kind="document", examiner_approved=examiner_approved,
            )
            if not decision.approved:
                self._log_call(
                    "retrieve",
                    {"reference_key": result.reference_key,
                     "reason": decision.reason}, "blocked", 0.0,
                )
                return None
        try:
            resp = self._session.get(result.download_url, timeout=60)
            resp.raise_for_status()
            content = resp.content
        except Exception as e:
            self._log_call("retrieve", {"reference_key": result.reference_key,
                                        "error": str(e)}, "error",
                           float(result.estimated_cost))
            return None
        safe = result.reference_key.replace("/", "_").replace(" ", "_")
        path, digest = cache.store_bytes(f"doc_{safe}.bin", content)
        self._log_call("retrieve", {"reference_key": result.reference_key},
                       "ok", float(result.estimated_cost))
        return path, digest, result.estimated_cost
