"""
OKCountyRecords API v1 client.
Auth: HTTP Basic — API key as username, blank password.
"""

import os
import re
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

import requests
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

BASE_URL = "https://okcountyrecords.com/api/v1"


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class SearchHit:
    hit_id: str
    instrument_type: str
    instrument_number: str
    book: str
    page: str
    doc_date: str
    recording_date: str
    grantor: List[str]
    grantee: List[str]
    legal: str
    county: str
    image_url: str
    source_url: str
    dedup_key: str
    estimated_cost: float = 0.50
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def grantor_names(self) -> List[str]:
        return self.grantor or []

    @property
    def grantee_names(self) -> List[str]:
        return self.grantee or []

    def to_dict(self) -> Dict[str, Any]:
        import json as _j
        return {
            "dedup_key":         self.dedup_key,
            "hit_id":            self.hit_id,
            "county":            self.county,
            "book":              self.book,
            "page":              self.page,
            "instrument_number": self.instrument_number,
            "instrument_type":   self.instrument_type,
            "doc_date":          self.doc_date,
            "recording_date":    self.recording_date,
            "grantor":           _j.dumps(self.grantor),
            "grantee":           _j.dumps(self.grantee),
            "legal":             self.legal,
            "image_url":         self.image_url,
            "source_url":        self.source_url,
            "search_query":      "",
        }


@dataclass
class DownloadResult:
    success: bool
    local_path: str
    file_size: int = 0
    error: Optional[str] = None


# ── Client ────────────────────────────────────────────────────────────────────

class OKCRClient:
    """
    Wraps the OKCountyRecords /api/v1/search and image-download endpoints.

    Authentication: HTTP Basic Auth with API key as username, blank password,
    exactly as documented at https://okcountyrecords.com/api/v1/documentation
    """

    def __init__(self, api_key: str,
                 cost_per_image: float = 0.50,
                 rate_limit_rps: float = 2.0):
        self.api_key = api_key.strip()
        self.cost_per_image = cost_per_image
        self._min_gap = 1.0 / max(rate_limit_rps, 0.1)
        self._last_call = 0.0

        retry = Retry(total=4, backoff_factor=1.5,
                      status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self._session = requests.Session()
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "DataBossX-TitleEngine/1.0",
        })

    # ── Auth helper ──────────────────────────────────────────────────────────

    @property
    def _auth(self) -> HTTPBasicAuth:
        return HTTPBasicAuth(self.api_key, "")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key not in ("", "YOUR_API_KEY_HERE"))

    # ── Rate limiting ────────────────────────────────────────────────────────

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_call
        if elapsed < self._min_gap:
            time.sleep(self._min_gap - elapsed)
        self._last_call = time.time()

    # ── Search ───────────────────────────────────────────────────────────────

    def search(
        self,
        county: str,
        *,
        q: str = None,
        grantor: str = None,
        grantee: str = None,
        instrument_type: str = None,
        section: str = None,
        township: str = None,
        range_: str = None,
        legal: str = None,
        date_from: str = None,
        date_to: str = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Tuple[List[SearchHit], int]:
        """
        Single-page search. Returns (hits, total_count).
        Uses every documented parameter so callers can mix/match.
        """
        if not self.is_configured():
            raise RuntimeError("API key not configured.")

        params: Dict[str, Any] = {"county": county, "page": page, "per_page": per_page}
        if q:              params["q"]              = q
        if grantor:        params["grantor"]        = grantor
        if grantee:        params["grantee"]        = grantee
        if instrument_type: params["instrument_type"] = instrument_type
        if section:        params["section"]        = section
        if township:       params["township"]       = township
        if range_:         params["range"]          = range_
        if legal:          params["legal"]          = legal
        if date_from:      params["date_from"]      = date_from
        if date_to:        params["date_to"]        = date_to

        self._throttle()
        log.debug("OKCR search: %s", params)
        resp = self._session.get(f"{BASE_URL}/search", params=params,
                                  auth=self._auth, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        hits = [self._parse_hit(r) for r in self._extract_results(data)]
        total = self._extract_total(data)
        return hits, total

    def search_all(self, *, county: str, **kwargs) -> List[SearchHit]:
        """Paginate through all results for a search."""
        all_hits: List[SearchHit] = []
        page = 1
        while True:
            hits, total = self.search(county, page=page, per_page=50, **kwargs)
            all_hits.extend(hits)
            if not hits or len(all_hits) >= total:
                break
            page += 1
            time.sleep(0.4)
        return all_hits

    # ── Image download ───────────────────────────────────────────────────────

    def download_image(self, url_or_hit, dest: Path) -> DownloadResult:
        """
        Download the watermarked PDF for a search hit or a direct URL.
        Accepts either a SearchHit object or a plain URL string.
        """
        if not self.is_configured():
            raise RuntimeError("API key not configured.")

        if isinstance(url_or_hit, SearchHit):
            url = url_or_hit.image_url
            if not url and url_or_hit.hit_id:
                url = f"{BASE_URL}/instruments/{url_or_hit.hit_id}/images"
        else:
            url = str(url_or_hit)

        if not url:
            return DownloadResult(success=False, local_path=str(dest),
                                  error="No image URL available")

        self._throttle()
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            resp = self._session.get(url, auth=self._auth, timeout=90, stream=True)
            resp.raise_for_status()
            written = 0
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(65536):
                    f.write(chunk)
                    written += len(chunk)
            return DownloadResult(success=True, local_path=str(dest), file_size=written)
        except requests.HTTPError as e:
            return DownloadResult(success=False, local_path=str(dest), error=str(e))
        except OSError as e:
            return DownloadResult(success=False, local_path=str(dest), error=str(e))

    # ── Cost estimation ──────────────────────────────────────────────────────

    def estimate_cost(self, n_images: int) -> Dict[str, Any]:
        total = round(n_images * self.cost_per_image, 2)
        return {
            "count": n_images,
            "unit_cost": self.cost_per_image,
            "estimated_usd": total,
            "total": total,
        }

    # ── Response parsing ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_results(data: dict) -> list:
        # OKCountyRecords may nest results under 'data', 'results', or root list
        if isinstance(data, list):
            return data
        for key in ("data", "results", "instruments", "records"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return []

    @staticmethod
    def _extract_total(data: dict) -> int:
        if isinstance(data, list):
            return len(data)
        for key in ("total", "total_count", "count"):
            if key in data:
                try:
                    return int(data[key])
                except (TypeError, ValueError):
                    pass
        meta = data.get("meta", data.get("pagination", {}))
        for key in ("total", "total_count"):
            if key in meta:
                try:
                    return int(meta[key])
                except (TypeError, ValueError):
                    pass
        return 0

    def _parse_hit(self, r: dict) -> SearchHit:
        def _list(v):
            if v is None:
                return []
            if isinstance(v, list):
                return [str(x) for x in v]
            return [str(v)]

        def _str(v):
            return str(v).strip() if v is not None else ""

        grantor = _list(r.get("grantor") or r.get("grantors") or r.get("grantor_name"))
        grantee = _list(r.get("grantee") or r.get("grantees") or r.get("grantee_name"))
        inst_num = _str(r.get("instrument_number") or r.get("doc_number") or r.get("document_number") or "")
        book     = _str(r.get("book") or r.get("deed_book") or "")
        page     = _str(r.get("page") or r.get("deed_page") or "")
        hit_id   = _str(r.get("id") or r.get("document_id") or r.get("instrument_id") or "")

        # Build a stable dedup key
        if inst_num:
            dedup = inst_num
        elif book and page:
            dedup = f"B{book}P{page}"
        elif hit_id:
            dedup = f"ID{hit_id}"
        else:
            import hashlib, json as _j
            dedup = hashlib.md5(_j.dumps(r, sort_keys=True).encode()).hexdigest()[:16]

        image_url  = _str(r.get("image_url") or r.get("download_url") or r.get("file_url") or "")
        source_url = _str(r.get("url") or r.get("source_url") or r.get("permalink") or "")

        return SearchHit(
            hit_id=hit_id,
            instrument_type=_str(r.get("instrument_type") or r.get("doc_type") or r.get("type") or ""),
            instrument_number=inst_num,
            book=book,
            page=page,
            doc_date=_str(r.get("document_date") or r.get("doc_date") or r.get("instrument_date") or ""),
            recording_date=_str(r.get("recording_date") or r.get("filed_date") or ""),
            grantor=grantor,
            grantee=grantee,
            legal=_str(r.get("legal_description") or r.get("legal") or r.get("property_description") or ""),
            county=_str(r.get("county") or ""),
            image_url=image_url,
            source_url=source_url,
            dedup_key=dedup,
            estimated_cost=self.cost_per_image,
            raw=r,
        )
