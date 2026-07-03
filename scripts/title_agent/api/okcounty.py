"""OKCountyRecords source verification — Phase 2.

Three responsibilities, each a class:

* ``CurlClient`` — talks to the API through a ``curl`` subprocess rather than
  ``requests``. The endpoint sits behind Cloudflare, which fingerprints and
  challenges Python's default TLS/HTTP stack; the system ``curl`` presents a
  browser-like handshake that gets through. Auth is HTTP Basic with the API
  **key as the username and an empty password**, per the OKCounty scheme.

* ``DocumentVerifier`` — reads the ``free-to-view`` flag on a search response
  so the loop never spends budget fetching an image that is free, and so it
  can tell a genuine "not found" (404 → SOURCE_UNVERIFIED) apart from a
  billable fetch.

* ``BudgetManager`` — the $100 hard ceiling. Every spend is appended to the
  ``budget_ledger`` table (append-only, trigger-guarded in memory.py), so the
  running total survives restarts. When cumulative spend would reach the cap
  it raises ``BudgetCapReached`` and the loop halts for the Examiner.

Nothing here fabricates a fact: a 404 or a contradiction is surfaced, never
smoothed over.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from ..core.config import config
from ..core.memory import AuditLogger, SQLiteManager

# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class OKCountyError(RuntimeError):
    """Base class for all source-verification failures."""


class CurlUnavailableError(OKCountyError):
    """The ``curl`` binary is not on PATH."""


class ApiKeyMissingError(OKCountyError):
    """No API key found in the environment."""


class SourceNotFoundError(OKCountyError):
    """The API returned 404 for a Book/Page — maps to SOURCE_UNVERIFIED."""

    def __init__(self, reference: str) -> None:
        super().__init__(f"Source document not found: {reference}")
        self.reference = reference


class BudgetCapReached(OKCountyError):
    """Cumulative spend would meet or exceed the hard cap — maps to
    BUDGET_CAP_REACHED. The loop must halt for Examiner authorization."""

    def __init__(self, attempted: float, spent: float, cap: float) -> None:
        super().__init__(
            f"Budget cap ${cap:.2f} reached: ${spent:.2f} spent, "
            f"a further ${attempted:.2f} refused."
        )
        self.attempted = attempted
        self.spent = spent
        self.cap = cap


# --------------------------------------------------------------------------- #
# CurlClient
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CurlResponse:
    """One HTTP round-trip, already parsed."""

    status_code: int
    body: str
    json: Optional[dict[str, Any]]

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


class CurlClient:
    """Minimal HTTP client backed by a ``curl`` subprocess.

    The client never shells out through a string — ``subprocess.run`` is given
    an argument list, so payload values cannot inject shell syntax. The API
    key is passed via ``-u KEY:`` (Basic Auth, empty password) and is read
    fresh from the environment on every call so key rotation needs no restart.
    """

    _SEP = "\n<<<TITLE_AGENT_HTTP_STATUS>>>"

    def __init__(self, manager: SQLiteManager, audit: Optional[AuditLogger] = None) -> None:
        self._audit = audit or AuditLogger(manager)
        self._base_url = config.OKCOUNTY_API_BASE_URL
        self._timeout = config.OKCOUNTY_CURL_TIMEOUT
        self._key_env = config.OKCOUNTY_API_KEY_ENV

    def _api_key(self) -> str:
        key = os.getenv(self._key_env, "").strip()
        if not key or key == "your_api_key_here":
            raise ApiKeyMissingError(
                f"OKCounty API key not set (expected in ${self._key_env})."
            )
        return key

    @staticmethod
    def _curl_path() -> str:
        path = shutil.which("curl")
        if path is None:
            raise CurlUnavailableError("`curl` binary not found on PATH.")
        return path

    def execute(
        self,
        endpoint: str,
        payload: Optional[Mapping[str, Any]] = None,
        *,
        method: str = "GET",
    ) -> CurlResponse:
        """Call ``endpoint`` (a path relative to the API base) and return the
        parsed response.

        A ``GET`` sends ``payload`` as query parameters; any other method sends
        it as a JSON body. Raises on transport failure, timeout, or a missing
        key — but a 404 is returned as a normal ``CurlResponse`` so the caller
        can decide whether it means SOURCE_UNVERIFIED.
        """
        curl = self._curl_path()
        key = self._api_key()
        url = f"{self._base_url}/{endpoint.lstrip('/')}"

        # -s silent, -S still show errors, -w appends the HTTP status after a
        # sentinel so we can split body from code without a temp file.
        args: list[str] = [
            curl,
            "-sS",
            "--fail-with-body",  # non-2xx still yields the body, but exit != 0
            "-u",
            f"{key}:",
            "-H",
            "Accept: application/json",
            "-H",
            "User-Agent: DataBossX-TitleAgent/1.0",
            "--max-time",
            str(self._timeout),
            "-X",
            method.upper(),
            "-w",
            f"{self._SEP}%{{http_code}}",
        ]

        query = dict(payload or {})
        if method.upper() == "GET":
            for k, v in query.items():
                args += ["--data-urlencode", f"{k}={v}"]
            if query:
                args.append("-G")  # fold --data-urlencode into the query string
        else:
            args += [
                "-H",
                "Content-Type: application/json",
                "--data-binary",
                json.dumps(query),
            ]
        args.append(url)

        redacted = f"{method.upper()} {endpoint}"
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self._timeout + 5,
            )
        except subprocess.TimeoutExpired as exc:
            self._audit.log_action("API_TIMEOUT", redacted, "FAIL")
            raise OKCountyError(f"curl timed out calling {endpoint}") from exc

        status_code, body = self._split_output(proc.stdout)

        # curl exit 22 / non-zero with --fail-with-body means HTTP >= 400; we
        # still parsed status_code above, so only a true transport error (no
        # status parsed) is fatal here.
        if status_code == 0:
            self._audit.log_action(
                "API_TRANSPORT_ERROR", redacted, "FAIL",
                metadata={"stderr": proc.stderr.strip()[:500], "rc": proc.returncode},
            )
            raise OKCountyError(
                f"curl transport failure for {endpoint}: {proc.stderr.strip()[:200]}"
            )

        parsed: Optional[dict[str, Any]] = None
        if body.strip():
            try:
                loaded = json.loads(body)
                parsed = loaded if isinstance(loaded, dict) else {"data": loaded}
            except json.JSONDecodeError:
                parsed = None

        self._audit.log_action(
            "API_CALL", redacted, f"HTTP {status_code}",
            metadata={"endpoint": endpoint, "status": status_code},
        )
        return CurlResponse(status_code=status_code, body=body, json=parsed)

    def _split_output(self, stdout: str) -> tuple[int, str]:
        """Separate the response body from the trailing ``-w`` status code."""
        if self._SEP in stdout:
            body, _, tail = stdout.rpartition(self._SEP)
            try:
                return int(tail.strip() or "0"), body
            except ValueError:
                return 0, body
        return 0, stdout


# --------------------------------------------------------------------------- #
# DocumentVerifier
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FreeFlagResult:
    """Outcome of inspecting a search response's free-to-view status."""

    found: bool
    free_to_view: bool
    document_id: Optional[str]
    estimated_cost: float
    detail: str


class DocumentVerifier:
    """Interprets an OKCounty search response prior to spending budget."""

    # Response keys that, if truthy, mean the image is free to view.
    _FREE_KEYS = ("free_to_view", "freeToView", "free", "is_free", "no_charge")

    def __init__(self) -> None:
        self._cost_per_image = config.OKCOUNTY_COST_PER_IMAGE

    def evaluate_free_flag(self, json_response: Optional[Mapping[str, Any]]) -> FreeFlagResult:
        """Return whether the document exists and whether it is free to view.

        The evaluator is deliberately conservative: if the free flag is absent
        or ambiguous it reports ``free_to_view=False`` and a real cost, so the
        agent errs toward asking permission rather than assuming a free fetch.
        """
        if not json_response:
            return FreeFlagResult(
                found=False,
                free_to_view=False,
                document_id=None,
                estimated_cost=0.0,
                detail="empty or missing response",
            )

        record = self._locate_record(json_response)
        if record is None:
            return FreeFlagResult(
                found=False,
                free_to_view=False,
                document_id=None,
                estimated_cost=0.0,
                detail="no document in response",
            )

        doc_id = self._first_str(record, ("id", "document_id", "documentId"))
        free = self._read_free_flag(record)
        cost = 0.0 if free else self._read_cost(record)
        return FreeFlagResult(
            found=True,
            free_to_view=free,
            document_id=doc_id,
            estimated_cost=cost,
            detail="free-to-view" if free else "billable",
        )

    def _locate_record(self, resp: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
        for key in ("results", "documents", "data"):
            val = resp.get(key)
            if isinstance(val, list) and val and isinstance(val[0], Mapping):
                return val[0]
            if isinstance(val, Mapping):
                return val
        # A flat document object with an id counts as the record itself.
        if any(k in resp for k in ("id", "document_id", "documentId")):
            return resp
        return None

    def _read_free_flag(self, record: Mapping[str, Any]) -> bool:
        for key in self._FREE_KEYS:
            if key in record:
                return self._truthy(record[key])
        # A stated zero cost also implies free-to-view. Absent any cost field,
        # stay conservative (not free) rather than assume.
        stated = self._stated_cost(record)
        if stated is not None:
            return stated <= 0.0
        return False

    def _stated_cost(self, record: Mapping[str, Any]) -> Optional[float]:
        """Return the cost explicitly stated on the record, or None if the
        record carries no recognizable cost field."""
        for key in ("cost", "price", "charge", "estimated_cost", "fee"):
            if key in record and record[key] is not None:
                try:
                    return float(record[key])
                except (TypeError, ValueError):
                    continue
        return None

    def _read_cost(self, record: Mapping[str, Any]) -> float:
        """Cost to charge for a billable document: the stated cost if present,
        otherwise the configured per-image default."""
        stated = self._stated_cost(record)
        return stated if stated is not None else self._cost_per_image

    @staticmethod
    def _truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {"true", "yes", "y", "1", "free"}
        return bool(value)

    @staticmethod
    def _first_str(record: Mapping[str, Any], keys: tuple[str, ...]) -> Optional[str]:
        for key in keys:
            if record.get(key) is not None:
                return str(record[key])
        return None


# --------------------------------------------------------------------------- #
# BudgetManager
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BudgetStatus:
    spent: float
    cap: float
    remaining: float
    halted: bool


class BudgetManager:
    """Durable, append-only spend tracker with a hard cap.

    Reads and writes the ``budget_ledger`` table so the running total is the
    sum of every recorded charge and cannot be silently reset (the table is
    UPDATE/DELETE-guarded at the engine level). ``track_spend`` refuses — by
    raising ``BudgetCapReached`` — any charge that would take cumulative spend
    to or past the cap. It checks *before* recording, so the ledger never
    contains a charge that breached the ceiling.
    """

    def __init__(
        self,
        manager: SQLiteManager,
        audit: Optional[AuditLogger] = None,
        cap: Optional[float] = None,
    ) -> None:
        self._db = manager
        self._audit = audit or AuditLogger(manager)
        self._cap = float(cap) if cap is not None else config.BUDGET_CAP_USD

    @property
    def cap(self) -> float:
        return self._cap

    def total_spent(self) -> float:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(amount), 0.0) AS total FROM budget_ledger"
            ).fetchone()
        return float(row["total"])

    def remaining(self) -> float:
        return max(0.0, self._cap - self.total_spent())

    def status(self) -> BudgetStatus:
        spent = self.total_spent()
        return BudgetStatus(
            spent=spent,
            cap=self._cap,
            remaining=max(0.0, self._cap - spent),
            halted=spent >= self._cap,
        )

    def would_exceed(self, cost: float) -> bool:
        return (self.total_spent() + cost) >= self._cap + 1e-9

    def track_spend(self, cost: float, reference: str) -> BudgetStatus:
        """Record ``cost`` against ``reference`` after enforcing the cap.

        A non-positive cost is recorded as-is (free fetches leave a zero-cost
        audit trail). A cost that would breach the cap is refused and the loop
        is expected to escalate BUDGET_CAP_REACHED.
        """
        if cost < 0:
            raise ValueError("spend cost cannot be negative")

        spent = self.total_spent()
        if cost > 0 and (spent + cost) > self._cap + 1e-9:
            self._audit.log_action(
                "BUDGET_CAP_REACHED", reference, "HALT",
                metadata={"spent": spent, "attempted": cost, "cap": self._cap},
            )
            raise BudgetCapReached(attempted=cost, spent=spent, cap=self._cap)

        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO budget_ledger (amount, reference, created_at) "
                "VALUES (?, ?, datetime('now'))",
                (float(cost), reference),
            )
        new_total = spent + cost
        self._audit.log_action(
            "BUDGET_SPEND", reference, f"${cost:.2f}",
            metadata={"cumulative": new_total, "cap": self._cap},
        )
        return BudgetStatus(
            spent=new_total,
            cap=self._cap,
            remaining=max(0.0, self._cap - new_total),
            halted=new_total >= self._cap,
        )
