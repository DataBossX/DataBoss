"""Legal-description extraction and normalization (Move #13) with exact
aliquot acreage math (feeds Move #65 acreage reconciliation).

Parses aliquot chains ("S/2 N/2 SW/4"), multi-tract descriptions joined by
"and"/","/"+", section-township-range in several notations, "less N acres"
exceptions, government lots, and depth/formation limitations. Both the
verbatim text and the normalized structure are preserved.

Acreage is exact ``Fraction`` math on a 640-acre section. Anything not
computable (metes and bounds, government lots without a plat) yields
``acres=None`` and an ``OPEN`` note — never a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction

SECTION_ACRES = Fraction(640)

_ALIQUOT_TOKEN = re.compile(r"\b(N|S|E|W|NE|NW|SE|SW)\s*/\s*(2|4)\b", re.IGNORECASE)
_LOT = re.compile(r"\blots?\s+([\d ,and]+)", re.IGNORECASE)
_LESS = re.compile(r"\bless\b[^\d]*([\d.]+)\s*acres?", re.IGNORECASE)
_STR_COMPACT = re.compile(          # 32-11N-25W
    r"\b(\d{1,2})\s*-\s*(\d{1,2})\s*([NS])\s*-\s*(\d{1,3})\s*([EW])\b", re.IGNORECASE)
_STR_VERBOSE = re.compile(
    r"\bsec(?:tion)?\.?\s+(\d{1,2})\b.*?"
    r"\btownship\s+(\d{1,2})\s+(north|south)\b.*?"
    r"\brange\s+(\d{1,3})\s+(east|west)\b", re.IGNORECASE | re.DOTALL)
_DEPTH = re.compile(
    r"((?:below|above|from|to|between)\s[^,;]*?(?:\d[\d,]*\s*(?:feet|ft)|"
    r"top\s+of?\s+\w+|base\s+of?\s+\w+|\b(?:hunton|morrow|springer|granite wash)\b)[^,;]*)",
    re.IGNORECASE)
_METES = re.compile(r"metes\s+and\s+bounds|beginning\s+at", re.IGNORECASE)


@dataclass
class Tract:
    text: str                       # normalized aliquot text, e.g. "S/2 N/2 SW/4"
    fraction: Fraction | None       # of the full section
    acres: Fraction | None          # None when not computable
    lot: str = ""
    note: str = ""


@dataclass
class LegalDescription:
    verbatim: str
    tracts: list = field(default_factory=list)
    section: str = ""
    township: str = ""
    range: str = ""
    exceptions_acres: Fraction = Fraction(0)
    depth_limitation: str = ""
    notes: list = field(default_factory=list)

    @property
    def gross_acres(self) -> Fraction | None:
        """Sum of computable tract acres minus exceptions; None if any tract
        is non-computable (a partial number would be misleading)."""
        total = Fraction(0)
        for t in self.tracts:
            if t.acres is None:
                return None
            total += t.acres
        return total - self.exceptions_acres


def _parse_aliquot_chain(chunk: str) -> Tract | None:
    tokens = _ALIQUOT_TOKEN.findall(chunk)
    if not tokens:
        return None
    fraction = Fraction(1)
    parts = []
    for direction, denom in tokens:
        fraction *= Fraction(1, int(denom))
        parts.append(f"{direction.upper()}/{denom}")
    return Tract(text=" ".join(parts), fraction=fraction,
                 acres=fraction * SECTION_ACRES)


def parse(text: str) -> LegalDescription:
    desc = LegalDescription(verbatim=text)
    work = str(text)

    m = _STR_COMPACT.search(work) or None
    if m:
        desc.section = str(int(m.group(1)))
        desc.township = f"{int(m.group(2))}{m.group(3).upper()}"
        desc.range = f"{int(m.group(4))}{m.group(5).upper()}"
        work = _STR_COMPACT.sub(" ", work)
    else:
        mv = _STR_VERBOSE.search(work)
        if mv:
            desc.section = str(int(mv.group(1)))
            desc.township = f"{int(mv.group(2))}{mv.group(3)[0].upper()}"
            desc.range = f"{int(mv.group(4))}{mv.group(5)[0].upper()}"
            work = _STR_VERBOSE.sub(" ", work)

    md = _DEPTH.search(work)
    if md:
        desc.depth_limitation = md.group(1).strip()
        work = _DEPTH.sub(" ", work)

    for ml in _LESS.finditer(work):
        desc.exceptions_acres += Fraction(ml.group(1))
        desc.notes.append(f"exception: less {ml.group(1)} acres (source of exception OPEN)")
    work = _LESS.sub(" ", work)

    if _METES.search(work):
        desc.tracts.append(Tract(text="(metes and bounds)", fraction=None, acres=None,
                                 note="metes-and-bounds parcel; acreage OPEN without survey"))
        desc.notes.append("metes-and-bounds description present; not aliquot-computable")

    for mlot in _LOT.finditer(work):
        for lot_no in re.findall(r"\d+", mlot.group(1)):
            desc.tracts.append(Tract(text=f"Lot {lot_no}", fraction=None, acres=None,
                                     lot=lot_no,
                                     note="government lot; acreage OPEN without plat"))
    work = _LOT.sub(" ", work)

    if re.search(r"\ball\s+(of\s+)?(said\s+)?sec", str(text), re.IGNORECASE) or \
            re.fullmatch(r"\s*all\s*", work, re.IGNORECASE):
        desc.tracts.append(Tract(text="ALL", fraction=Fraction(1), acres=SECTION_ACRES))
        return desc

    # split remaining text into tract chunks on and / , / + / ;
    for chunk in re.split(r"\band\b|[,;+]", work, flags=re.IGNORECASE):
        tract = _parse_aliquot_chain(chunk)
        if tract:
            desc.tracts.append(tract)

    if not desc.tracts:
        desc.notes.append("no computable tract parsed; REVIEW REQUIRED")
    return desc


def reconcile_acreage(descriptions: list[str], expected_total: Fraction | int
                      ) -> tuple[Fraction | None, list[str]]:
    """Sum gross acres across descriptions and compare with the expected
    total (Move #65). Returns (total_or_None, problems)."""
    problems: list[str] = []
    total = Fraction(0)
    for text in descriptions:
        d = parse(text)
        acres = d.gross_acres
        if acres is None:
            problems.append(f"not computable: {text!r} ({'; '.join(d.notes) or 'unknown form'})")
            return None, problems
        total += acres
    if total != Fraction(expected_total):
        problems.append(f"acreage total {float(total)} != expected {expected_total}")
    return total, problems
