"""The self-healing verification engine — the deterministic brain of the swarm.

This is the piece the Cursor meta-prompt calls the "self-healing verification
loop": *if the Mathematician finds that the working interest does not tie to the
tract acreage, it returns the task to the Title Auditor with the error delta to
re-evaluate the runsheet notes.*

We implement that loop **deterministically**, on exact ``fractions.Fraction``
math, by reusing the :mod:`horizon` engine (which already refuses to fabricate
balances). An LLM is not trusted to add 1/3 + 5/128; the engine is. The CrewAI
agents in :mod:`command_center.agents` narrate and route what this module
computes — they never compute interest themselves.

The loop, per section:

    INGEST     read the OGL register + runsheet from the workbook
    AUDIT      chain each tract with exact interest math (horizon.chain_to_report)
    VERIFY     the Mathematician sums each tract's working interests and compares
               to the full 8/8 estate / gross acres; emits a delta per tract
    HEAL       for an *undetermined* conveyance (blank / unparseable interest),
               the Auditor re-reads that instrument's runsheet notes; if the note
               documents the interest ("all", "8/8", a fraction), it is adopted
               as an ASSUMED data point (highlighted yellow downstream) and the
               tract is re-verified
    ESCALATE   an over-conveyance, a chain-of-title break, or an undetermined
               interest the runsheet cannot resolve is tagged Needs Examiner
               Review — never healed by inventing a number

The loop is bounded and convergent: it stops on the first fully-balanced pass, on
a pass that makes no new assumption (no progress), or at ``max_loops``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from horizon.chaining import (
    OGLRecord,
    RunsheetNote,
    normalize_instrument,
    reconcile_chain,
)
from horizon.interest import (
    FULL,
    format_acres,
    format_fraction,
    try_parse_acres,
    try_parse_interest,
)
from horizon.models import ReportModel
from horizon.pipeline import (
    _tract_key,
    chain_to_report,
    read_ogl_records,
    read_runsheet_notes,
)

# Agent identities used to attribute telemetry lines (mirrors the CrewAI roles).
INGESTION = "INGESTION"
TITLE_AUDITOR = "TITLE_AUDITOR"
MATHEMATICIAN = "MATHEMATICIAN"
SYSTEM = "SYSTEM"


# --------------------------------------------------------------------------- #
# Telemetry
# --------------------------------------------------------------------------- #
@dataclass
class TelemetryEvent:
    """One line of the live telemetry console.

    ``agent`` attributes the thought to a member of the swarm; ``level`` drives
    the colour/icon in the Streamlit console.
    """

    agent: str
    level: str  # info | thought | action | verify | heal | warn | escalate | success
    message: str
    loop: int = 0
    data: dict = field(default_factory=dict)


# A sink is any callable that receives events as they happen (the Streamlit UI
# streams them; tests collect them into a list).
TelemetrySink = Callable[[TelemetryEvent], None]


class Telemetry:
    """Fan-out event recorder. Keeps a full transcript and streams to a sink."""

    def __init__(self, sink: Optional[TelemetrySink] = None) -> None:
        self._sink = sink
        self.events: List[TelemetryEvent] = []

    def emit(self, agent: str, level: str, message: str, loop: int = 0, **data) -> None:
        evt = TelemetryEvent(agent=agent, level=level, message=message, loop=loop, data=data)
        self.events.append(evt)
        if self._sink is not None:
            self._sink(evt)


# --------------------------------------------------------------------------- #
# Result model
# --------------------------------------------------------------------------- #
@dataclass
class TractBalance:
    """The Mathematician's verdict for one tract."""

    tract: str
    tract_legal: str
    gross_acres: Optional[Fraction]
    starting_interest: Fraction
    outstanding_sum: Fraction  # Σ of every party's live interest — should be 8/8
    delta: Fraction  # FULL − outstanding_sum (0 ⇒ ties out)
    net_acres_sum: Optional[Fraction]
    status: str  # balanced | healed | escalated | undetermined
    reasons: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)

    @property
    def balanced(self) -> bool:
        return self.status in ("balanced", "healed")

    def delta_acres(self) -> Optional[Fraction]:
        if self.gross_acres is None:
            return None
        return self.delta * self.gross_acres


@dataclass
class EngineResult:
    """Everything a report writer / UI needs from one run."""

    section: str
    report: ReportModel
    balances: List[TractBalance]
    # (row_index_in_report, canonical_field_name) pairs to highlight yellow.
    assumed_cells: List[Tuple[int, str]]
    loops_run: int
    converged: bool
    events: List[TelemetryEvent]

    @property
    def tracts_balanced(self) -> int:
        return sum(1 for b in self.balances if b.balanced)

    @property
    def tracts_escalated(self) -> int:
        return sum(1 for b in self.balances if b.status == "escalated")

    @property
    def tracts_undetermined(self) -> int:
        return sum(1 for b in self.balances if b.status == "undetermined")


# --------------------------------------------------------------------------- #
# Healing helpers
# --------------------------------------------------------------------------- #
_ALL_INTEREST_RE = re.compile(
    r"\b(all|entire|whole|100\s*%|8\s*/\s*8|right,?\s*title\s*and\s*interest)\b", re.I
)
_FRACTION_IN_TEXT_RE = re.compile(r"\b(\d+)\s*/\s*(\d+)\b")
_PERCENT_IN_TEXT_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*%")


def _party_key(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", " ", str(name or "")).upper().strip()


def infer_conveyed_from_notes(
    notes: List[str], holder_before: Optional[Fraction]
) -> Optional[Tuple[Fraction, str]]:
    """Try to resolve a blank/unparseable conveyance from its runsheet notes.

    Returns ``(assumed_fraction, human_reason)`` or ``None`` if the notes do not
    document the interest. Never guesses beyond what the note text supports:

    * an explicit fraction / percent in the note is adopted verbatim;
    * "all / entire / 8/8 / right, title and interest" is read as *all of the
      grantor's current holding* (``holder_before``), the standard reading of a
      blanket assignment.
    """
    joined = " ".join(n for n in notes if n)
    if not joined.strip():
        return None

    # "all / entire / whole / 8/8 / right, title and interest" = *all of the
    # grantor's current holding*, not the whole 8/8 estate. Checked first so a
    # phrase like "8/8 of grantor's holding" is read as holder_before, never as a
    # literal whole-estate conveyance that would fabricate an over-conveyance.
    if _ALL_INTEREST_RE.search(joined) and holder_before is not None:
        return holder_before, "runsheet note conveys all of grantor's interest (8/8 of holding)"

    m = _FRACTION_IN_TEXT_RE.search(joined)
    if m and int(m.group(2)) != 0:
        frac = Fraction(int(m.group(1)), int(m.group(2)))
        # n/n (e.g. 8/8, 4/4) is "the whole holding" → holder_before, not the estate.
        if frac == 1 and holder_before is not None:
            return holder_before, "runsheet note conveys the grantor's whole holding"
        return frac, f"runsheet note states {frac.numerator}/{frac.denominator}"

    m = _PERCENT_IN_TEXT_RE.search(joined)
    if m:
        frac = try_parse_interest(m.group(1) + "%")
        if frac is not None:
            return frac, f"runsheet note states {m.group(1)}%"

    return None


def _notes_for_instrument(
    runsheet_notes: List[RunsheetNote], instrument_number: str
) -> List[str]:
    key = normalize_instrument(instrument_number)
    out: List[str] = []
    for n in runsheet_notes:
        if normalize_instrument(n.instrument_number) == key and (n.note or "").strip():
            out.append(n.note)
    return out


def _tract_ledger(links, starting: Fraction) -> Tuple[Dict[str, Fraction], bool]:
    """Build a party→interest ledger by walking reconciled links.

    Returns ``(holdings, has_undetermined)``. ``has_undetermined`` is True when a
    link's conveyance could not be parsed (so the ledger can't be trusted).
    """
    holdings: Dict[str, Fraction] = {}
    has_undetermined = False
    if links:
        holdings[_party_key(links[0].grantor)] = starting
    for link in links:
        if link.conveyed is None:
            has_undetermined = True
            continue
        g, gr = _party_key(link.grantor), _party_key(link.grantee)
        holdings[g] = holdings.get(g, Fraction(0)) - link.conveyed
        holdings[gr] = holdings.get(gr, Fraction(0)) + link.conveyed
    return holdings, has_undetermined


# --------------------------------------------------------------------------- #
# The engine
# --------------------------------------------------------------------------- #
class SelfHealingEngine:
    """Drives INGEST → AUDIT → VERIFY → HEAL/ESCALATE for a whole section."""

    def __init__(
        self,
        section: str = "31-12N-24W",
        max_loops: int = 5,
        telemetry: Optional[Telemetry] = None,
    ) -> None:
        self.section = section
        self.max_loops = max_loops
        self.tel = telemetry or Telemetry()

    # -- ingestion ---------------------------------------------------------- #
    def ingest(self, workbook: Path) -> Tuple[List[OGLRecord], List[RunsheetNote]]:
        self.tel.emit(INGESTION, "action", f"Opening workbook {Path(workbook).name}")
        ogl = read_ogl_records(Path(workbook))
        notes = read_runsheet_notes(Path(workbook))
        self.tel.emit(
            INGESTION,
            "info",
            f"Structured {len(ogl)} OGL conveyance rows and {len(notes)} runsheet notes.",
            data={"ogl": len(ogl), "notes": len(notes)},
        )
        if not ogl:
            self.tel.emit(
                INGESTION,
                "warn",
                "No OGL conveyance rows found — check the workbook has an OGL sheet.",
            )
        return ogl, notes

    def ingest_records(
        self, ogl: List[OGLRecord], notes: List[RunsheetNote]
    ) -> "EngineResult":
        """Run the loop over already-parsed records (used by tests + tools)."""
        return self._run(ogl, notes)

    def run(self, workbook: Path) -> EngineResult:
        ogl, notes = self.ingest(Path(workbook))
        return self._run(ogl, notes)

    # -- the loop ----------------------------------------------------------- #
    def _run(self, ogl: List[OGLRecord], notes: List[RunsheetNote]) -> EngineResult:
        # assumptions[instrument_key] = (assumed_conveyed_str, human_reason)
        assumptions: Dict[str, Tuple[str, str]] = {}
        converged = False
        loops_run = 0

        for loop in range(1, self.max_loops + 1):
            loops_run = loop
            self.tel.emit(SYSTEM, "info", f"── Loop {loop}/{self.max_loops} ──", loop=loop)

            working = self._apply_assumptions(ogl, assumptions)
            balances, new_assumptions = self._verify(working, notes, assumptions, loop)

            unbalanced = [b for b in balances if not b.balanced and b.status != "escalated"]
            if not unbalanced:
                converged = True
                escalated = sum(1 for b in balances if b.status == "escalated")
                tail = (
                    f" {escalated} tract(s) remain escalated for examiner review."
                    if escalated
                    else ""
                )
                self.tel.emit(
                    MATHEMATICIAN,
                    "success",
                    f"No undetermined interests remain after loop {loop}.{tail}",
                    loop=loop,
                )
                break

            if not new_assumptions:
                self.tel.emit(
                    TITLE_AUDITOR,
                    "warn",
                    "No further assumption is supportable from the runsheet — "
                    "escalating the remaining gaps to examiner review.",
                    loop=loop,
                )
                break

            for key, (val, reason) in new_assumptions.items():
                assumptions[key] = (val, reason)
                self.tel.emit(
                    TITLE_AUDITOR,
                    "heal",
                    f"Instrument {key}: assuming conveyed = {val} ({reason}). "
                    f"Flagged ASSUMED (yellow) and returned to the Mathematician.",
                    loop=loop,
                )

        # Final authoritative build through the horizon pipeline (rich TitleRows).
        working = self._apply_assumptions(ogl, assumptions)
        build = chain_to_report(working, notes, section=self.section)
        balances, _ = self._verify(working, notes, assumptions, loops_run)
        assumed_cells = self._locate_assumed_cells(build.report, assumptions)

        self.tel.emit(
            SYSTEM,
            "success" if converged else "warn",
            (
                f"Converged in {loops_run} loop(s). "
                if converged
                else f"Stopped after {loops_run} loop(s) with unresolved gaps. "
            )
            + f"{sum(1 for b in balances if b.balanced)}/{len(balances)} tracts tie out.",
        )
        return EngineResult(
            section=self.section,
            report=build.report,
            balances=balances,
            assumed_cells=assumed_cells,
            loops_run=loops_run,
            converged=converged,
            events=list(self.tel.events),
        )

    # -- audit + verify one pass ------------------------------------------- #
    def _verify(
        self,
        ogl: List[OGLRecord],
        notes: List[RunsheetNote],
        existing_assumptions: Dict[str, Tuple[str, str]],
        loop: int,
    ) -> Tuple[List[TractBalance], Dict[str, Tuple[str, str]]]:
        """Chain + verify every tract; propose new assumptions for the gaps."""
        tracts: Dict[str, List[OGLRecord]] = {}
        for rec in ogl:
            tracts.setdefault(_tract_key(rec.legal_description) or "UNSPECIFIED", []).append(rec)

        balances: List[TractBalance] = []
        new_assumptions: Dict[str, Tuple[str, str]] = {}

        for tract_key, records in tracts.items():
            tract_legal = records[0].legal_description if records else ""
            self.tel.emit(
                TITLE_AUDITOR,
                "action",
                f"Chaining tract {tract_legal or tract_key!r} "
                f"({len(records)} instrument(s)) from the full 8/8 estate.",
                loop=loop,
            )
            result = reconcile_chain(
                tract_key, records, starting_interest=FULL, tract_legal=tract_legal
            )
            holdings, has_undetermined = _tract_ledger(result.links, FULL)
            outstanding = sum(holdings.values(), Fraction(0))
            delta = FULL - outstanding

            gross = self._tract_gross(records)
            # Net acres carried by ALL live working interests = Σ(interest)×gross.
            # When the tract ties out (Σ = 8/8) this equals the gross acreage —
            # exactly the "WI sum == tract acres" invariant the Mathematician checks.
            net_sum = (outstanding * gross) if (gross is not None and not has_undetermined) else None

            status, reasons = self._classify(result, holdings, has_undetermined)
            assumptions_here = [
                r for k, (v, r) in existing_assumptions.items()
                if k in {normalize_instrument(rec.instrument_number) for rec in records}
            ]
            if assumptions_here and status == "balanced":
                status = "healed"

            bal = TractBalance(
                tract=tract_key,
                tract_legal=tract_legal,
                gross_acres=gross,
                starting_interest=FULL,
                outstanding_sum=outstanding,
                delta=delta,
                net_acres_sum=net_sum,
                status=status,
                reasons=reasons,
                assumptions=assumptions_here,
            )
            balances.append(bal)
            self._emit_verdict(bal, loop)

            # Propose healing for undetermined conveyances only.
            if status == "undetermined":
                proposed = self._propose_heal(records, notes, existing_assumptions, loop)
                new_assumptions.update(proposed)

        return balances, new_assumptions

    def _classify(self, result, holdings, has_undetermined):
        reasons = list(result.review_reasons)
        # Over-conveyance shows up as a negative holding OR a flagged reconciliation.
        over = any(v < 0 for v in holdings.values())
        if over:
            reasons.append("Over-conveyance: a party conveyed more than it held.")
            return "escalated", reasons
        if has_undetermined:
            return "undetermined", reasons
        if result.needs_examiner_review:
            # legal-tie or continuity break — a structural defect, not a heal-able gap
            return "escalated", reasons
        return "balanced", reasons

    def _propose_heal(self, records, notes, existing, loop):
        """For each undetermined conveyance, try to resolve it from the runsheet."""
        proposed: Dict[str, Tuple[str, str]] = {}
        # Recompute holder_before by re-walking with exact math up to each link.
        holder = FULL
        for rec in records:
            key = normalize_instrument(rec.instrument_number)
            conveyed_raw = str(rec.conveyed_interest or "").strip()
            parsed = try_parse_interest(conveyed_raw) if conveyed_raw else None
            is_undetermined = (rec.grantor or rec.grantee) and parsed is None
            if is_undetermined and key not in existing:
                tract_notes = _notes_for_instrument(notes, rec.instrument_number)
                inferred = infer_conveyed_from_notes(tract_notes, holder)
                if inferred is not None:
                    frac, reason = inferred
                    proposed[key] = (format_fraction(frac), reason)
                    self.tel.emit(
                        MATHEMATICIAN,
                        "verify",
                        f"Instrument {key or '(no number)'}: conveyed interest is "
                        f"undetermined — handing gap back to the Title Auditor.",
                        loop=loop,
                    )
                    holder = holder - frac if holder is not None else None
                else:
                    self.tel.emit(
                        MATHEMATICIAN,
                        "escalate",
                        f"Instrument {key or '(no number)'}: interest undetermined and "
                        f"unsupported by runsheet notes — escalating.",
                        loop=loop,
                    )
            elif parsed is not None and holder is not None:
                holder = holder - parsed
        return proposed

    def _emit_verdict(self, bal: TractBalance, loop: int) -> None:
        gross_txt = format_acres(bal.gross_acres) if bal.gross_acres is not None else "?"
        sum_txt = format_fraction(bal.outstanding_sum)
        if bal.status in ("balanced", "healed"):
            net_txt = format_acres(bal.net_acres_sum) if bal.net_acres_sum is not None else "?"
            self.tel.emit(
                MATHEMATICIAN,
                "verify",
                f"Tract {bal.tract_legal or bal.tract}: Σ working interest = {sum_txt} of 8/8 "
                f"✓  (net {net_txt} / {gross_txt} gross ac).",
                loop=loop,
            )
        elif bal.status == "undetermined":
            self.tel.emit(
                MATHEMATICIAN,
                "warn",
                f"Tract {bal.tract_legal or bal.tract}: Σ working interest cannot be summed "
                f"— an interest is undetermined (delta unknown).",
                loop=loop,
            )
        else:  # escalated
            reason = (bal.reasons[0] if bal.reasons else
                      f"does not tie to 8/8 (delta {format_fraction(bal.delta)})")
            self.tel.emit(
                MATHEMATICIAN,
                "escalate",
                f"Tract {bal.tract_legal or bal.tract}: ESCALATED — {reason} "
                f"Cannot heal by assumption; tagged Needs Examiner Review.",
                loop=loop,
            )

    # -- small helpers ------------------------------------------------------ #
    def _apply_assumptions(
        self, ogl: List[OGLRecord], assumptions: Dict[str, Tuple[str, str]]
    ) -> List[OGLRecord]:
        if not assumptions:
            return list(ogl)
        out: List[OGLRecord] = []
        for rec in ogl:
            key = normalize_instrument(rec.instrument_number)
            if key in assumptions and not str(rec.conveyed_interest or "").strip():
                val, _ = assumptions[key]
                out.append(
                    OGLRecord(
                        instrument_number=rec.instrument_number,
                        grantor=rec.grantor,
                        grantee=rec.grantee,
                        conveyed_interest=val,
                        legal_description=rec.legal_description,
                        doc_type=rec.doc_type,
                        instrument_date=rec.instrument_date,
                        gross_acres=rec.gross_acres,
                    )
                )
            else:
                out.append(rec)
        return out

    @staticmethod
    def _tract_gross(records: List[OGLRecord]) -> Optional[Fraction]:
        for rec in records:
            g = try_parse_acres(rec.gross_acres) if str(rec.gross_acres or "").strip() else None
            if g is not None:
                return g
        return None

    def _locate_assumed_cells(
        self, report: ReportModel, assumptions: Dict[str, Tuple[str, str]]
    ) -> List[Tuple[int, str]]:
        """Map assumed instruments to the report cells that carry assumed data."""
        cells: List[Tuple[int, str]] = []
        assumed_keys = set(assumptions)
        for idx, row in enumerate(report.rows):
            if normalize_instrument(row.instrument_number) in assumed_keys:
                for fld in ("conveyed_interest", "retained_interest", "net_mineral_acres"):
                    if str(getattr(row, fld, "") or "").strip():
                        cells.append((idx, fld))
        return cells


# --------------------------------------------------------------------------- #
# Convenience entry point
# --------------------------------------------------------------------------- #
def run_self_healing(
    workbook: Path,
    section: str = "31-12N-24W",
    max_loops: int = 5,
    sink: Optional[TelemetrySink] = None,
) -> EngineResult:
    """One-call entry: run the full self-healing loop over ``workbook``."""
    engine = SelfHealingEngine(section=section, max_loops=max_loops, telemetry=Telemetry(sink))
    return engine.run(Path(workbook))
