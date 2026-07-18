"""Chain-of-title graph (Move #14) with document-coverage analysis (Move #28).

Parties, instruments, and tracts form a graph; conveyances are edges from
grantor to grantee. Analysis finds chain breaks (a grantor who never
acquired), long unexplained gaps, and repeated conveyances of the same tract
— the defects a landman hunts for on a runsheet, computed deterministically.

Identity caution (Move #57): party names are normalized only for matching
(case, punctuation, whitespace); originals are preserved, and near-miss
names are *reported*, never silently merged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction

SOVEREIGN_NAMES = {"united states", "usa", "us land office", "u s land office",
                   "state of oklahoma", "state of wyoming"}


def normalize_name(name: str) -> str:
    text = re.sub(r"[^\w\s]", " ", str(name)).casefold()
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class InstrumentNode:
    instrument_id: str                  # instrument number or book/page
    date: str                           # ISO recorded date (sortable)
    grantors: list
    grantees: list
    kind: str = ""                      # deed, assignment, lease, release, ...
    book_page: str = ""
    legal_description: str = ""
    tracts: list = field(default_factory=list)
    interest_conveyed: Fraction | None = None
    evidence_id: str = ""
    notes: str = ""


@dataclass
class ChainFinding:
    rule: str
    severity: str                       # critical | high | medium | low
    instrument_id: str
    message: str
    recommendation: str = ""


class ChainGraph:
    # Conveyance kinds that transfer title; releases/affidavits/etc. don't
    # establish the grantee as a title holder.
    TITLE_KINDS = ("deed", "patent", "assignment", "conveyance", "merger", "probate")

    def __init__(self):
        self.instruments: list[InstrumentNode] = []

    def add(self, node: InstrumentNode) -> None:
        self.instruments.append(node)

    def parties(self) -> set[str]:
        out = set()
        for n in self.instruments:
            out.update(normalize_name(p) for p in n.grantors + n.grantees)
        return out

    def instruments_for(self, party: str) -> list[InstrumentNode]:
        key = normalize_name(party)
        return [n for n in self._sorted()
                if key in [normalize_name(p) for p in n.grantors + n.grantees]]

    def _sorted(self) -> list[InstrumentNode]:
        return sorted(self.instruments, key=lambda n: (n.date or "9999", n.instrument_id))

    def _is_title_kind(self, kind: str) -> bool:
        k = kind.casefold()
        return any(t in k for t in self.TITLE_KINDS)

    # -- analysis ------------------------------------------------------------

    def analyze(self, gap_years: int = 15) -> list[ChainFinding]:
        findings: list[ChainFinding] = []
        findings += self._chain_breaks()
        findings += self._coverage_gaps(gap_years)
        findings += self._repeated_conveyances()
        findings += self._name_near_misses()
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        findings.sort(key=lambda f: order[f.severity])
        return findings

    def _chain_breaks(self) -> list[ChainFinding]:
        """A grantor conveying title without ever having acquired it."""
        out = []
        holders: set[str] = set(SOVEREIGN_NAMES)
        for n in self._sorted():
            if not self._is_title_kind(n.kind):
                continue
            for grantor in n.grantors:
                key = normalize_name(grantor)
                if key not in holders and not any(s in key for s in SOVEREIGN_NAMES):
                    out.append(ChainFinding(
                        "chain_break", "critical", n.instrument_id,
                        f"grantor {grantor!r} conveys ({n.kind} {n.book_page or n.instrument_id}"
                        f", {n.date}) but never appears as a grantee earlier in the chain",
                        "Search for the missing acquisition instrument (probate, unrecorded "
                        "assignment, name variation) before accepting this conveyance."))
            holders.update(normalize_name(g) for g in n.grantees)
        return out

    def _coverage_gaps(self, gap_years: int) -> list[ChainFinding]:
        """Long silent periods in the record (Move #28: missing periods)."""
        out = []
        dated = [n for n in self._sorted() if re.match(r"^\d{4}", n.date or "")]
        for prev, cur in zip(dated, dated[1:]):
            gap = int(cur.date[:4]) - int(prev.date[:4])
            if gap >= gap_years:
                out.append(ChainFinding(
                    "coverage_gap", "high", cur.instrument_id,
                    f"{gap}-year silence between {prev.book_page or prev.instrument_id} "
                    f"({prev.date}) and {cur.book_page or cur.instrument_id} ({cur.date})",
                    "Run the index for the silent period; look for probate, mortgages, "
                    "releases, or mis-indexed instruments."))
        return out

    def _repeated_conveyances(self) -> list[ChainFinding]:
        """Same grantor conveys the same tract twice with no reacquisition."""
        out = []
        conveyed: dict[tuple, str] = {}
        for n in self._sorted():
            if not self._is_title_kind(n.kind):
                continue
            for grantor in n.grantors:
                for tract in (n.tracts or [n.legal_description or "(unspecified)"]):
                    key = (normalize_name(grantor), normalize_name(str(tract)))
                    if key in conveyed:
                        out.append(ChainFinding(
                            "repeated_conveyance", "high", n.instrument_id,
                            f"{grantor!r} conveys {tract!r} again in "
                            f"{n.book_page or n.instrument_id} (first at {conveyed[key]}) "
                            "with no intervening reacquisition",
                            "Verify whether the interests are different estates/depths or "
                            "whether one instrument is corrective; do not double-count."))
                    conveyed[key] = n.book_page or n.instrument_id
            # a grantee re-acquiring clears the flag for that tract
            for grantee in n.grantees:
                for tract in (n.tracts or [n.legal_description or "(unspecified)"]):
                    conveyed.pop((normalize_name(grantee), normalize_name(str(tract))), None)
        return out

    def _name_near_misses(self) -> list[ChainFinding]:
        """Names that differ only by initials/subsets — report, never merge."""
        out = []
        names = sorted(self.parties())
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                ta, tb = set(a.split()), set(b.split())
                if a != b and (ta < tb or tb < ta) and (ta & tb):
                    out.append(ChainFinding(
                        "name_near_miss", "medium", "",
                        f"party names {a!r} and {b!r} may be the same person/entity",
                        "Merge identities only with supporting evidence (a/k/a affidavit, "
                        "probate, corporate filing); otherwise keep them distinct."))
        return out
