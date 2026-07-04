"""Chaining engine: link the OGL register to runsheet notes and reconcile
interest down a title chain.

The single most common failure in a cursory title report is the break between
the OGL (oil & gas lease) register and the runsheet -- an instrument that
appears in one but not the other. So the primary key of the whole intelligence
layer is ``Instrument_Number``: we build a cross-reference dictionary keyed on
the *normalized* instrument number and report every unmatched key as a chain
break.

Interest is walked down the chain with the exact math in :mod:`horizon.interest`.
When the chain cannot be tied out (unknown starting interest, an over-conveyance,
or a conveyance whose grantor is not the current holder), the affected tract is
tagged "Needs Examiner Review" -- never balanced by fabrication.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Optional

from .interest import (
    FULL,
    Reconciliation,
    format_fraction,
    parse_interest,
    reconcile,
    try_parse_interest,
)


def normalize_instrument(value: Optional[object]) -> str:
    """Normalize an instrument/document number to a stable cross-reference key.

    Strips everything but alphanumerics and uppercases, so "2019-001234",
    "2019 001234" and "#2019001234" collapse to the same key. Empty in ->
    empty out (callers treat "" as "no instrument reference").
    """
    if value is None:
        return ""
    return re.sub(r"[^A-Za-z0-9]+", "", str(value)).upper()


@dataclass
class OGLRecord:
    """One row of the OGL / conveyance register."""

    instrument_number: str
    grantor: str = ""
    grantee: str = ""
    conveyed_interest: str = ""
    legal_description: str = ""
    doc_type: str = ""
    instrument_date: str = ""

    @property
    def key(self) -> str:
        return normalize_instrument(self.instrument_number)


@dataclass
class RunsheetNote:
    """One runsheet note, referencing an instrument by number."""

    instrument_number: str
    note: str = ""
    legal_description: str = ""

    @property
    def key(self) -> str:
        return normalize_instrument(self.instrument_number)


@dataclass
class CrossRef:
    """A cross-reference entry keyed by instrument number."""

    key: str
    ogl: Optional[OGLRecord] = None
    notes: List[RunsheetNote] = field(default_factory=list)

    @property
    def matched(self) -> bool:
        return self.ogl is not None and bool(self.notes)

    @property
    def status(self) -> str:
        if self.ogl is None:
            return "orphan_note"        # runsheet note with no OGL instrument
        if not self.notes:
            return "unreferenced_ogl"   # OGL instrument never noted in runsheet
        return "matched"


def build_cross_reference(
    ogl_records: List[OGLRecord],
    runsheet_notes: List[RunsheetNote],
) -> Dict[str, CrossRef]:
    """Build the Instrument_Number -> CrossRef dictionary linking both sheets."""
    xref: Dict[str, CrossRef] = {}
    for rec in ogl_records:
        k = rec.key
        if not k:
            continue
        xref.setdefault(k, CrossRef(key=k)).ogl = rec
    for note in runsheet_notes:
        k = note.key
        if not k:
            continue
        xref.setdefault(k, CrossRef(key=k)).notes.append(note)
    return xref


def find_chain_breaks(xref: Dict[str, CrossRef]) -> List[CrossRef]:
    """Return every cross-ref that is not fully matched (a chain break)."""
    return [c for c in xref.values() if c.status != "matched"]


# ---------------------------------------------------------------------------
# Chain-out interest reconciliation
# ---------------------------------------------------------------------------
@dataclass
class ChainLink:
    """One reconciled step in a title chain for a single tract."""

    instrument_number: str
    grantor: str
    grantee: str
    conveyed: Optional[Fraction]
    holder_before: Optional[Fraction]
    holder_after: Optional[Fraction]
    reconciliation: Reconciliation
    tied_to_legal: bool = True

    def as_dict(self) -> dict:
        def fmt(f: Optional[Fraction]) -> str:
            return format_fraction(f) if f is not None else ""

        return {
            "instrument_number": self.instrument_number,
            "grantor": self.grantor,
            "grantee": self.grantee,
            "conveyed": fmt(self.conveyed),
            "holder_before": fmt(self.holder_before),
            "holder_after": fmt(self.holder_after),
            "status": self.reconciliation.status,
            "tied_to_legal": "yes" if self.tied_to_legal else "NO",
            "note": self.reconciliation.note,
        }


@dataclass
class ChainResult:
    """Reconciliation of a full chain for one tract/legal description."""

    tract: str
    links: List[ChainLink] = field(default_factory=list)
    needs_examiner_review: bool = False
    review_reasons: List[str] = field(default_factory=list)

    @property
    def final_holder_interest(self) -> Optional[Fraction]:
        if not self.links:
            return None
        return self.links[-1].holder_after

    def flag(self, reason: str) -> None:
        self.needs_examiner_review = True
        if reason not in self.review_reasons:
            self.review_reasons.append(reason)


def _legal_ties(link_legal: str, tract_legal: str) -> bool:
    """Cheap containment check that a conveyance's legal description ties to the
    tract's legal description from the canonical cursory report. Empty conveyance
    legal is treated as "inherits tract" (ties)."""
    if not link_legal:
        return True
    a = re.sub(r"[^A-Za-z0-9]+", "", link_legal).upper()
    b = re.sub(r"[^A-Za-z0-9]+", "", tract_legal).upper()
    if not b:
        return True
    return a in b or b in a


def reconcile_chain(
    tract: str,
    records: List[OGLRecord],
    starting_interest: Optional[object] = FULL,
    tract_legal: str = "",
) -> ChainResult:
    """Walk ``records`` (in order) applying ``retained = grantor - conveyed``.

    ``starting_interest`` is the interest held by the first grantor (defaults to
    the full 8/8 estate). Pass ``None`` when it is unknown from the files -- the
    whole chain is then flagged for examiner review rather than assumed.

    A tract is flagged "Needs Examiner Review" when any of these hold:
      * the starting interest is unknown;
      * a conveyed interest cannot be parsed;
      * a conveyance exceeds the current holder's interest (over-conveyance);
      * a conveyance's legal description does not tie to the tract.
    """
    result = ChainResult(tract=tract, links=[])

    holder: Optional[Fraction]
    if starting_interest is None:
        holder = None
        result.flag(f"Starting interest for tract {tract!r} is undetermined.")
    else:
        holder = starting_interest if isinstance(starting_interest, Fraction) \
            else parse_interest(starting_interest)

    for rec in records:
        conveyed = try_parse_interest(rec.conveyed_interest) \
            if str(rec.conveyed_interest).strip() else None
        rc = reconcile(holder, conveyed)

        tied = _legal_ties(rec.legal_description, tract_legal)
        if not tied:
            result.flag(
                f"Instrument {rec.instrument_number!r} legal description does "
                f"not tie to tract {tract!r}."
            )

        holder_before = holder
        if rc.status == "balanced":
            # Grantor conveyed `conveyed`; grantor's *retained* interest is
            # rc.retained. The chain follows the grantee, who now holds the
            # conveyed interest (this is what carries forward down-chain).
            holder = conveyed
        elif rc.status == "over_conveyance":
            result.flag(rc.note)
            holder = None  # cannot trust downstream once the math breaks
        else:  # examiner_review (unknown holder or conveyed)
            result.flag(rc.note)
            holder = None

        result.links.append(ChainLink(
            instrument_number=rec.instrument_number,
            grantor=rec.grantor,
            grantee=rec.grantee,
            conveyed=conveyed,
            holder_before=holder_before,
            holder_after=holder,
            reconciliation=rc,
            tied_to_legal=tied,
        ))

    return result
