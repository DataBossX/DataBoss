"""OKCountyRecords / Oklahoma records access -- API first, browser fallback.

This is a thin, defensive client. It NEVER hard-fails the pipeline: if no
credentials, no network, or no browser are available it simply returns empty
results and records why. Every image purchase is routed through the spend
tracker so the $100 cap is enforced before any paid fetch happens.

Secrets: credentials come only from the environment (loaded via env_utils) and
are never logged. The base URL and any tokens are read at call time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from .logbook import LogBook
from .spend import SpendTracker


@dataclass
class RecordsResult:
    available: bool
    wells: List[Dict]
    documents: List[Dict]
    reason: str = ""


class OKCountyRecordsClient:
    """Best-effort client for Oklahoma county records and OCC well data."""

    def __init__(self, log: Optional[LogBook] = None,
                 spend: Optional[SpendTracker] = None) -> None:
        self.log = log or LogBook()
        self.spend = spend
        self.base_url = os.environ.get("OKCOUNTYRECORDS_BASE_URL", "").rstrip("/")
        # Presence-only check; value is never read into logs.
        self._has_key = bool(os.environ.get("OKCOUNTYRECORDS_API_KEY"))
        self.county = "Roger Mills"

    # -- capability probe ---------------------------------------------------
    def is_configured(self) -> bool:
        return bool(self.base_url)

    # -- API path -----------------------------------------------------------
    def _api_get(self, path: str, params: Dict) -> Optional[Dict]:
        if not self.is_configured():
            return None
        try:
            import requests
        except Exception:
            self.log.warn("requests not installed; skipping OKCountyRecords API")
            return None
        headers = {}
        api_key = os.environ.get("OKCOUNTYRECORDS_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            resp = requests.get(f"{self.base_url}/{path.lstrip('/')}",
                                params=params, headers=headers, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            self.log.warn(f"OKCountyRecords API returned HTTP {resp.status_code}")
        except Exception as exc:  # network, JSON, TLS, etc.
            self.log.warn(f"OKCountyRecords API error: {type(exc).__name__}")
        return None

    # -- public: wells ------------------------------------------------------
    def fetch_wells(self, section: str = "31", township: str = "12N",
                    range_: str = "24W") -> RecordsResult:
        """Return wells for the section. Empty (with reason) if unavailable."""
        if not self.is_configured():
            return RecordsResult(False, [], [],
                                 "OKCountyRecords not configured (set "
                                 "OKCOUNTYRECORDS_BASE_URL). Local data only.")
        data = self._api_get("wells", {
            "county": self.county, "section": section,
            "township": township, "range": range_,
        })
        if data is None:
            data = self._browser_fetch_wells(section, township, range_)
        if not data:
            return RecordsResult(False, [], [], "no response from records source")
        wells = data.get("wells", data if isinstance(data, list) else [])
        norm = [self._norm_well(w) for w in wells]
        self.log.info(f"OKCountyRecords returned {len(norm)} wells")
        return RecordsResult(True, norm, [], "")

    def _norm_well(self, w: Dict) -> Dict:
        return {
            "api_number": w.get("api") or w.get("api_number", ""),
            "well_name": w.get("well_name") or w.get("name", ""),
            "operator": w.get("operator", ""),
            "well_status": w.get("status") or w.get("well_status", ""),
            "spud_date": w.get("spud_date", ""),
            "completion_date": w.get("completion_date", ""),
            "formation": w.get("formation", ""),
            "section": str(w.get("section", "31")),
            "township": str(w.get("township", "12N")),
            "range": str(w.get("range", "24W")),
            "county": w.get("county", "Roger Mills"),
            "source": "OKCountyRecords",
        }

    # -- browser fallback ---------------------------------------------------
    def _browser_fetch_wells(self, section, township, range_) -> Optional[List[Dict]]:
        """Playwright fallback -- only if configured and playwright present."""
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except Exception:
            self.log.warn("playwright unavailable; skipping browser fallback")
            return None
        self.log.info("browser fallback available but no scrape template "
                      "configured for this deployment; returning none")
        return None

    # -- document image purchase (spend-gated) ------------------------------
    def purchase_image(self, doc_id: str, unit_cost: float = 1.0) -> Optional[str]:
        """Buy one document image, respecting the $100 spend cap.

        Returns a local path/id on success, None if blocked by the cap or if no
        source is configured.
        """
        if self.spend is not None and not self.spend.can_spend(unit_cost):
            self.log.warn(f"image {doc_id} skipped: ${unit_cost:.2f} would "
                          f"exceed spend cap")
            return None
        if not self.is_configured():
            return None
        # Actual download would happen here; record the spend on success.
        if self.spend is not None:
            self.spend.record(f"document image {doc_id}", unit_cost,
                              image_id=doc_id, source="OKCountyRecords")
        return f"image::{doc_id}"
