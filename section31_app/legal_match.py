"""Compare runsheet legal descriptions to OGL legal descriptions.

Legal descriptions are messy free text ("SW/4 of SW/4", "S2 SW4", "the South
Half of the Southwest Quarter"). This module normalises them to a canonical
token form and fuzzy-matches runsheet legals against OGL legals so an OGL number
can be pushed confidently onto the matching tract/title/WI records.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from .config import LEGAL_MATCH_THRESHOLD

# Aliquot vocabulary normalisation.
_QUARTER = {
    "northeast": "NE", "ne": "NE", "northwest": "NW", "nw": "NW",
    "southeast": "SE", "se": "SE", "southwest": "SW", "sw": "SW",
    "north": "N", "n": "N", "south": "S", "s": "S",
    "east": "E", "e": "E", "west": "W", "w": "W",
}
_HALF = re.compile(r"\b(n|s|e|w)\s*/?\s*2\b", re.I)
_QTR = re.compile(r"\b(ne|nw|se|sw)\s*/?\s*4\b", re.I)


def normalize_legal(text: str) -> str:
    """Canonicalise a legal description to comparable token form."""
    if not text:
        return ""
    t = str(text).lower()
    t = t.replace("quarter", "4").replace("half", "2")
    t = t.replace("/4", "4").replace("/2", "2")
    t = re.sub(r"\bof the\b|\bof\b|\bthe\b", " ", t)
    # words -> abbreviations
    def repl(m):
        return _QUARTER.get(m.group(0), m.group(0))
    t = re.sub(r"\b(northeast|northwest|southeast|southwest|north|south|east|west)\b",
               repl, t)
    t = _QTR.sub(lambda m: m.group(1).upper() + "4", t)
    t = _HALF.sub(lambda m: m.group(1).upper() + "2", t)
    # Keep letters of BOTH cases -- earlier steps emit uppercase aliquots
    # (NE, NW, S2, SW4); a lowercase-only class would erase them.
    t = re.sub(r"[^a-zA-Z0-9 ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip().upper()
    # Collapse redundant repeats like "NE4 NE4" (spelled-out + abbreviation)
    # into a single, order-preserving token set.
    seen = set()
    tokens = []
    for tok in t.split():
        if tok not in seen:
            seen.add(tok)
            tokens.append(tok)
    return " ".join(tokens)


def _score(a: str, b: str) -> float:
    """0-100 similarity. Uses rapidfuzz when present, else a token fallback."""
    na, nb = normalize_legal(a), normalize_legal(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 100.0
    try:
        from rapidfuzz import fuzz

        return float(fuzz.token_sort_ratio(na, nb))
    except Exception:
        sa, sb = set(na.split()), set(nb.split())
        if not sa or not sb:
            return 0.0
        return 100.0 * len(sa & sb) / len(sa | sb)


@dataclass
class LegalMatch:
    runsheet_legal: str
    ogl_legal: str
    ogl_number: str
    match_score: float
    matched: bool
    method: str
    remarks: str = ""

    def as_row(self) -> Dict:
        return {
            "runsheet_legal": self.runsheet_legal,
            "ogl_legal": self.ogl_legal,
            "ogl_number": self.ogl_number,
            "match_score": round(self.match_score, 1),
            "matched": "yes" if self.matched else "no",
            "method": self.method,
            "remarks": self.remarks,
        }


def crosswalk(
    runsheet_legals: List[str],
    ogls: List[Dict],
    threshold: int = LEGAL_MATCH_THRESHOLD,
) -> List[LegalMatch]:
    """Match each runsheet legal to its best OGL legal.

    ``ogls`` is a list of dicts with at least ``legal_description`` and
    ``ogl_number``. Returns one :class:`LegalMatch` per runsheet legal.
    """
    method = "rapidfuzz.token_sort_ratio"
    try:
        import rapidfuzz  # noqa: F401
    except Exception:
        method = "jaccard-fallback"

    matches: List[LegalMatch] = []
    for legal in runsheet_legals:
        best: Optional[Dict] = None
        best_score = 0.0
        for ogl in ogls:
            sc = _score(legal, ogl.get("legal_description", ""))
            if sc > best_score:
                best_score, best = sc, ogl
        if best is not None and best_score >= threshold:
            matches.append(LegalMatch(
                runsheet_legal=legal,
                ogl_legal=best.get("legal_description", ""),
                ogl_number=best.get("ogl_number", ""),
                match_score=best_score, matched=True, method=method,
            ))
        else:
            matches.append(LegalMatch(
                runsheet_legal=legal,
                ogl_legal=best.get("legal_description", "") if best else "",
                ogl_number=best.get("ogl_number", "") if best else "",
                match_score=best_score, matched=False, method=method,
                remarks="below threshold -- needs examiner review",
            ))
    return matches


def push_ogl_onto_records(records: List[Dict], matches: List[LegalMatch]) -> int:
    """Stamp the matched OGL number onto tract/title/WI records in place.

    A record is updated only when its legal description matches a runsheet legal
    that resolved to an OGL, and the record does not already carry one. Returns
    the number of records updated.
    """
    resolved = {normalize_legal(m.runsheet_legal): m.ogl_number
                for m in matches if m.matched and m.ogl_number}
    updated = 0
    for rec in records:
        if rec.get("ogl_number"):
            continue
        key = normalize_legal(rec.get("legal_description", ""))
        if key and key in resolved:
            rec["ogl_number"] = resolved[key]
            note = "OGL# pushed from runsheet legal match"
            rec["remarks"] = (rec.get("remarks", "") + f" | {note}").strip(" |")
            updated += 1
    return updated
