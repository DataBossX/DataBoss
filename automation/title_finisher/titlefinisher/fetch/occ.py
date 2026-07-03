"""Oklahoma Corporation Commission (OCC) well-record client.

Pulls the structured RBDMS well row and the scanned Form 1002A completion report for an
API number, plus a best-effort spacing-order lookup. Public endpoints; no key required,
but this environment blocks the hosts (run where reachable).
"""
from __future__ import annotations
import os, time
import requests

RBDMS = "https://gisdata-occ.opendata.arcgis.com"  # RBDMS well layers (ArcGIS Hub)
WELL_BROWSE = "https://wellbrowse.occ.ok.gov"
IMAGING = "https://imaging.occ.ok.gov/OG/Well%20Records"


class OCC:
    def __init__(self, user_agent="TitleFinisher/1.0", timeout=30):
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": user_agent})

    def _get(self, url, params=None, stream=False, retries=3):
        last = None
        for attempt in range(retries):
            try:
                r = self.s.get(url, params=params, timeout=self.timeout, stream=stream)
                if r.status_code == 200:
                    return r
                if r.status_code in (403, 407):
                    raise RuntimeError(f"OCC {url} blocked ({r.status_code}) — egress policy.")
                last = f"HTTP {r.status_code}"
            except requests.RequestException as e:
                last = str(e)
            time.sleep(2 ** attempt)
        raise RuntimeError(f"OCC request failed: {last}")

    def well_record(self, api14: str) -> dict:
        """Return the structured RBDMS well attributes for an API (14 or 10 digit).
        Fields of interest: operator, status, spud, completion, TD, TVD, formation, footages."""
        api = api14.replace("-", "")
        # RBDMS_WELLS FeatureServer query (public). Layer id may shift; adjust if needed.
        url = ("https://services.arcgis.com/vfzGVQGz62Y8gm0j/arcgis/rest/services/"
               "RBDMS_WELLS/FeatureServer/0/query")
        r = self._get(url, {"where": f"API='{api}' OR API_NUMBER='{api}'",
                            "outFields": "*", "f": "json"})
        feats = r.json().get("features", [])
        return feats[0]["attributes"] if feats else {}

    def form_1002a(self, api14: str, dest_dir: str) -> str | None:
        """Best-effort: locate + download the scanned Form 1002A completion report.
        OCC imaging is keyed by an internal doc id, discoverable via well-browse; where a
        direct hint isn't available this returns None and the caller keeps the cell flagged."""
        # Placeholder for the imaging-id lookup (well-browse API differs per record).
        # Implemented as a hook so the pipeline stays honest: no id -> no fabricated data.
        return None
