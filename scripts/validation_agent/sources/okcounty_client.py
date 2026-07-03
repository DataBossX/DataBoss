"""OKCountyRecordsClient -- curl-subprocess source verification.

Requests are executed through the system ``curl`` binary via ``subprocess`` (no
shell) so the client presents a full browser-grade TLS/HTTP fingerprint and
standard headers -- the same way a human browser reaches the operator's own
authenticated OKCountyRecords subscription.  Credentials come from the
environment (never hardcoded, never logged) and are passed to curl over Basic
Auth.

Every paid fetch is gated by :class:`APISpendGuard` first, so the $100 ceiling
is enforced before a single byte is requested.  Metadata responses are cached
in-memory for the life of a run to avoid redundant calls.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

from ..config.settings import config
from ..db.audit_logger import AuditLogger
from .spend_guard import APISpendGuard


@dataclass
class SourceRecord:
    document_id: str
    county: str
    book: str
    page: str
    instrument_number: str
    instrument_type: str
    recording_date: str
    grantors: list[str]
    grantees: list[str]
    legal_description: str
    free_to_view: bool
    estimated_cost: float
    download_url: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CurlResponse:
    ok: bool
    http_status: Optional[int]
    body: bytes
    error: Optional[str]


@dataclass
class FetchResult:
    outcome: str            # "success" | "blocked" | "error" | "unconfigured"
    file_path: Optional[str]
    http_status: Optional[int]
    actual_cost: float
    message: str


class OKCountyRecordsClient:
    def __init__(self, audit: Optional[AuditLogger] = None,
                 guard: Optional[APISpendGuard] = None) -> None:
        self.audit = audit or AuditLogger()
        self.guard = guard or APISpendGuard(self.audit)
        self.base_url = config.okcounty_base_url.rstrip("/")
        self._meta_cache: dict[str, Optional[SourceRecord]] = {}

    def is_configured(self) -> bool:
        return config.okcounty_configured()

    # -- low-level curl executor -------------------------------------------
    def _curl(self, url: str, *, method: str = "GET",
              output_path: Optional[Path] = None, timeout: int = 60) -> CurlResponse:
        """Run curl safely as an argument list (never through a shell)."""
        status_marker = "\n__HTTP_STATUS__:"
        args = [
            config.curl_binary,
            "-sS",                       # silent but show errors
            "-L",                        # follow redirects
            "--compressed",
            "-A", config.curl_user_agent,
            "-H", "Accept: application/json",
            "--connect-timeout", "20",
            "--max-time", str(timeout),
            "-X", method,
        ]
        if self.is_configured():
            args += ["--user",
                     f"{config.okcounty_username()}:{config.okcounty_password()}"]
        # Capture the HTTP status regardless of where the body goes.
        args += ["-w", f"{status_marker}%{{http_code}}"]
        if output_path is not None:
            args += ["-o", str(output_path)]
        args.append(url)

        try:
            proc = subprocess.run(args, capture_output=True, timeout=timeout + 10,
                                  check=False)
        except FileNotFoundError:
            return CurlResponse(False, None, b"",
                                f"curl binary not found: {config.curl_binary}")
        except subprocess.TimeoutExpired:
            return CurlResponse(False, None, b"", f"curl timed out after {timeout}s")

        stdout = proc.stdout or b""
        status: Optional[int] = None
        body = stdout
        marker = status_marker.encode()
        if marker in stdout:
            body, _, tail = stdout.rpartition(marker)
            try:
                status = int(tail.decode().strip())
            except ValueError:
                status = None
        if proc.returncode != 0 and status is None:
            err = (proc.stderr or b"").decode(errors="replace").strip()
            return CurlResponse(False, None, body, err or "curl failed")
        ok = status is not None and 200 <= status < 300
        return CurlResponse(ok, status, body,
                            None if ok else f"HTTP {status}")

    # -- metadata search (treated as free unless configured otherwise) -----
    def search_document(self, county: str, *, book: str = "", page: str = "",
                        instrument_number: str = "",
                        run_id: Optional[str] = None) -> Optional[SourceRecord]:
        key = json.dumps([county, book, page, instrument_number], sort_keys=True)
        if key in self._meta_cache:
            return self._meta_cache[key]

        if not self.is_configured():
            self.audit.log_api_call(run_id, "okcounty/search",
                                    {"county": county, "book": book, "page": page,
                                     "instrument_number": instrument_number},
                                    outcome="unconfigured", http_status=None,
                                    estimated_cost=0.0, actual_cost=0.0)
            self._meta_cache[key] = None
            return None

        query = {k: v for k, v in (("county", county), ("book", book),
                                   ("page", page),
                                   ("instrumentNumber", instrument_number)) if v}
        # urlencode percent-escapes spaces and reserved chars (&, #, ...) so a
        # county like "Le Flore" or a value with '&' does not corrupt the query.
        url = f"{self.base_url}/documents/search?" + urlencode(query)

        # Metadata search cost is configured (default $0 -> free).
        decision = self.guard.authorize(config.okcounty_cost_per_search,
                                        run_id=run_id,
                                        description=f"search {county} {book}/{page}")
        if not decision.allowed:
            self.audit.log_api_call(run_id, "okcounty/search",
                                    {"county": county}, outcome="blocked",
                                    http_status=None,
                                    estimated_cost=decision.estimated_cost,
                                    actual_cost=0.0)
            self._meta_cache[key] = None
            return None

        resp = self._curl(url)
        outcome = "success" if resp.ok else "error"
        self.audit.log_api_call(run_id, "okcounty/search",
                                {"county": county, "book": book, "page": page,
                                 "instrument_number": instrument_number},
                                outcome=outcome, http_status=resp.http_status,
                                estimated_cost=decision.estimated_cost,
                                actual_cost=0.0)
        if decision.estimated_cost > 0 and resp.ok:
            self.guard.commit_spend(decision.estimated_cost,
                                    f"search {county} {book}/{page}", run_id)
        record = self._parse_record(resp, county, book, page, instrument_number) \
            if resp.ok else None
        self._meta_cache[key] = record
        return record

    def _parse_record(self, resp: CurlResponse, county: str, book: str,
                      page: str, instrument_number: str) -> Optional[SourceRecord]:
        try:
            data = json.loads(resp.body.decode(errors="replace") or "{}")
        except json.JSONDecodeError:
            return None
        # The endpoint may return either {"results": [...]} or a bare JSON array;
        # handle both without assuming a dict (a list has no .get()).
        if isinstance(data, list):
            results = data
        elif isinstance(data, dict):
            results = data.get("results") or ([data] if data else [])
        else:
            return None
        if not results or not isinstance(results[0], dict):
            return None
        r = results[0]
        return SourceRecord(
            document_id=str(r.get("id", r.get("documentId", ""))),
            county=r.get("county", county),
            book=str(r.get("book", book)),
            page=str(r.get("page", page)),
            instrument_number=str(r.get("instrumentNumber", instrument_number)),
            instrument_type=r.get("instrumentType", ""),
            recording_date=r.get("recordingDate", ""),
            grantors=[str(g) for g in r.get("grantors", [])],
            grantees=[str(g) for g in r.get("grantees", [])],
            legal_description=r.get("legalDescription", ""),
            free_to_view=bool(r.get("freeToView", False)),
            estimated_cost=float(r.get("price", config.okcounty_cost_per_image)),
            download_url=r.get("downloadUrl", ""),
            raw=r,
        )

    # -- paid image fetch (spend-gated) ------------------------------------
    def fetch_document(self, record: SourceRecord, dest_path: str | Path,
                       run_id: Optional[str] = None) -> FetchResult:
        if not self.is_configured():
            return FetchResult("unconfigured", None, None, 0.0,
                               "OKCountyRecords credentials not configured.")
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        decision = self.guard.authorize(
            record.estimated_cost, free_to_view=record.free_to_view,
            run_id=run_id, description=f"fetch {record.document_id}")
        if not decision.allowed:
            self.audit.log_api_call(run_id, "okcounty/download",
                                    {"document_id": record.document_id},
                                    outcome="blocked", http_status=None,
                                    estimated_cost=decision.estimated_cost,
                                    actual_cost=0.0)
            return FetchResult("blocked", None, None, 0.0, decision.reason)

        url = record.download_url or \
            f"{self.base_url}/documents/{record.document_id}/download"
        resp = self._curl(url, output_path=dest)
        if not resp.ok:
            self.audit.log_api_call(run_id, "okcounty/download",
                                    {"document_id": record.document_id},
                                    outcome="error", http_status=resp.http_status,
                                    estimated_cost=decision.estimated_cost,
                                    actual_cost=0.0)
            return FetchResult("error", None, resp.http_status, 0.0,
                               resp.error or "download failed")

        actual = 0.0 if record.free_to_view else record.estimated_cost
        if actual > 0:
            self.guard.commit_spend(actual, f"fetch {record.document_id}", run_id)
        self.audit.log_api_call(run_id, "okcounty/download",
                                {"document_id": record.document_id},
                                outcome="success", http_status=resp.http_status,
                                estimated_cost=decision.estimated_cost,
                                actual_cost=actual)
        return FetchResult("success", str(dest), resp.http_status, actual,
                           "Document retrieved.")

    # -- verification helper for Gate 11 -----------------------------------
    @staticmethod
    def verify_against(record: SourceRecord, *, expected_parties: list[str],
                       expected_legal: str) -> tuple[bool, str]:
        """Compare a retrieved record to workbook facts; report contradictions."""
        def norm(s: str) -> str:
            return "".join(ch for ch in s.upper() if ch.isalnum())

        rec_parties = {norm(p) for p in record.grantors + record.grantees}
        for party in expected_parties:
            if party and norm(party) not in rec_parties and \
                    not any(norm(party) in rp for rp in rec_parties):
                return False, (f"Party '{party}' not found on source document "
                               f"{record.document_id}.")
        if expected_legal and record.legal_description:
            if norm(expected_legal) not in norm(record.legal_description) and \
                    norm(record.legal_description) not in norm(expected_legal):
                return False, ("Legal description on source contradicts workbook: "
                               f"'{record.legal_description}' vs '{expected_legal}'.")
        return True, "Source matches workbook party and legal description."


# Module-level singleton (mirrors doto_image_commander convention).
client = OKCountyRecordsClient()
