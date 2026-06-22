"""Normalize county index/document abbreviations to canonical doc types.

ALWAYS keep the original source wording too (callers store it in Notes /
doc_type_original) so no evidence is lost.
"""
from __future__ import annotations

# canonical -> set of source spellings (lowercased, punctuation-insensitive)
_MAP = {
    "Oil and Gas Lease": {"o/l", "ol", "oil and gas lease", "oil & gas lease", "o&g lease"},
    "Assignment": {"asgt", "asgn", "assignment", "assign"},
    "Partial Assignment": {"pt-asgt", "pt asgt", "partial assignment", "part asgt"},
    "Mineral Deed": {"md", "mineral deed", "min deed"},
    "Quitclaim Deed": {"qcd", "qc", "quitclaim", "quit claim", "quit claim deed"},
    "Ratification": {"ratif", "ratification"},
    "Release": {"rel", "release"},
    "Mortgage": {"mtg", "mort", "mortgage"},
    "Warranty Deed": {"wd", "deed", "warranty deed", "general warranty deed"},
    "Final Decree": {"fd", "final decree"},
    "Affidavit": {"aff", "affidavit"},
    "Right of Way": {"row", "right of way", "r/w"},
    "Correction": {"cor", "correction", "corr"},
    "Memorandum": {"memo", "memorandum"},
    "Court/Probate Order": {"order", "judg", "judgment", "decree", "probate"},
    "Homestead Patent": {"homestead", "patent", "hd"},
}

_LOOKUP = {}
for canon, spellings in _MAP.items():
    for s in spellings:
        _LOOKUP[s] = canon


def _key(s: str) -> str:
    return "".join(ch for ch in s.lower().strip() if ch.isalnum() or ch in "/&- ").strip()


def normalize(source: str | None) -> tuple[str | None, str | None]:
    """Return (canonical_or_None, original). Unknown source -> (None, original)
    so the caller can flag it for review rather than guessing."""
    if not source:
        return None, source
    k = _key(source)
    if k in _LOOKUP:
        return _LOOKUP[k], source
    # try collapsing internal spaces
    k2 = k.replace(" ", "")
    for spelling, canon in _LOOKUP.items():
        if spelling.replace(" ", "") == k2:
            return canon, source
    return None, source
