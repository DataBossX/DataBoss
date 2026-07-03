"""Title examination business logic — Phase 5, the six quality gates.

Each validator returns a ``GateResult`` carrying zero or more ``Failure``s, and
each ``Failure`` is tagged with a ``FailureCategory`` so the loop can route it.
The categorization is where the Golden Law is enforced in code:

* A missing or wrong **pro-rata / footing formula** is a MATH_FOOTING_ERROR
  (Category A) — the agent may inject the standard formula, because doing so
  asserts no new fact, only the arithmetic already implied by the data.

* A genuine **non-conservation of interest**, a **broken chain**, an
  **unverifiable source**, or an **OGL/WI contradiction** is Category B. The
  agent cannot clear these without inventing an heir, a deed, a Book/Page, or a
  royalty — so it escalates. Over-escalation is the intended bias: when a
  failure is ambiguous, it goes to the Examiner, never to auto-repair.

These validators are pure functions over typed inputs; the loop supplies the
data (from ingestion) and, for Gate 4, a source probe backed by the OKCounty
client and budget manager.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, Sequence

from ..core.config import DECIMAL_TOLERANCE, GROSS_ACRE_TARGET
from ..core.taxonomy import FailureCategory, Gate

# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Failure:
    """One gate failure, categorized for routing."""

    gate: Gate
    category: FailureCategory
    reference: str
    detail: str
    proof: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GateResult:
    """The outcome of evaluating one gate."""

    gate: Gate
    failures: tuple[Failure, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.failures


def _norm_name(name: Optional[str]) -> str:
    """Normalize a party name for comparison: uppercase, strip legal noise and
    punctuation, collapse whitespace. Conservative — it only removes obvious
    formatting so that 'John Q. Doe' and 'JOHN Q DOE' match, not so that two
    genuinely different names collapse together."""
    if not name:
        return ""
    text = name.upper()
    text = re.sub(r"[.,;:'\"()]", " ", text)
    text = re.sub(r"\b(AN UNMARRIED|A SINGLE|HUSBAND AND WIFE|ET UX|ET AL)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# --------------------------------------------------------------------------- #
# Gate 1 — Interest Conservation
# --------------------------------------------------------------------------- #


class InterestConservation:
    """Gate 1: every instrument column must net to exactly zero."""

    def __init__(self, tolerance: float = DECIMAL_TOLERANCE) -> None:
        self._tol = tolerance

    def check_zero_sum(self, column: Sequence[float], reference: str) -> GateResult:
        """The net of all granted (+) and reserved (-) interest in a column
        must be 0. A non-zero net is a substantive ownership problem — a party
        conveying more or less than they hold — so it escalates as TITLE_GAP.
        The agent must never zero it out by editing numbers.
        """
        values = [float(v) for v in column if v is not None]
        net = sum(values)
        if abs(net) <= self._tol:
            return GateResult(Gate.INTEREST_CONSERVATION)
        failure = Failure(
            gate=Gate.INTEREST_CONSERVATION,
            category=FailureCategory.TITLE_GAP,
            reference=reference,
            detail=(
                f"Interest does not conserve: net {net:.8f} over "
                f"{len(values)} entries (must be 0)."
            ),
            proof={"net": net, "count": len(values), "values": values},
        )
        return GateResult(Gate.INTEREST_CONSERVATION, (failure,))


# --------------------------------------------------------------------------- #
# Gate 2 — Acreage Footing
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TractAcreage:
    """A tract's acreage inputs for pro-rata verification."""

    tract_number: int
    gross_acres: float
    interest_fraction: float
    net_acres: Optional[float]  # None == formula missing


class AcreageFooting:
    """Gate 2: pro-rata net acres per tract and the 637.42 gross total."""

    def __init__(self, tolerance: float = DECIMAL_TOLERANCE) -> None:
        self._tol = tolerance

    def verify_pro_rata(self, tract: TractAcreage) -> GateResult:
        """Net acres must equal gross * interest_fraction. A missing or wrong
        value is a footing-formula defect (Category A) — the standard formula
        can be injected without asserting a new fact."""
        expected = tract.gross_acres * tract.interest_fraction
        ref = f"Tract {tract.tract_number}"
        if tract.net_acres is None:
            return self._footing_fail(
                ref, f"Pro-rata NET ACRES formula missing (expected {expected:.8f}).",
                {"expected": expected, "gross": tract.gross_acres,
                 "fraction": tract.interest_fraction},
            )
        if abs(tract.net_acres - expected) > self._tol:
            return self._footing_fail(
                ref,
                f"NET ACRES {tract.net_acres:.8f} != gross*fraction {expected:.8f}.",
                {"actual": tract.net_acres, "expected": expected,
                 "gross": tract.gross_acres, "fraction": tract.interest_fraction},
            )
        return GateResult(Gate.ACREAGE_FOOTING)

    def verify_gross_total(
        self, tracts: Sequence[TractAcreage], target: float = GROSS_ACRE_TARGET
    ) -> GateResult:
        """The sum of tract gross acres must equal the target (637.42). A
        mismatch is a footing error on the aggregate sum (Category A)."""
        total = sum(t.gross_acres for t in tracts)
        if abs(total - target) <= self._tol:
            return GateResult(Gate.ACREAGE_FOOTING)
        return self._footing_fail(
            f"Gross total ({len(tracts)} tracts)",
            f"Gross acreage {total:.8f} != target {target:.2f} (delta {total - target:.8f}).",
            {"total": total, "target": target, "delta": total - target},
        )

    def _footing_fail(self, ref: str, detail: str, proof: dict[str, Any]) -> GateResult:
        return GateResult(
            Gate.ACREAGE_FOOTING,
            (Failure(Gate.ACREAGE_FOOTING, FailureCategory.MATH_FOOTING_ERROR, ref, detail, proof),),
        )


# --------------------------------------------------------------------------- #
# Gate 3 — Chain Continuity
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ChainInstrument:
    """One row of a tract's runsheet, in chain order."""

    seq: int
    grantor: str
    grantee: str
    instrument_date: Optional[str] = None  # ISO 'YYYY-MM-DD' if known


class ChainContinuity:
    """Gate 3: grantor of instrument N == grantee of N-1, no chronological gap."""

    def check_gapless_chain(
        self, runsheet: Sequence[ChainInstrument], reference: str
    ) -> GateResult:
        """A grantor/grantee break or a date reversal is a TITLE_GAP — a
        missing deed or unprobated estate the agent must not invent around."""
        failures: list[Failure] = []
        ordered = sorted(runsheet, key=lambda i: i.seq)
        for prev, cur in zip(ordered, ordered[1:]):
            if _norm_name(cur.grantor) != _norm_name(prev.grantee):
                failures.append(
                    Failure(
                        gate=Gate.CHAIN_CONTINUITY,
                        category=FailureCategory.TITLE_GAP,
                        reference=f"{reference} seq {prev.seq}->{cur.seq}",
                        detail=(
                            f"Chain break: grantee '{prev.grantee}' does not match "
                            f"next grantor '{cur.grantor}'."
                        ),
                        proof={"prev_grantee": prev.grantee, "next_grantor": cur.grantor,
                               "prev_seq": prev.seq, "next_seq": cur.seq},
                    )
                )
            if self._date_reversed(prev.instrument_date, cur.instrument_date):
                failures.append(
                    Failure(
                        gate=Gate.CHAIN_CONTINUITY,
                        category=FailureCategory.TITLE_GAP,
                        reference=f"{reference} seq {prev.seq}->{cur.seq}",
                        detail=(
                            f"Chronological gap: {cur.instrument_date} precedes "
                            f"{prev.instrument_date}."
                        ),
                        proof={"prev_date": prev.instrument_date, "next_date": cur.instrument_date},
                    )
                )
        return GateResult(Gate.CHAIN_CONTINUITY, tuple(failures))

    @staticmethod
    def _date_reversed(prev: Optional[str], cur: Optional[str]) -> bool:
        if not prev or not cur:
            return False  # unknown dates are not a proof of reversal
        return cur < prev  # ISO dates compare lexically


# --------------------------------------------------------------------------- #
# Gate 4 — Source Verification
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class InstrumentLine:
    """A runsheet line to be traced to a source document."""

    seq: int
    book: str
    page: str
    instrument_type: Optional[str] = None
    workbook_has_metadata: bool = True


@dataclass(frozen=True)
class SourceProbeResult:
    """What a source probe reports for one Book/Page."""

    found: bool
    free_to_view: bool
    contradiction: Optional[str] = None  # non-None means API disagrees w/ workbook
    detail: str = ""


class SourceProbe(Protocol):
    """Adapter the loop provides, backed by CurlClient + DocumentVerifier +
    BudgetManager. Kept abstract here so the rules stay unit-testable."""

    def verify(self, line: "InstrumentLine") -> SourceProbeResult: ...


class SourceAudit:
    """Gate 4: every runsheet line must trace to a verified source document."""

    def verify_instrument_lines(
        self, runsheet: Sequence[InstrumentLine], api_client: SourceProbe, reference: str
    ) -> GateResult:
        """Route each line:

        * 404 / not found -> SOURCE_UNVERIFIED (escalate).
        * API contradicts the workbook -> SOURCE_UNVERIFIED (escalate).
        * found, free-to-view, but the workbook lacks the metadata ->
          METADATA_MISSING (auto-fetch and inject).
        * found and consistent -> pass.
        """
        failures: list[Failure] = []
        for line in runsheet:
            ref = f"{reference} seq {line.seq} (Book {line.book}/Page {line.page})"
            result = api_client.verify(line)
            if not result.found:
                failures.append(
                    Failure(Gate.SOURCE_VERIFICATION, FailureCategory.SOURCE_UNVERIFIED, ref,
                            f"Source document not found: {result.detail or '404'}.",
                            {"book": line.book, "page": line.page})
                )
                continue
            if result.contradiction:
                failures.append(
                    Failure(Gate.SOURCE_VERIFICATION, FailureCategory.SOURCE_UNVERIFIED, ref,
                            f"API contradicts workbook: {result.contradiction}.",
                            {"book": line.book, "page": line.page,
                             "contradiction": result.contradiction})
                )
                continue
            if not line.workbook_has_metadata and result.free_to_view:
                failures.append(
                    Failure(Gate.SOURCE_VERIFICATION, FailureCategory.METADATA_MISSING, ref,
                            "Free-to-view source found; workbook metadata missing.",
                            {"book": line.book, "page": line.page})
                )
        return GateResult(Gate.SOURCE_VERIFICATION, tuple(failures))


# --------------------------------------------------------------------------- #
# Gate 5 — OGL Parity
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class OGLEntry:
    """One lease in the OGL register."""

    tract_number: int
    lessor: str
    royalty_decimal: float  # e.g. 0.1875 for 3/16


@dataclass(frozen=True)
class WIEntry:
    """One owner's interest on a tract in the Working-Interest sheet."""

    tract_number: int
    owner: str
    wi_decimal: float
    nri_decimal: float


class OGLAudit:
    """Gate 5: OGL register must reconcile with the WI sheets, per tract."""

    def __init__(self, tolerance: float = 1e-6) -> None:
        # WI/NRI are quoted to ~6 decimals in practice; a slightly looser
        # tolerance than the raw decimal dust avoids false positives on
        # legitimately rounded book figures while still catching real gaps.
        self._tol = tolerance

    def validate_ogl_register(
        self, ogl_data: Sequence[OGLEntry], wi_data: Sequence[WIEntry]
    ) -> GateResult:
        """For each tract: WI owners must sum to 100%, every WI tract must have
        a lease, and each owner's NRI must equal WI*(1 - royalty). Any mismatch
        is a logical contradiction the Examiner must reconcile -> TITLE_GAP.
        """
        failures: list[Failure] = []
        ogl_by_tract: dict[int, list[OGLEntry]] = {}
        for e in ogl_data:
            ogl_by_tract.setdefault(e.tract_number, []).append(e)
        wi_by_tract: dict[int, list[WIEntry]] = {}
        for w in wi_data:
            wi_by_tract.setdefault(w.tract_number, []).append(w)

        for tract in sorted(set(ogl_by_tract) | set(wi_by_tract)):
            ref = f"Tract {tract}"
            leases = ogl_by_tract.get(tract, [])
            owners = wi_by_tract.get(tract, [])

            if owners and not leases:
                failures.append(self._gap(ref, "Working interest present but no OGL lease on record."))
                continue
            if leases and not owners:
                failures.append(self._gap(ref, "OGL lease present but no working-interest owners."))
                continue

            wi_total = sum(o.wi_decimal for o in owners)
            if abs(wi_total - 1.0) > self._tol:
                failures.append(self._gap(
                    ref, f"Working interest sums to {wi_total:.6f}, not 1.000000.",
                    {"wi_total": wi_total}))

            royalty = leases[0].royalty_decimal if leases else 0.0
            for o in owners:
                expected_nri = o.wi_decimal * (1.0 - royalty)
                if abs(o.nri_decimal - expected_nri) > self._tol:
                    failures.append(self._gap(
                        ref,
                        f"Owner '{o.owner}': NRI {o.nri_decimal:.6f} != "
                        f"WI*(1-royalty) {expected_nri:.6f} (royalty {royalty:.6f}).",
                        {"owner": o.owner, "nri": o.nri_decimal,
                         "expected_nri": expected_nri, "royalty": royalty}))
        return GateResult(Gate.OGL_PARITY, tuple(failures))

    def _gap(self, ref: str, detail: str, proof: Optional[dict[str, Any]] = None) -> Failure:
        return Failure(Gate.OGL_PARITY, FailureCategory.TITLE_GAP, ref, detail, proof or {})
