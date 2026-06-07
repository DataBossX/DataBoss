"""Classify an instrument from its text.

Heuristic, keyword/score based -- transparent and deterministic. Returns a
document type plus a 0-100 confidence so downstream code knows how much to
trust it. When the LLM is enabled, the heuristic result is offered as a prior.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Ordered most-specific first. Each entry: (label, [regex patterns], weight).
_RULES: List[Tuple[str, List[str], int]] = [
    ("Oil & Gas Lease", [r"oil\s+and\s+gas\s+lease", r"oil\s*&\s*gas\s+lease",
                          r"\blessor\b.*\blessee\b", r"paid[- ]up\s+lease"], 3),
    ("Assignment of Oil & Gas Lease",
        [r"assignment\s+of\s+(oil|leases?)", r"\bassignor\b.*\bassignee\b",
         r"assignment\s+and\s+bill\s+of\s+sale"], 3),
    ("Mineral Deed", [r"mineral\s+deed", r"conveys?.*minerals?",
                      r"oil,?\s*gas\s+and\s+other\s+minerals"], 3),
    ("Royalty Deed", [r"royalty\s+deed", r"royalty\s+conveyance"], 3),
    ("Warranty Deed", [r"warranty\s+deed", r"do(es)?\s+hereby\s+grant.*warrant"], 2),
    ("Quitclaim Deed", [r"quit[- ]?claim\s+deed", r"quitclaim"], 3),
    ("Mortgage / Deed of Trust",
        [r"\bmortgage\b", r"deed\s+of\s+trust", r"security\s+instrument"], 2),
    ("Release", [r"release\s+of\s+(mortgage|lease|oil)", r"\brelease\b"], 2),
    ("Affidavit", [r"affidavit", r"being\s+first\s+duly\s+sworn"], 2),
    ("Probate / Estate Document",
        [r"\bprobate\b", r"last\s+will\s+and\s+testament", r"letters\s+testamentary",
         r"order\s+admitting", r"final\s+decree"], 2),
    ("Pooling / Unitization Order",
        [r"pooling", r"unitization", r"spacing\s+order", r"corporation\s+commission"], 2),
    ("Easement / Right of Way",
        [r"easement", r"right[- ]of[- ]way"], 2),
    ("Power of Attorney", [r"power\s+of\s+attorney"], 2),
    ("Memorandum of Lease", [r"memorandum\s+of\s+(oil|lease)"], 2),
]


def classify(text: str) -> Tuple[str, float, Dict[str, int]]:
    """Return (document_type, confidence_0_100, score_breakdown)."""
    t = (text or "").lower()
    if not t.strip():
        return "Unknown", 0.0, {}

    scores: Dict[str, int] = {}
    for label, patterns, weight in _RULES:
        hits = sum(1 for p in patterns if re.search(p, t))
        if hits:
            scores[label] = scores.get(label, 0) + hits * weight

    if not scores:
        return "Unknown", 10.0, {}

    best = max(scores, key=scores.get)
    top = scores[best]
    runner_up = sorted(scores.values(), reverse=True)
    second = runner_up[1] if len(runner_up) > 1 else 0

    # Confidence grows with absolute evidence and separation from the runner-up.
    margin = top - second
    confidence = min(95.0, 45.0 + top * 8.0 + margin * 6.0)
    if top <= 1:
        confidence = min(confidence, 55.0)  # single weak signal -> needs review
    return best, round(confidence, 1), scores
