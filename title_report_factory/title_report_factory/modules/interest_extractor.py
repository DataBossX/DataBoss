"""interest_extractor -- parse royalty fractions, acreage, and interest type."""
from __future__ import annotations

import re
from fractions import Fraction


def parse_royalty(value) -> str:
    """Return a normalized royalty string (e.g. '3/16' or '0.1875')."""
    if value is None or value == "":
        return ""
    s = str(value).strip()
    m = re.search(r"(\d+)\s*/\s*(\d+)", s)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    try:
        f = float(s)
        if 0 < f < 1:
            return s
    except ValueError:
        pass
    return s


def royalty_decimal(value) -> float | None:
    s = parse_royalty(value)
    if not s:
        return None
    m = re.match(r"(\d+)\s*/\s*(\d+)$", s)
    if m:
        return float(Fraction(int(m.group(1)), int(m.group(2))))
    try:
        return float(s)
    except ValueError:
        return None


def parse_acres(value) -> str:
    if value is None or value == "":
        return ""
    s = str(value).strip()
    m = re.search(r"[\d,]+(?:\.\d+)?", s)
    return m.group(0).replace(",", "") if m else s


def interest_type(doc_class: str, text: str = "") -> str:
    """Best-effort classification of the interest touched by an instrument."""
    t = f"{doc_class} {text}".lower()
    if "wellbore" in t:
        return "Working interest (wellbore-limited)"
    if "override" in t or "orri" in t:
        return "Overriding royalty interest"
    if "lease" in t or "ogl" in t:
        return "Leasehold (working interest)"
    if "mineral" in t:
        return "Mineral interest"
    if "royalty" in t:
        return "Royalty interest"
    if "assignment" in t or "conveyance" in t:
        return "Leasehold/interest (scope per schedule)"
    if "merger" in t:
        return "Corporate succession (entity-level)"
    return "Needs Review"
