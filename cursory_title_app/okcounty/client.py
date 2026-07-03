"""OKCountyRecords API client (runs on the USER'S machine, where the host is
reachable — it is egress-blocked from the cloud prep container).

API contract (from the account API console / project notes):
  * Auth: HTTP Basic, username = API key, empty password  ->  -u "<KEY>:"
  * List counties:  GET /api/v1/counties
  * Document image: GET /api/v1/images?county=<County>&number=<instr#>&action=view
                    -> returns application/pdf (binary)

The key is read from the environment (OKCOUNTY_API_KEY) — never hardcoded, never
logged. This client may incur per-image charges, so callers must gate paid pulls
behind an explicit confirmation (see fetch.py).
"""
from __future__ import annotations

import os
from pathlib import Path

import requests

DEFAULT_BASE = os.getenv("OKCOUNTY_BASE_URL", "https://okcountyrecords.com/api/v1")
DEFAULT_COUNTY = os.getenv("TARGET_COUNTY", "Roger Mills")


class OkCountyError(RuntimeError):
    pass


class OkCountyClient:
    def __init__(self, api_key: str | None = None, base_url: str = DEFAULT_BASE,
                 timeout: int = 60):
        self.api_key = api_key or os.getenv("OKCOUNTY_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._s = requests.Session()
        # Basic auth: key as username, empty password.
        self._s.auth = (self.api_key, "")
        self._s.headers.update({"User-Agent": "CursoryTitleApp/1.0"})

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def preflight(self) -> dict:
        """Confirm the host is reachable and the key authenticates. Returns a
        dict; raises OkCountyError with a plain-English reason on failure."""
        if not self.is_configured():
            raise OkCountyError("OKCOUNTY_API_KEY not set in environment/.env.")
        try:
            r = self._s.get(f"{self.base_url}/counties", timeout=self.timeout)
        except requests.exceptions.ProxyError as e:
            raise OkCountyError(
                "Host unreachable (proxy/egress blocked). Run this on a machine "
                f"with direct internet access to okcountyrecords.com. [{e}]")
        except requests.exceptions.RequestException as e:
            raise OkCountyError(f"Network error reaching OKCountyRecords: {e}")
        if r.status_code in (401, 403):
            raise OkCountyError(f"Auth failed (HTTP {r.status_code}). Check the API key.")
        r.raise_for_status()
        return {"ok": True, "status": r.status_code,
                "counties_sample": r.text[:200]}

    def image(self, number: str, county: str = DEFAULT_COUNTY,
              action: str = "view") -> bytes:
        """Fetch one document image as PDF bytes. May incur a charge."""
        params = {"county": county, "number": number, "action": action}
        r = self._s.get(f"{self.base_url}/images", params=params, timeout=self.timeout)
        if r.status_code in (401, 403):
            raise OkCountyError(f"Auth/entitlement failed (HTTP {r.status_code}) for {number}.")
        if r.status_code == 404:
            raise OkCountyError(f"Not found: {county} {number}.")
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "")
        if "pdf" not in ct.lower() and not r.content[:4] == b"%PDF":
            raise OkCountyError(f"Unexpected content-type '{ct}' for {number} "
                                f"(len={len(r.content)}). Body head: {r.text[:120]!r}")
        return r.content

    def save_image(self, number: str, out_dir: Path,
                   county: str = DEFAULT_COUNTY, action: str = "view") -> Path:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        safe = str(number).replace("/", "_").replace(" ", "_")
        dest = out_dir / f"{safe}.pdf"
        dest.write_bytes(self.image(number, county=county, action=action))
        return dest
