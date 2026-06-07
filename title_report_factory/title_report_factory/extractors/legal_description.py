"""Extract PLSS legal descriptions (Section / Township / Range) from text.

Handles common Oklahoma styles, e.g.:
    "Section 27, Township 11 North, Range 25 West"
    "Sec 27 T11N R25W"      "S27-T11N-R25W"     "27-11N-25W"
Returns a LegalDescription with a confidence score. Partial matches are kept
and flagged rather than discarded.
"""
from __future__ import annotations

import re
from typing import List, Optional

from ..models import LegalDescription
from ..utils import clean_ws

_SEC = r"(?:sec(?:tion)?\.?\s*)?(?P<sec>\d{1,2})"
_TWP = r"(?:t(?:ownship)?\.?\s*)?(?P<twp>\d{1,3})\s*(?P<twpdir>n(?:orth)?|s(?:outh)?)"
_RNG = r"(?:r(?:ange)?\.?\s*)?(?P<rng>\d{1,3})\s*(?P<rngdir>e(?:ast)?|w(?:est)?)"

# Full pattern with separators between each token.
_FULL = re.compile(
    rf"{_SEC}[\s,.\-]+{_TWP}[\s,.\-]+{_RNG}",
    re.IGNORECASE,
)

_QUARTERS = re.compile(
    r"\b((?:[NS][EW]/4|[NSEW]/2|[NS][EW]\s*(?:1/4|quarter)|"
    r"north(?:east|west)|south(?:east|west))(?:\s+of\s+the\s+[A-Za-z/0-9 ]+?)?)\b",
    re.IGNORECASE,
)


def _norm_dir(d: str) -> str:
    d = d.lower()
    return {"n": "N", "north": "N", "s": "S", "south": "S",
            "e": "E", "east": "E", "w": "W", "west": "W"}.get(d, d[:1].upper())


def extract_legal(text: str,
                  expected_county: Optional[str] = None,
                  expected_state: Optional[str] = None) -> LegalDescription:
    t = text or ""
    out = LegalDescription()

    m = _FULL.search(t)
    if m:
        sec = m.group("sec")
        twp = f"{int(m.group('twp'))}{_norm_dir(m.group('twpdir'))}"
        rng = f"{int(m.group('rng'))}{_norm_dir(m.group('rngdir'))}"
        out.section = sec
        out.township = twp
        out.range = rng
        out.raw = clean_ws(m.group(0))
        out.confidence = 85.0
    else:
        out.confidence = 0.0

    quarters: List[str] = []
    for q in _QUARTERS.finditer(t):
        val = clean_ws(q.group(1))
        if val and val.lower() not in (x.lower() for x in quarters):
            quarters.append(val)
    out.quarter_calls = quarters[:12]
    if quarters and out.confidence:
        out.confidence = min(95.0, out.confidence + 5.0)

    # County / State if mentioned near the description.
    cm = re.search(r"([A-Z][a-z]+)\s+County", t)
    if cm:
        out.county = cm.group(1) + " County"
    sm = re.search(r"\b(Oklahoma|Texas|Kansas|Colorado|New Mexico)\b", t)
    if sm:
        out.state = sm.group(1)

    # If we know the target county/state, a match there boosts confidence.
    if expected_county and out.county and expected_county.split()[0].lower() in out.county.lower():
        out.confidence = min(98.0, out.confidence + 3.0)

    return out


def matches_subject(legal: LegalDescription, section: str,
                    township: str, range_: str) -> bool:
    """True if the extracted legal hits the subject section-township-range."""
    def norm(x: Optional[str]) -> str:
        return re.sub(r"[^0-9a-z]", "", (x or "").lower())

    return (
        bool(legal.section) and norm(legal.section) == norm(section)
        and norm(legal.township) == norm(township)
        and norm(legal.range) == norm(range_)
    )
