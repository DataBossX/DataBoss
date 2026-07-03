"""Repair planner.

Takes triaged validation results and produces a plan of SAFE repairs only.
Formula defects with a known intended formula become concrete cell edits.
Everything unsafe is routed to escalation, never to the repair plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .failure_classifier import classify, FORMULA_DEFECT


@dataclass
class RepairAction:
    kind: str            # "set_formula"
    sheet: str
    cell: str
    formula: str
    before_value: str
    evidence: dict = field(default_factory=dict)


@dataclass
class RepairPlan:
    actions: list[RepairAction] = field(default_factory=list)
    escalations: list[dict] = field(default_factory=list)

    @property
    def has_repairs(self) -> bool:
        return bool(self.actions)


def build_plan(results: list[dict]) -> RepairPlan:
    plan = RepairPlan()
    for r in results:
        if r.get("status") == "PASS":
            continue
        triage = classify(r)
        if triage.repairable and triage.category == FORMULA_DEFECT:
            ev = r.get("evidence") or {}
            intended = ev.get("intended_formula")
            cell = r.get("affected_cell_or_range") or ev.get("cell")
            sheet = r.get("affected_sheet")
            if intended and cell and sheet:
                plan.actions.append(RepairAction(
                    kind="set_formula", sheet=sheet, cell=cell,
                    formula=intended,
                    before_value=str(ev.get("hardcoded_value", "")),
                    evidence=ev,
                ))
                continue
        # Not repairable (or missing evidence) -> escalate.
        plan.escalations.append({
            "gate_name": r.get("gate_name"),
            "category": triage.category,
            "subject": r.get("affected_subject"),
            "reason": r.get("reason"),
            "recommended_action": r.get("recommended_action"),
            "rationale": triage.rationale,
            "evidence": r.get("evidence"),
        })
    return plan
