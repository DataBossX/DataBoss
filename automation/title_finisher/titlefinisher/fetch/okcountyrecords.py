"""okcountyrecords.com API client — instrument search and image download.

Endpoints follow the documented pattern:
    https://okcountyrecords.com/api/v1/images?county=<County>&number=<doc>&action=view
plus a search endpoint for a recent-filing sweep by legal. The API key is sent both as a
bearer header and an `apikey` query param (the service has accepted either historically);
adjust in one place here if the account's scheme differs.

All network calls are isolated to this module so the rest of TitleFinisher runs offline.
"""
from __future__ import annotations
import os, time
import requests

BASE = "https://okcountyrecords.com/api/v1"


class OkCountyRecords:
    def __init__(self, api_key: str, user_agent: str = "TitleFinisher/1.0", timeout: int = 30):
        if not api_key:
            raise ValueError("okcountyrecords API key required")
        self.key = api_key
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {api_key}",
            "User-Agent": user_agent,
            "Accept": "application/json",
        })

    def _get(self, path, params=None, stream=False, retries=4):
        params = dict(params or {}); params.setdefault("apikey", self.key)
        last = None
        for attempt in range(retries):
            try:
                r = self.s.get(f"{BASE}/{path}", params=params, timeout=self.timeout, stream=stream)
                if r.status_code == 200:
                    return r
                if r.status_code in (403, 407):
                    raise RuntimeError(
                        f"okcountyrecords returned {r.status_code} — this environment's "
                        "egress policy is blocking the host, or the key lacks scope. "
                        "Run TitleFinisher where okcountyrecords.com is reachable.")
                last = f"HTTP {r.status_code}"
            except requests.RequestException as e:
                last = str(e)
            time.sleep(2 ** attempt)
        raise RuntimeError(f"okcountyrecords request failed after {retries} tries: {last}")

    def search_section(self, county: str, twprge: str, section: str,
                       filed_after: str | None = None) -> list[dict]:
        """Recent-filing sweep: instruments for a section, optionally filed after a date."""
        twp, rge = twprge.split("-")
        params = {"county": county, "township": twp, "range": rge, "section": section}
        if filed_after:
            params["filed_after"] = filed_after
        return self._get("search", params).json().get("results", [])

    def image_by_number(self, county: str, number: str, dest: str) -> str:
        """Download the instrument image for a document number to `dest`. Returns dest."""
        r = self._get("images", {"county": county, "number": number, "action": "view"}, stream=True)
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
        return dest

    def image_by_book_page(self, county: str, book: str, page: str, dest: str) -> str:
        r = self._get("images", {"county": county, "book": book, "page": page, "action": "view"}, stream=True)
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
        return dest
