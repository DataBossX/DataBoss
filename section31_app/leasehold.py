"""Track leasehold / working-interest ownership by OGL and assignment chain.

Consumes merged 'Leasehold WI Ownership' rows, normalises WI/NRI fractions,
reconstructs the assignment chain into a readable arrow string, and flags rows
whose working interests under a single OGL do not sum to 100%.
"""

from __future__ import annotations

import re
from typing import Dict, List

from .schema import SHEETS
from .ownership import _fraction, _to_float


def _chain_string(value) -> str:
    """Normalise an assignment chain into 'A -> B -> C'."""
    if not value:
        return ""
    parts = re.split(r"\s*(?:->|=>|>|;|\||,|\bto\b|\bthen\b)\s*", str(value))
    parts = [p.strip() for p in parts if p.strip()]
    return " -> ".join(parts)


def normalize_leasehold(rows: List[Dict]) -> List[Dict]:
    cols = SHEETS["Leasehold WI Ownership"]
    out: List[Dict] = []
    for raw in rows:
        rec = {c: raw.get(c, "") for c in cols}
        wi = _fraction(rec.get("working_interest"))
        nri = _fraction(rec.get("net_revenue_interest"))
        if wi:
            rec["working_interest"] = round(wi, 6)
        if nri:
            rec["net_revenue_interest"] = round(nri, 6)
        rec["assignment_chain"] = _chain_string(rec.get("assignment_chain"))
        if not rec.get("source"):
            rec["source"] = "unknown"
        out.append(rec)
    return _flag_wi_gaps(out)


def _flag_wi_gaps(rows: List[Dict]) -> List[Dict]:
    """Warn when WI under one OGL doesn't total ~100%."""
    by_ogl: Dict[str, float] = {}
    for r in rows:
        ogl = str(r.get("ogl_number", "")).strip()
        if ogl:
            by_ogl[ogl] = by_ogl.get(ogl, 0.0) + _to_float(r.get("working_interest"))
    for r in rows:
        ogl = str(r.get("ogl_number", "")).strip()
        if ogl and ogl in by_ogl:
            total = by_ogl[ogl]
            if total and abs(total - 1.0) > 0.02:
                r["remarks"] = (r.get("remarks", "") +
                                f" | WI under {ogl} totals {total:.3f} (!=1.0)").strip(" |")
    return rows


def leasehold_totals(rows: List[Dict]) -> Dict:
    ogls = sorted({str(r.get("ogl_number", "")).strip()
                   for r in rows if r.get("ogl_number")})
    return {"wi_owners": len(rows), "distinct_ogls": len(ogls)}
