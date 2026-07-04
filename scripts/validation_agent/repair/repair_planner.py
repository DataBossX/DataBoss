"""Repair planner.

Turns SAFE, repairable validation results into concrete, evidence-backed XML
edit plans. A formula defect is only planned when an exact intended formula can
be established (from an adjacent-cell pattern, a template, or an immutable prior
version). If the intended formula is unknown, the item is escalated instead.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from repair.failure_classifier import classify


class RepairPlan:
    def __init__(self, sheet: str, cell: str, new_formula: str, evidence: str,
                 failure_class: str):
        self.sheet = sheet
        self.cell = cell
        self.new_formula = new_formula
        self.evidence = evidence
        self.failure_class = failure_class

    def as_dict(self) -> Dict[str, Any]:
        return {"sheet": self.sheet, "cell": self.cell, "new_formula": self.new_formula,
                "evidence": self.evidence, "failure_class": self.failure_class}


def plan_repairs(results: List[Dict[str, Any]],
                 known_formulas: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Return {plans: [...], escalate: [...]}.

    ``known_formulas`` maps "Sheet!Cell" -> exact intended formula string, sourced
    from adjacent cells / template / prior immutable version. Only cells present
    here are planned for repair; everything else escalates.
    """
    known_formulas = known_formulas or {}
    plans: List[Dict[str, Any]] = []
    escalate: List[Dict[str, Any]] = []
    for r in results:
        route = classify(r)
        if route["route"] != "repair":
            escalate.append(r)
            continue
        key = f"{r.get('affected_sheet')}!{r.get('affected_cell_or_range')}"
        intended = known_formulas.get(key)
        if not intended:
            # Cannot prove the intended formula -> do not guess; escalate.
            escalate.append(dict(r, reason=r.get("reason", "") +
                                 " | intended formula unknown -> escalated (no guess)."))
            continue
        plans.append(RepairPlan(
            sheet=r["affected_sheet"], cell=r["affected_cell_or_range"],
            new_formula=intended,
            evidence=f"intended formula established from known context for {key}",
            failure_class=route["failure_class"]).as_dict())
    return {"plans": plans, "escalate": escalate}
