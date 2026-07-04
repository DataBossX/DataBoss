"""Classify workbook sheets into domain roles using names, headers and fuzzy
keyword matching. Low-confidence classifications are marked for escalation
rather than guessed.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from rapidfuzz import fuzz

CATEGORIES = {
    "tract": ["tract", "n/2", "s/2", "ne/4", "nw/4", "se/4", "sw/4", "aliquot", "net acres", "mineral owner"],
    "ogl": ["ogl", "oil and gas lease", "lease register", "lessor", "lessee", "royalty", "primary term"],
    "runsheet": ["runsheet", "run sheet", "instrument", "grantor", "grantee", "book", "page", "recorded"],
    "working_interest": ["working interest", "wi ", "wi1", "wi 1", "wi 2", "nri", "assignment", "wellbore"],
    "well": ["well", "api", "spud", "completion", "hbp", "formation", "spacing"],
    "exception": ["exception", "curative", "title issue", "open item", "requirement", "gap"],
    "qa": ["qa", "quality", "audit", "check", "scorecard", "validation"],
    "sources": ["source", "index", "rawdata", "raw data", "document", "citation"],
}

CONFIDENCE_ESCALATE_BELOW = 0.55


def _score(text: str, keywords: List[str]) -> float:
    text_l = text.lower()
    best = 0.0
    for kw in keywords:
        if kw in text_l:
            best = max(best, 1.0)
        else:
            best = max(best, fuzz.partial_ratio(kw, text_l) / 100.0)
    return best


def classify_sheet(name: str, headers: List[str]) -> Dict[str, Any]:
    blob = " ".join([name] + [str(h) for h in headers])
    scores = {cat: _score(blob, kws) for cat, kws in CATEGORIES.items()}
    best_cat = max(scores, key=scores.get)
    best_score = scores[best_cat]
    category = best_cat if best_score >= 0.5 else "unknown"
    return {
        "sheet": name,
        "category": category,
        "confidence": round(best_score, 3),
        "all_scores": {k: round(v, 3) for k, v in scores.items()},
        "needs_escalation": best_score < CONFIDENCE_ESCALATE_BELOW,
    }


TRACT_NUM_RE = re.compile(r"tract\s*0*([0-9]{1,2})", re.IGNORECASE)


def classify_workbook(sheets: List[Dict[str, Any]]) -> Dict[str, Any]:
    classified = [classify_sheet(s["name"], s.get("sample_headers", [])) for s in sheets]

    tract_numbers = set()
    for s in sheets:
        m = TRACT_NUM_RE.search(s["name"])
        if m:
            tract_numbers.add(int(m.group(1)))

    by_cat: Dict[str, List[str]] = {}
    for c in classified:
        by_cat.setdefault(c["category"], []).append(c["sheet"])

    core = {
        "tracts_found": sorted(tract_numbers),
        "tract_count": len(tract_numbers),
        "has_ogl": "ogl" in by_cat,
        "has_working_interest": "working_interest" in by_cat,
        "has_well": "well" in by_cat,
    }
    missing_core: List[str] = []
    if core["tract_count"] < 10:
        missing_core.append(f"expected 10 tracts, found {core['tract_count']}")
    if not core["has_ogl"]:
        missing_core.append("no OGL register sheet identified")
    if not core["has_working_interest"]:
        missing_core.append("no working-interest sheet identified")

    return {
        "sheets": classified,
        "by_category": by_cat,
        "core": core,
        "missing_core": missing_core,
        "fatal": len(missing_core) > 0,
    }
