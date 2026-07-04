"""
Repair planner.

Turns SAFE_REPAIR triage items into concrete, auditable repair actions. Only
formula defects with a known intended formula are planned. Legal/title/source
items produce escalation entries instead. Nothing here mutates a workbook — it
only plans; xml_editor performs the safe edit on a copied version.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .failure_classifier import Triage, Routing, FailureType


@dataclass
class RepairAction:
    kind: str                     # "formula_sum" etc.
    gate_name: str
    subject: str
    description: str
    params: Dict[str, Any] = field(default_factory=dict)
    safe: bool = True


@dataclass
class RepairPlan:
    actions: List[RepairAction] = field(default_factory=list)
    escalations: List[Triage] = field(default_factory=list)
    blocked: List[Triage] = field(default_factory=list)

    @property
    def has_safe_repairs(self) -> bool:
        return bool(self.actions)


def build_plan(triages: List[Triage], results) -> RepairPlan:
    plan = RepairPlan()
    # index results by (gate, subject) for param extraction
    by_key = {}
    for r in results:
        by_key[(getattr(r, "gate_name", ""), getattr(r, "affected_subject", ""))] = r

    for t in triages:
        if t.routing == Routing.BLOCKED:
            plan.blocked.append(t)
            continue
        if t.routing == Routing.ESCALATE:
            plan.escalations.append(t)
            continue
        # SAFE_REPAIR
        if t.failure_type == FailureType.FORMULA_DEFECT:
            subject = t.subject
            plan.actions.append(RepairAction(
                kind="formula_sum",
                gate_name=t.gate_name,
                subject=subject,
                description=f"Replace hard-coded total in {subject} with SUM over its owner rows",
                params={"subject": subject},
                safe=True,
            ))
        else:
            # Computational mismatches are NOT silently repaired — escalate.
            plan.escalations.append(t)
    return plan
