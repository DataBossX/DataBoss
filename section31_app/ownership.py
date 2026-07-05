"""Track title (mineral) ownership.

Consumes merged 'Tract & Title Ownership' rows and normalises them: cleans
numeric net-acre / royalty fields, derives net mineral acres from
interest x gross acres where one side is missing, classifies lease status, and
tags a confidence based on how many controlling fields are present.
"""

from __future__ import annotations

import re
from typing import Dict, List

from .schema import SHEETS

_LEASED = re.compile(r"lease|hbp|held|producing|active", re.I)
_OPEN = re.compile(r"open|unleased|expired|available", re.I)


def _to_float(value) -> float:
    if value in (None, ""):
        return 0.0
    s = str(value).replace(",", "").replace("$", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return 0.0
    num = float(m.group(0))
    if "%" in s and num > 1:
        num /= 100.0
    return num


def _fraction(value) -> float:
    """Parse '1/8', '0.125', '12.5%' into a decimal fraction."""
    if value in (None, ""):
        return 0.0
    s = str(value).strip()
    if "/" in s:
        try:
            num, den = s.split("/", 1)
            return float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            return 0.0
    return _to_float(s)


def _classify_status(row: Dict) -> str:
    text = " ".join(str(row.get(k, "")) for k in ("lease_status", "lessee", "remarks"))
    if _LEASED.search(text):
        return "Leased"
    if _OPEN.search(text):
        return "Open"
    if row.get("lessee"):
        return "Leased"
    return row.get("lease_status") or "Unknown"


def normalize_ownership(rows: List[Dict]) -> List[Dict]:
    cols = SHEETS["Tract & Title Ownership"]
    out: List[Dict] = []
    for raw in rows:
        rec = {c: raw.get(c, "") for c in cols}
        gross = _to_float(rec.get("gross_acres"))
        nma = _to_float(rec.get("net_mineral_acres"))
        interest = _fraction(rec.get("mineral_interest"))
        # Derive the missing leg of nma = interest * gross when possible.
        if not nma and gross and interest:
            nma = round(gross * interest, 4)
            rec["net_mineral_acres"] = nma
            rec["remarks"] = (rec.get("remarks", "") +
                              " | NMA derived = interest x gross").strip(" |")
        elif not interest and gross and nma:
            rec["mineral_interest"] = round(nma / gross, 6) if gross else ""
        rec["lease_status"] = _classify_status(rec)

        present = sum(1 for k in ("owner_name", "legal_description",
                                  "net_mineral_acres", "mineral_interest")
                      if rec.get(k))
        rec["confidence"] = {4: "high", 3: "medium", 2: "low"}.get(present, "very low")
        if not rec.get("source"):
            rec["source"] = "unknown"
        out.append(rec)
    return out


def ownership_totals(rows: List[Dict]) -> Dict[str, float]:
    """Roll-up totals used by QA and the cover sheet."""
    total_nma = sum(_to_float(r.get("net_mineral_acres")) for r in rows)
    leased = sum(1 for r in rows if r.get("lease_status") == "Leased")
    return {
        "owners": len(rows),
        "total_net_mineral_acres": round(total_nma, 2),
        "leased_tracts": leased,
        "open_tracts": sum(1 for r in rows if r.get("lease_status") == "Open"),
    }
