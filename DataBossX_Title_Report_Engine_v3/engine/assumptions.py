"""Tasks 11 & 12 -- collect assumptions and review flags, and generate notes.

Assumptions are *created* inside the chain engine (that is where the evidence
gap is discovered); this module aggregates them, enforces the labeling contract
(every assumption statement begins with "ASSUMPTION:"), and produces the
consolidated review-flag list. It never manufactures new ownership.
"""

from __future__ import annotations

from typing import List

from .models import Assumption, ReviewFlag, TractResult

ALLOWED_KINDS = {
    "opening_ownership", "tract_allocation", "control_acreage", "heirship_probate",
    "lease_ogl", "acreage_rounding", "title_gap", "missing_release",
    "missing_assignment",
}


def collect_assumptions(results: List[TractResult]) -> List[Assumption]:
    out: List[Assumption] = []
    for res in results:
        for a in res.assumptions:
            if not a.statement.startswith("ASSUMPTION:"):
                a.statement = "ASSUMPTION: " + a.statement
            out.append(a)
    return out


def collect_flags(results: List[TractResult]) -> List[ReviewFlag]:
    out: List[ReviewFlag] = []
    for res in results:
        out.extend(res.flags)
        if res.evidence_score < 75:
            out.append(ReviewFlag(
                tract=res.tract, severity="yellow" if res.evidence_score >= 50 else "red",
                category="evidence_score",
                message=f"Tract {res.tract} evidence score {res.evidence_score} "
                        "-- review required before relying on final ownership.",
                recommended_action="Resolve the flagged gaps and rerun."))
    return out
