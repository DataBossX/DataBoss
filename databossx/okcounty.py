#!/usr/bin/env python3
"""OKCountyRecords evidence-pull client (CAP_RESEARCH / CAP_INDEX_EXTRACTION).

Reusable client + runner for pulling county record copies for any Oklahoma
project. Designed around the DataBossX evidence rules:

- **No charge without approval**: every call that can incur a per-document
  charge requires ``approve_charges=True`` AND an explicit ``max_spend_usd``
  budget; the guard raises before the request once the budget is reached.
- **Evidence integrity**: every downloaded byte stream is SHA-256 hashed and
  appended to a JSONL manifest before anything else touches it.
- **Never fabricate**: failures are recorded in the manifest as
  ``status: "failed"`` rows; nothing is retried into a partial file.

Credentials come from the environment only (never hardcode or commit them):

    OKCOUNTY_API_KEY   required for any request
    OKCOUNTY_BASE_URL  default https://okcountyrecords.com/api/v1

Run the Tier 1 queue (works on any machine whose network can reach the API;
cloud sessions may be blocked by egress policy):

    python -m databossx.okcounty --queue registry/EVIDENCE_PULL_QUEUE.json \
        --tier 1 --out evidence/32-11N-25W --max-spend-usd 10.00 --approve-charges

Endpoint paths are configurable via ``EndpointSpec`` because the vendor's API
surface may differ from the default guesses below; adjust once against the
official API docs and every project inherits the fix.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

DEFAULT_BASE_URL = "https://okcountyrecords.com/api/v1"


class ChargeNotApprovedError(RuntimeError):
    """A charging call was attempted without explicit approval."""


class SpendLimitError(RuntimeError):
    """The approved budget would be exceeded by the next charge."""


@dataclass
class SpendGuard:
    """Hard budget for per-document charges."""

    max_spend_usd: float
    est_cost_per_doc_usd: float = 0.40
    spent_usd: float = 0.0

    def authorize(self) -> None:
        if self.spent_usd + self.est_cost_per_doc_usd > self.max_spend_usd + 1e-9:
            raise SpendLimitError(
                f"budget exhausted: spent ${self.spent_usd:.2f}, next doc "
                f"~${self.est_cost_per_doc_usd:.2f} exceeds cap ${self.max_spend_usd:.2f}")

    def record(self) -> None:
        self.spent_usd += self.est_cost_per_doc_usd


@dataclass
class EndpointSpec:
    """URL templates relative to the base URL. Adjust to the vendor's docs."""

    search: str = "search/{county}"
    detail: str = "detail/{county}/{instrument}"
    document: str = "document/{county}/{instrument}"


@dataclass
class OKCountyClient:
    """Minimal REST client. ``transport`` is injectable for tests/offline use:
    a callable ``(url, headers) -> bytes``."""

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    endpoints: EndpointSpec = field(default_factory=EndpointSpec)
    transport: Optional[Callable[[str, Dict[str, str]], bytes]] = None
    timeout: float = 60.0

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.environ.get("OKCOUNTY_API_KEY")
        self.base_url = (self.base_url or os.environ.get("OKCOUNTY_BASE_URL")
                         or DEFAULT_BASE_URL).rstrip("/")
        if not self.api_key:
            raise ValueError("OKCOUNTY_API_KEY is not set (env or argument); "
                             "credentials must never be hardcoded")

    # -- plumbing ---------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"}

    def _fetch(self, url: str) -> bytes:
        if self.transport is not None:
            return self.transport(url, self._headers())
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.read()

    def _url(self, template: str, **kw: str) -> str:
        path = template.format(**{k: urllib.parse.quote(str(v)) for k, v in kw.items()})
        return f"{self.base_url}/{path}"

    # -- metadata (free) --------------------------------------------------
    def search(self, county: str, **params: str) -> Dict:
        url = self._url(self.endpoints.search, county=county)
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return json.loads(self._fetch(url).decode("utf-8"))

    def get_detail(self, county: str, instrument: str) -> Dict:
        return json.loads(
            self._fetch(self._url(self.endpoints.detail, county=county,
                                  instrument=instrument)).decode("utf-8"))

    # -- documents (may charge) -------------------------------------------
    def download_document(self, county: str, instrument: str, dest_dir: Path,
                          guard: SpendGuard, approve_charges: bool = False,
                          timestamp: Optional[str] = None) -> Dict:
        """Download one instrument copy, hash it, and return a manifest row."""
        if not approve_charges:
            raise ChargeNotApprovedError(
                "document pulls can incur charges; pass approve_charges=True "
                "with an explicit SpendGuard budget")
        guard.authorize()
        url = self._url(self.endpoints.document, county=county, instrument=instrument)
        stamp = timestamp or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        row: Dict = {"instrument": instrument, "county": county, "url": url,
                     "pulled_at": stamp}
        try:
            payload = self._fetch(url)
        except (urllib.error.URLError, OSError) as exc:
            row.update(status="failed", error=str(exc))
            return row
        guard.record()
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe = instrument.replace("/", "_")
        out = dest_dir / f"{county}_{safe}.pdf"
        out.write_bytes(payload)
        row.update(status="ok", path=str(out), size_bytes=len(payload),
                   sha256=hashlib.sha256(payload).hexdigest(),
                   est_cost_usd=guard.est_cost_per_doc_usd)
        return row


def load_queue(path: Path, tier: Optional[int] = None) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as fh:
        queue = json.load(fh)["instruments"]
    if tier is not None:
        queue = [q for q in queue if q.get("tier") == tier]
    return queue


def run_queue(client: OKCountyClient, queue: List[Dict], out_dir: Path,
              guard: SpendGuard, approve_charges: bool,
              manifest_path: Optional[Path] = None,
              timestamp: Optional[str] = None) -> List[Dict]:
    """Pull every queue entry; append manifest rows as they complete."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_path or (out_dir / "PULL_MANIFEST.jsonl")
    rows: List[Dict] = []
    for item in queue:
        try:
            row = client.download_document(
                item["county"], item["instrument_id"], out_dir, guard,
                approve_charges=approve_charges, timestamp=timestamp)
        except SpendLimitError as exc:
            row = {"instrument": item["instrument_id"], "county": item["county"],
                   "status": "skipped_budget", "error": str(exc)}
        row["book_page"] = item.get("book_page")
        rows.append(row)
        with open(manifest_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        if row["status"] == "skipped_budget":
            break  # no point attempting further charged pulls
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--queue", type=Path, required=True)
    ap.add_argument("--tier", type=int, default=1)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-spend-usd", type=float, required=True)
    ap.add_argument("--est-cost-per-doc", type=float, default=0.40)
    ap.add_argument("--approve-charges", action="store_true",
                    help="explicit acknowledgement that pulls may incur charges")
    args = ap.parse_args(argv)
    client = OKCountyClient()
    guard = SpendGuard(max_spend_usd=args.max_spend_usd,
                       est_cost_per_doc_usd=args.est_cost_per_doc)
    queue = load_queue(args.queue, tier=args.tier)
    rows = run_queue(client, queue, args.out, guard, args.approve_charges)
    ok = sum(1 for r in rows if r["status"] == "ok")
    failed = sum(1 for r in rows if r["status"] == "failed")
    print(f"pulled {ok}/{len(queue)} (failed {failed}, "
          f"spent ~${guard.spent_usd:.2f} of ${args.max_spend_usd:.2f})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
