"""Optional public-record collection.

This module is a *gated* connector. It will only attempt network calls when an
OKCountyRecords API key (or equivalent) is configured AND ``--collect-records``
is passed. It never bypasses paywalls, CAPTCHAs, logins, or access controls,
and it logs every search/download attempt. With no credentials it returns an
empty result and a clear status so the run stays honest.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

from .models import TractKey


@dataclass
class CollectionResult:
    attempted: bool = False
    available: bool = False
    status: str = "not-attempted"
    search_log: List[Dict[str, str]] = field(default_factory=list)
    downloaded: List[str] = field(default_factory=list)


def collect_records(tract: TractKey, enabled: bool = False) -> CollectionResult:
    """Collect public records if explicitly enabled and credentials exist."""
    result = CollectionResult()
    if not enabled:
        result.status = "disabled (pass --collect-records to enable)"
        return result

    api_key = os.getenv("OKCOUNTY_API_KEY", "")
    if not api_key or api_key == "your_api_key_here":
        result.attempted = True
        result.status = (
            "no credentials: OKCOUNTY_API_KEY not configured; "
            "no record source accessed (access controls respected)"
        )
        return result

    # Credentials present: log the searches we *would* run. Actual HTTP calls
    # are intentionally delegated to the existing doto_image_commander client to
    # avoid duplicating an authenticated integration here.
    result.attempted = True
    result.available = True
    result.status = (
        "credentials present; delegate to doto_image_commander OKCountyClient "
        "for authenticated search/download"
    )
    for term in tract.search_terms():
        result.search_log.append({
            "query": term,
            "source": "OKCountyRecords (api.okcountyrecords.com)",
            "result": "deferred to OKCountyClient",
        })
    return result
