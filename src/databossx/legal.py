"""Legal-description normalization (Public Land Survey System: Section/Township/Range).

Real title documents write the same tract many ways -- "Sec 31 T12N R24W",
"Section 31, Township 12 North, Range 24 West", "31-12N-24W", "S31-T12N-R24W".
Grouping a chain of title correctly requires collapsing those to one canonical
key. This module parses the S/T/R descriptor across those forms and returns a
stable key, or ``None`` when it cannot parse all three components -- it never
guesses a tract it cannot read.

Aligns with the #56 bounded-port slice S2 (document/legal intelligence),
implemented natively in the canonical package. Pure, deterministic, no schema.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_DIR = {"north": "N", "south": "S", "east": "E", "west": "W",
        "n": "N", "s": "S", "e": "E", "w": "W"}

# Section: "Sec 31", "Section 31", "Sec. 31", "S31", "Sctn 31".
_SEC = re.compile(r"\b(?:sec(?:tion|\.|tn)?|s)\s*\.?\s*(\d{1,2})\b", re.I)
# Township: "T12N", "Twp 12 North", "Township 12 N", "12N".
_TWP = re.compile(
    r"\b(?:t(?:wp|ownship)?\.?\s*)?(\d{1,3})\s*[-\s]?\s*"
    r"(north|south|n|s)\b", re.I)
# Range: "R24W", "Rng 24 West", "Range 24 W", "24W".
_RNG = re.compile(
    r"\b(?:r(?:ng|ange)?\.?\s*)?(\d{1,3})\s*[-\s]?\s*"
    r"(east|west|e|w)\b", re.I)

# Compact hyphenated form: "31-12N-24W", "31-T12N-R24W", "S31-T12N-R24W".
_COMPACT = re.compile(
    r"\b(?:s)?(\d{1,2})\s*-\s*t?(\d{1,3})\s*([nsNS])\s*-\s*"
    r"r?(\d{1,3})\s*([ewEW])\b", re.I)


@dataclass(frozen=True)
class LegalDescription:
    section: Optional[str]
    township: Optional[str]   # e.g. "12N"
    range: Optional[str]      # e.g. "24W"

    @property
    def complete(self) -> bool:
        return bool(self.section and self.township and self.range)

    @property
    def key(self) -> Optional[str]:
        if not self.complete:
            return None
        return f"{self.section}-{self.township}-{self.range}"


def _dir(word: str) -> str:
    return _DIR.get(str(word).strip().lower(), str(word).strip().upper()[:1])


def parse_legal(text: Optional[str]) -> LegalDescription:
    """Parse a legal description into Section/Township/Range (best-effort)."""
    s = str(text or "")
    # Try the compact hyphenated form first (section-first, no "Sec" prefix).
    m = _COMPACT.search(s)
    if m:
        return LegalDescription(
            section=str(int(m.group(1))),
            township=f"{int(m.group(2))}{_dir(m.group(3))}",
            range=f"{int(m.group(4))}{_dir(m.group(5))}")
    sec = _SEC.search(s)
    twp = _TWP.search(s)
    rng = _RNG.search(s)
    section = str(int(sec.group(1))) if sec else None
    township = f"{int(twp.group(1))}{_dir(twp.group(2))}" if twp else None
    range_ = f"{int(rng.group(1))}{_dir(rng.group(2))}" if rng else None
    return LegalDescription(section=section, township=township, range=range_)


def canonical_key(text: Optional[str]) -> Optional[str]:
    """Canonical S-T-R key (e.g. ``31-12N-24W``), or ``None`` if not parseable."""
    return parse_legal(text).key


def tract_key(text: Optional[str]) -> str:
    """A stable tract key for grouping.

    Prefer the canonical S/T/R key; fall back to an alphanumeric squash of the
    raw text when the descriptor cannot be fully parsed (so nothing is dropped).
    This is backward compatible with the prior alphanumeric-only keying.
    """
    key = canonical_key(text)
    if key:
        return key
    return re.sub(r"[^A-Za-z0-9]+", "", str(text or "")).upper()
