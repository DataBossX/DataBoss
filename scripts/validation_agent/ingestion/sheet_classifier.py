"""
Sheet classification with confidence.

Classifies each sheet into one of the known report categories using sheet-name
and header-row keyword scoring plus fuzzy matching. rapidfuzz is used when
available; otherwise difflib provides the fuzzy score (stdlib fallback), so
classification always runs. Low-confidence sheets are flagged for escalation
rather than guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from rapidfuzz import fuzz as _rf

    def _ratio(a: str, b: str) -> float:
        return _rf.partial_ratio(a, b) / 100.0
except Exception:  # pragma: no cover - fallback path
    from difflib import SequenceMatcher

    def _ratio(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()


CATEGORIES = ["tract", "ogl_register", "runsheet", "working_interest", "well",
              "exception_curative", "qa", "sources", "overview", "unknown"]

# keyword → category weights
KEYWORDS: Dict[str, List[str]] = {
    "tract": ["tract"],
    "ogl_register": ["ogl", "oil and gas lease", "lease register", "og l"],
    "runsheet": ["runsheet", "run sheet", "raw", "rawdata", "raw data", "index"],
    "working_interest": ["wi", "working interest", "wi 1", "wi 2", "leasehold"],
    "well": ["well", "wells", "hbp", "api"],
    "exception_curative": ["curative", "exception", "requirement", "fix", "defect"],
    "qa": ["qa", "quality", "check", "foot", "acreage_foot", "audit"],
    "sources": ["source", "ownership summary", "targets", "economics", " orri", "npri", "royalty"],
    "overview": ["overview", "plat", "title", "summary"],
}

LOW_CONFIDENCE = 0.55
CORE_REQUIRED = {"tract": 10, "ogl_register": 1, "working_interest": 1}


@dataclass
class Classification:
    sheet: str
    category: str
    confidence: float
    escalate: bool
    signals: List[str]


def _score_sheet(name: str, header: List[str]) -> Tuple[str, float, List[str]]:
    """
    The sheet NAME is the strongest signal (0.95); header-only keyword hits are
    weaker (0.5) so a stray column like 'Tracts' on the OGL register does not
    misroute the sheet to the 'tract' category. Ties break toward the higher
    name-derived score.
    """
    name_l = name.lower().strip()
    header_hay = " ".join(header or []).lower()
    best_cat, best_score, sig = "unknown", 0.0, []
    for cat, kws in KEYWORDS.items():
        score = 0.0
        local_sig = []
        for kw in kws:
            if kw in name_l:                       # keyword in the sheet name — strong
                score = max(score, 0.95)
                local_sig.append(f"name:{kw}")
                continue
            fr = _ratio(kw, name_l)                # fuzzy name match — medium
            if fr > 0.7:
                score = max(score, fr * 0.85)
                local_sig.append(f"fuzzy:{kw}={fr:.2f}")
            if kw in header_hay:                   # keyword only in headers — weak
                score = max(score, 0.5)
                local_sig.append(f"header:{kw}")
        if score > best_score:
            best_cat, best_score, sig = cat, score, local_sig
    return best_cat, round(best_score, 3), sig


def classify_sheets(manifest_sheets: List[Dict]) -> List[Classification]:
    out: List[Classification] = []
    for s in manifest_sheets:
        name = s.get("name", "")
        header = s.get("header_row", [])
        cat, conf, sig = _score_sheet(name, header)
        out.append(Classification(name, cat, conf, escalate=conf < LOW_CONFIDENCE, signals=sig))
    return out


def core_gate(classifications: List[Classification]) -> Dict[str, object]:
    """Check the core sheet requirements; missing core = fatal escalation."""
    counts: Dict[str, int] = {c: 0 for c in CATEGORIES}
    for c in classifications:
        if not c.escalate:
            counts[c.category] = counts.get(c.category, 0) + 1
    missing = {}
    for cat, need in CORE_REQUIRED.items():
        have = counts.get(cat, 0)
        if have < need:
            missing[cat] = {"need": need, "have": have}
    return {
        "counts": counts,
        "missing_core": missing,
        "fatal": bool(missing),
        "tracts_found": counts.get("tract", 0),
    }
