"""Extract parties (grantor/grantee, lessor/lessee, assignor/assignee),
recording / execution / effective dates, instrument numbers and book/page.

All heuristic and conservative: when a value can't be found it is left empty so
the caller can substitute an explicit sentinel rather than a guess.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from ..utils import clean_ws, short_date

# ---- instrument number & book/page ---------------------------------------
_INSTR = re.compile(
    r"(?:instrument|inst\.?|doc(?:ument)?|reception|file)\s*(?:no\.?|#|number)?\s*[:#]?\s*"
    r"([0-9][0-9\-]{4,})",
    re.IGNORECASE,
)
_BOOKPAGE = re.compile(
    r"book\s*(?:no\.?)?\s*([0-9A-Za-z]+)\s*[,/]?\s*page\s*([0-9A-Za-z]+)",
    re.IGNORECASE,
)

# ---- dates ---------------------------------------------------------------
_DATE = r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Z][a-z]+\s+\d{1,2},\s*\d{4})"
_REC_DATE = re.compile(rf"(?:recorded|recording\s+date|filed)\D{{0,20}}{_DATE}", re.IGNORECASE)
_EXE_DATE = re.compile(rf"(?:dated|executed|made\s+(?:and\s+entered\s+)?this)\D{{0,30}}{_DATE}", re.IGNORECASE)
_EFF_DATE = re.compile(rf"(?:effective\s+(?:date|as\s+of)?)\D{{0,20}}{_DATE}", re.IGNORECASE)
_ANY_DATE = re.compile(_DATE)

# ---- parties -------------------------------------------------------------
# party clause up to a connective keyword
_PARTY_BLOCK = r"(?P<a>.+?)\s*,?\s*(?:hereinafter|hereafter|\(|whose\s+address|of\s+the\s+county)"

_ROLE_PAIRS = [
    # (left role, right role, regex linking them)
    ("grantor", "grantee",
     re.compile(r"between\s+(?P<a>.+?)\s*,?\s*(?:hereinafter|\(|whose|as\s+grantor).*?"
                r"and\s+(?P<b>.+?)\s*,?\s*(?:hereinafter|\(|whose|as\s+grantee)",
                re.IGNORECASE | re.DOTALL)),
    ("lessor", "lessee",
     re.compile(r"between\s+(?P<a>.+?)\s*,?\s*(?:hereinafter|\(|lessor).*?"
                r"and\s+(?P<b>.+?)\s*,?\s*(?:hereinafter|\(|lessee)",
                re.IGNORECASE | re.DOTALL)),
    ("assignor", "assignee",
     # Require the literal role words so document-title text isn't captured.
     re.compile(r"(?P<a>[^\n,]{3,80}?)\s*,?\s*(?:as\s+)?assignor\b.*?"
                r"(?:to|unto|and)\s+(?P<b>[^\n,]{3,80}?)\s*,?\s*(?:as\s+)?assignee\b",
                re.IGNORECASE | re.DOTALL)),
]

_LABELLED = {
    "grantor": re.compile(r"grantor[s]?\s*[:\-]\s*(.+)", re.IGNORECASE),
    "grantee": re.compile(r"grantee[s]?\s*[:\-]\s*(.+)", re.IGNORECASE),
    "lessor": re.compile(r"lessor[s]?\s*[:\-]\s*(.+)", re.IGNORECASE),
    "lessee": re.compile(r"lessee[s]?\s*[:\-]\s*(.+)", re.IGNORECASE),
    "assignor": re.compile(r"assignor[s]?\s*[:\-]\s*(.+)", re.IGNORECASE),
    "assignee": re.compile(r"assignee[s]?\s*[:\-]\s*(.+)", re.IGNORECASE),
}


# Document-title / boilerplate words that signal a captured non-name span.
_NOISE = re.compile(
    r"\b(deed|lease|mortgage|agreement|assignment|affidavit|conveyance|"
    r"warranty|quitclaim|release|memorandum)\b", re.IGNORECASE)


def _tidy_party(raw: str) -> str:
    s = clean_ws((raw or "").replace("\n", " "))
    s = re.sub(r"\s*\b(a\s+single\s+person|husband\s+and\s+wife|et\s+ux\.?|"
               r"a\s+married\s+(man|woman)|individually).*$", "", s, flags=re.IGNORECASE)
    s = s.strip(" ,.;:-()")
    # Reject obvious non-names: document-title noise or over-long spans.
    if not s or len(s) > 70 or _NOISE.search(s):
        return ""
    return s


def extract_parties(text: str) -> Dict[str, List[str]]:
    t = text or ""
    result: Dict[str, List[str]] = {
        "grantor": [], "grantee": [], "lessor": [],
        "lessee": [], "assignor": [], "assignee": [],
    }

    for left, right, rx in _ROLE_PAIRS:
        m = rx.search(t)
        if m:
            a = _tidy_party(m.group("a"))
            b = _tidy_party(m.group("b"))
            if a and not result[left]:
                result[left].append(a)
            if b and not result[right]:
                result[right].append(b)

    # Labelled fallbacks ("Grantor: John Doe").
    for role, rx in _LABELLED.items():
        if result[role]:
            continue
        m = rx.search(t)
        if m:
            val = _tidy_party(m.group(1).splitlines()[0])
            if val:
                result[role].append(val)

    return {k: v for k, v in result.items() if v}


def extract_dates(text: str) -> Dict[str, str]:
    t = text or ""
    out: Dict[str, str] = {}
    rm = _REC_DATE.search(t)
    if rm:
        out["recording_date"] = short_date(rm.group(1))
    em = _EXE_DATE.search(t)
    if em:
        out["execution_date"] = short_date(em.group(1))
    fm = _EFF_DATE.search(t)
    if fm:
        out["effective_date"] = short_date(fm.group(1))
    return out


def extract_recording_data(text: str) -> Dict[str, str]:
    t = text or ""
    out: Dict[str, str] = {}
    im = _INSTR.search(t)
    if im:
        out["instrument_no"] = im.group(1).strip()
    bm = _BOOKPAGE.search(t)
    if bm:
        out["book_page"] = f"{bm.group(1)}/{bm.group(2)}"
    return out
