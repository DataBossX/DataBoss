"""Chain-of-title abstract / ownership-chain builder.

The runsheet is the reconciled register; the **abstract** is its human reading:
per tract, the instruments in chronological chain order, each showing the
grantor -> grantee transfer, the interest conveyed, the interest the grantor
retained, and the running examiner status. This is the "ownership chain" the
mission asks for, presented as a title examiner would read it.

It is a *presentation* of the reconciled rows -- it introduces no new numbers.
A row the engines flagged for examiner review stays flagged here; nothing is
balanced or invented to make a chain read cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .legal import tract_key as _tract_key


@dataclass
class AbstractEntry:
    """One instrument as it reads in the chain of title."""

    seq: int
    instrument_number: str
    instrument_date: str
    doc_type: str
    grantor: str
    grantee: str
    conveyed_interest: str
    retained_interest: str
    net_mineral_acres: str
    status: str
    remarks: str

    @property
    def needs_review(self) -> bool:
        return bool(self.status) and self.status.lower() != "ok"

    def sentence(self) -> str:
        """A one-line, plain-language reading of this link."""
        who = f"{self.grantor or '(unknown grantor)'} → {self.grantee or '(unknown grantee)'}"
        parts = [f"{self.seq}."]
        if self.instrument_date:
            parts.append(f"[{self.instrument_date}]")
        if self.doc_type:
            parts.append(self.doc_type)
        parts.append(who)
        if self.instrument_number:
            parts.append(f"(Inst. {self.instrument_number})")
        if self.conveyed_interest:
            parts.append(f"conveys {self.conveyed_interest}")
        if self.net_mineral_acres:
            parts.append(f"= {self.net_mineral_acres} net ac")
        line = " ".join(parts)
        if self.needs_review:
            line += f"  -- REVIEW: {self.remarks or self.status}"
        return line


@dataclass
class TractAbstract:
    """The chain of title for one tract."""

    tract: str
    legal_description: str
    entries: List[AbstractEntry] = field(default_factory=list)

    @property
    def review_count(self) -> int:
        return sum(1 for e in self.entries if e.needs_review)

    @property
    def final_grantee(self) -> str:
        """The last grantee in the chain -- the apparent current holder."""
        for e in reversed(self.entries):
            if e.grantee:
                return e.grantee
        return ""

    def narrative(self) -> str:
        """A chronological, plain-language chain-of-title paragraph."""
        header = f"Tract {self.legal_description or self.tract}:"
        lines = [header] + [f"  {e.sentence()}" for e in self.entries]
        if self.review_count:
            lines.append(f"  ({self.review_count} link(s) require examiner review "
                         "before this chain is certified.)")
        return "\n".join(lines)


def _get(row: object, key: str) -> str:
    if isinstance(row, dict):
        val = row.get(key, "")
    else:
        val = getattr(row, key, "")
    return "" if val is None else str(val)


def build_abstract(rows) -> List[TractAbstract]:
    """Group reconciled runsheet rows into per-tract chains of title.

    Rows are kept in their given (chain) order within each tract. ``rows`` may be
    :class:`horizon.models.TitleRow` objects or plain dicts with the same fields.
    """
    tracts: dict = {}
    order: List[str] = []
    for row in rows:
        legal = _get(row, "legal_description")
        key = _tract_key(legal) or "UNSPECIFIED"
        if key not in tracts:
            tracts[key] = TractAbstract(tract=key, legal_description=legal)
            order.append(key)
        ta = tracts[key]
        if legal and not ta.legal_description:
            ta.legal_description = legal
        ta.entries.append(AbstractEntry(
            seq=len(ta.entries) + 1,
            instrument_number=_get(row, "instrument_number"),
            instrument_date=_get(row, "instrument_date"),
            doc_type=_get(row, "doc_type"),
            grantor=_get(row, "grantor"),
            grantee=_get(row, "grantee"),
            conveyed_interest=_get(row, "conveyed_interest"),
            retained_interest=_get(row, "retained_interest"),
            net_mineral_acres=_get(row, "net_mineral_acres"),
            status=_get(row, "status") or "ok",
            remarks=_get(row, "remarks"),
        ))
    return [tracts[k] for k in order]


def abstract_narrative(abstracts: List[TractAbstract]) -> str:
    """Join every tract's chain-of-title narrative into one text block."""
    return "\n\n".join(a.narrative() for a in abstracts)
