"""
matching.py
===========
Field normalization + fuzzy similarity for HorizonTitleLinkExtractor.

Why this exists: exact normalized equality flags trivial differences ("John A
Smith" vs "John A. Smith") as real corrections, drowning the user in noise. This
module classifies every field difference as:

    "same"   - effectively identical (ignore)
    "minor"  - small/formatting difference (note it, do not treat as a change)
    "major"  - a substantive difference worth human review

It also provides similarity scores used by the consensus engine so two models
that read "ACME L.L.C." and "ACME LLC" are recognised as agreeing.

Uses rapidfuzz when available; falls back to the stdlib difflib so the tool
works (and tests pass) even before optional deps are installed.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any

try:  # optional, much faster + better quality
    from rapidfuzz.fuzz import token_sort_ratio as _rf_token
    from rapidfuzz.fuzz import ratio as _rf_ratio

    def _ratio(a: str, b: str) -> float:
        return _rf_ratio(a, b) / 100.0

    def _token_ratio(a: str, b: str) -> float:
        return _rf_token(a, b) / 100.0
except Exception:  # pragma: no cover - fallback path
    from difflib import SequenceMatcher

    def _ratio(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    def _token_ratio(a: str, b: str) -> float:
        ta = " ".join(sorted(a.split()))
        tb = " ".join(sorted(b.split()))
        return SequenceMatcher(None, ta, tb).ratio()


DATE_FIELDS = {"filed_date", "recorded_date", "effective_date"}
NAME_FIELDS = {"grantor", "grantee"}
LEGAL_FIELDS = {"legal_description"}

# Tokens that carry no distinguishing meaning when comparing company/person names.
_NAME_NOISE = re.compile(
    r"\b(the|a|an|and|&|of|llc|l\.l\.c|inc|incorporated|corp|corporation|co|"
    r"company|lp|l\.p|llp|ltd|trust|trustee|trustees|et|ux|al|vir|family|"
    r"living|revocable|jr|sr|ii|iii|iv|mr|mrs|ms)\b",
    re.I,
)
_PUNCT = re.compile(r"[.,;:#/\\()\-]+")
_WS = re.compile(r"\s+")


def normalize_ws(v: Any) -> str:
    if v is None:
        return ""
    return _WS.sub(" ", str(v)).strip()


def normalize_date(v: Any) -> str:
    """Return YYYY-MM-DD when parseable, else the trimmed original string."""
    if v in (None, ""):
        return ""
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%-m/%-d/%Y",
                "%B %d, %Y", "%b %d, %Y", "%d-%b-%Y", "%Y/%m/%d"):
        try:
            return _dt.datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def _canon(v: Any) -> str:
    s = _PUNCT.sub(" ", normalize_ws(v).lower())
    return _WS.sub(" ", s).strip()


# Collapse runs of 2+ single letters ("l l c" -> "llc") so punctuated company
# suffixes match their compact form. Lone initials ("john a smith") are left be.
_LETTER_RUN = re.compile(r"\b([a-z])(?:\s+([a-z]))+\b")


def _collapse_letter_runs(s: str) -> str:
    return _LETTER_RUN.sub(lambda m: m.group(0).replace(" ", ""), s)


def _canon_name(v: Any) -> str:
    s = _collapse_letter_runs(_canon(v))
    s = _NAME_NOISE.sub(" ", s)
    return _WS.sub(" ", s).strip()


_LEGAL_REPL = {
    r"\bquarter\b": "4", r"\bqtr\b": "4",
    r"\bnorthwest\b": "nw", r"\bnortheast\b": "ne",
    r"\bsouthwest\b": "sw", r"\bsoutheast\b": "se",
    r"\bnorth\b": "n", r"\bsouth\b": "s", r"\beast\b": "e", r"\bwest\b": "w",
    r"\bsection\b": "sec", r"\btownship\b": "twp", r"\brange\b": "rng",
    r"\bhalf\b": "2",
}
# Tokens that carry no geometric meaning in a legal description.
_LEGAL_STOP = {"of", "the", "and", "a", "an", "in", "to", "all", "that", "part"}


def _canon_legal(v: Any) -> str:
    s = _canon(v)
    for pat, rep in _LEGAL_REPL.items():
        s = re.sub(pat, rep, s)
    return _WS.sub(" ", s).strip()


def _legal_tokens(v: Any) -> set[str]:
    """Significant tokens of a legal description (directions, fractions, numbers,
    sec/twp/rng). Direction codes like NW vs NE are distinct tokens, so a
    one-letter call change is correctly treated as a large difference."""
    return {t for t in _canon_legal(v).split() if t and t not in _LEGAL_STOP}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def similarity(field: str, a: Any, b: Any) -> float:
    """Field-aware similarity in [0, 1]. 1.0 means effectively identical."""
    if field in DATE_FIELDS:
        return 1.0 if normalize_date(a) == normalize_date(b) else 0.0
    if field in NAME_FIELDS:
        ca, cb = _canon_name(a), _canon_name(b)
        if not ca and not cb:
            return 1.0
        if not ca or not cb:
            return 0.0
        return max(_token_ratio(ca, cb), _ratio(ca, cb))
    if field in LEGAL_FIELDS:
        ta, tb = _legal_tokens(a), _legal_tokens(b)
        if not ta and not tb:
            return 1.0
        if not ta or not tb:
            return 0.0
        # Token-set Jaccard: direction/number tokens must match. This keeps
        # NW/4 vs NE/4 well apart while tolerating abbreviation/word-order.
        return _jaccard(ta, tb)
    ca, cb = _canon(a), _canon(b)
    if not ca and not cb:
        return 1.0
    if not ca or not cb:
        return 0.0
    return _ratio(ca, cb)


# Default thresholds; the orchestrator may override from config.
SAME_THRESHOLD = 0.97
MINOR_THRESHOLD = 0.85


def classify_diff(field: str, existing: Any, suggested: Any,
                  same_threshold: float = SAME_THRESHOLD,
                  minor_threshold: float = MINOR_THRESHOLD) -> str:
    """Return 'same' | 'minor' | 'major' for a single field comparison.

    If the AI suggested nothing (None/empty) we never call it a change.
    """
    if suggested in (None, ""):
        return "same"
    if normalize_ws(existing) == "" and normalize_ws(suggested) != "":
        return "major"  # spreadsheet blank, document has a value -> worth review
    sim = similarity(field, existing, suggested)
    if sim >= same_threshold:
        return "same"
    if sim >= minor_threshold:
        return "minor"
    return "major"


def values_agree(field: str, a: Any, b: Any,
                 threshold: float = MINOR_THRESHOLD) -> bool:
    """Used by consensus: do two model readings agree on a field?"""
    return similarity(field, a, b) >= threshold
