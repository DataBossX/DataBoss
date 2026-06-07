"""Extract conveyed/reserved interest, lease economics, acreage and royalty.

These are notoriously easy to get wrong, so every value is returned verbatim
from the text where possible, and the caller labels derived numbers as
"apparent/best-effort" rather than verified.
"""
from __future__ import annotations

import re
from typing import Dict

from ..utils import clean_ws

_FRACTION = r"(\d+(?:\.\d+)?\s*/\s*\d+|\d+(?:\.\d+)?%|\d+(?:\.\d+)?\s*percent)"

_ROYALTY = re.compile(rf"(?:royalty|deliver(?:ed)?\s+to\s+the\s+credit)\D{{0,40}}{_FRACTION}", re.IGNORECASE)
_RESERVE = re.compile(rf"reserv\w+\D{{0,60}}{_FRACTION}", re.IGNORECASE)
_CONVEY = re.compile(rf"(?:convey|grant|assign)\w*\D{{0,60}}{_FRACTION}", re.IGNORECASE)
_ACRES = re.compile(r"(\d{1,4}(?:\.\d+)?)\s*acres?", re.IGNORECASE)
_PRIMARY = re.compile(r"primary\s+term\D{0,20}(\d{1,2})\s*(years?|yrs?)", re.IGNORECASE)
_DELAY = re.compile(r"(?:delay\s+rental|bonus)\D{0,30}(\$?\d[\d,]*(?:\.\d+)?)", re.IGNORECASE)


def extract_interest(text: str, document_type: str = "") -> Dict[str, str]:
    t = text or ""
    out: Dict[str, str] = {}

    reserve = _RESERVE.search(t)
    convey = _CONVEY.search(t)
    parts = []
    if convey:
        parts.append(f"Conveys {clean_ws(convey.group(1))}")
    if reserve:
        parts.append(f"Reserves {clean_ws(reserve.group(1))}")
    if parts:
        out["interest"] = "; ".join(parts)

    roy = _ROYALTY.search(t)
    if roy:
        out["royalty"] = clean_ws(roy.group(1))

    acres = _ACRES.search(t)
    if acres:
        out["gross_acres"] = clean_ws(acres.group(1))

    lease_bits = []
    pterm = _PRIMARY.search(t)
    if pterm:
        lease_bits.append(f"Primary term {pterm.group(1)} {pterm.group(2)}")
    delay = _DELAY.search(t)
    if delay:
        lease_bits.append(f"Bonus/rental {delay.group(1)}")
    if lease_bits:
        out["lease_terms"] = "; ".join(lease_bits)

    return out
