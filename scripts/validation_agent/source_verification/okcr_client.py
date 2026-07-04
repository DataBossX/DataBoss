"""OKCountyRecords source verification via curl subprocess (Component 5).

Basic Auth with the API key as the username, executed through ``curl`` (not
``requests``) to clear Cloudflare. Every fetch checks the ``free_to_view`` flag
and the spend ledger before spending a cent; if the host is unreachable (locked-
down/cloud egress returns 403 at the proxy) the client returns SourceUnavailable
so the loop degrades to escalation and never fabricates.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

from .. import config
from ..memory.spend_ledger import SpendCapExceeded, SpendLedger


@dataclass
class InstrumentMeta:
    county: str
    number: str
    free_to_view: bool
    cost_usd: Decimal
    doc_type: Optional[str] = None
    raw: Optional[dict] = None


@dataclass
class SourceUnavailable:
    reason: str


class OKCRClient:
    def __init__(
        self,
        api_key: str,
        ledger: SpendLedger,
        base_url: str = config.OKCR_BASE_URL,
        curl: str = config.CURL_BINARY,
        timeout: int = 40,
    ) -> None:
        self._key = api_key
        self._ledger = ledger
        self._base = base_url.rstrip("/")
        self._curl = curl
        self._timeout = timeout

    # -- low-level curl --------------------------------------------------- #
    def _curl_json(self, url: str) -> Optional[dict]:
        try:
            proc = subprocess.run(
                [self._curl, "-sS", "-u", f"{self._key}:", "-H", "Accept: application/json", url],
                capture_output=True, text=True, timeout=self._timeout,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return None

    # -- API surface ------------------------------------------------------ #
    def counties(self) -> list[str] | SourceUnavailable:
        data = self._curl_json(f"{self._base}/counties")
        if data is None:
            return SourceUnavailable("counties endpoint unreachable (proxy/cloudflare)")
        if isinstance(data, list):
            return [str(c) for c in data]
        return [str(c) for c in data.get("counties", [])]

    def lookup(self, number: str, county: str = config.COUNTY) -> InstrumentMeta | SourceUnavailable:
        data = self._curl_json(
            f"{self._base}/images?county={county}&number={number}&action=meta"
        )
        if data is None:
            return SourceUnavailable(f"lookup unreachable for {number}")
        free = bool(data.get("free_to_view", data.get("free", False)))
        cost = Decimal(str(data.get("cost", data.get("price", "0")))).quantize(Decimal("0.01"))
        return InstrumentMeta(
            county=county, number=number, free_to_view=free, cost_usd=cost,
            doc_type=data.get("doc_type"), raw=data,
        )

    def fetch_image(
        self, number: str, out_path: Path, county: str = config.COUNTY
    ) -> Path | SourceUnavailable:
        meta = self.lookup(number, county)
        if isinstance(meta, SourceUnavailable):
            return meta
        # Golden rule: never spend without free flag or affordable, ledger-checked cost.
        if not meta.free_to_view:
            if not self._ledger.can_afford(meta.cost_usd):
                return SourceUnavailable(
                    f"{number}: cost ${meta.cost_usd} exceeds remaining "
                    f"${self._ledger.remaining()}"
                )
        url = f"{self._base}/images?county={county}&number={number}&action=view"
        try:
            proc = subprocess.run(
                [self._curl, "-sS", "-u", f"{self._key}:", "-o", str(out_path), url],
                capture_output=True, text=True, timeout=self._timeout,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return SourceUnavailable(f"image fetch unreachable for {number}")
        if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            return SourceUnavailable(f"empty/failed image for {number}")
        if not meta.free_to_view:
            try:
                self._ledger.charge(meta.cost_usd, note=f"okcr:{number}")
            except SpendCapExceeded as exc:
                return SourceUnavailable(str(exc))
        return out_path
