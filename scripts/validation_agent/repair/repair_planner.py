"""RepairPlanner -- segregate safe automated repairs from human escalations.

Section 4 (Separation of Concerns) and the Golden Law require a hard split:

    * Safe queue  -- exact, machine-verifiable mutations (restore a SUM formula,
      normalize a fraction).  These become :class:`RepairAction` objects.
    * Escalation queue -- anything that would require inventing a legal or title
      fact.  These become fully-populated :class:`Escalation` payloads
      (Section 7's nine mandatory fields).

Repair eligibility is intentionally conservative: if a repair is not an exact
mathematical restoration or a formatting normalization, it is ineligible.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..failure_taxonomy import escalate_language
from ..models import (CellRef, Escalation, FailureCategory, Finding, RepairAction,
                      Severity)
from .failure_classifier import ClassifiedFinding, FailureClassifier

_SUPPORTED_ACTIONS = {"restore_formula", "normalize_fraction"}

_URGENCY = {
    Severity.MEDIUM: "Routine",
    Severity.HIGH: "Elevated",
    Severity.SYSTEM_HIGH: "Elevated",
    Severity.CRITICAL: "Urgent",
    Severity.FATAL: "Immediate",
}

_RECOMMENDED_ACTION = {
    FailureCategory.MISSING_SOURCE:
        "Locate and attach the recorded instrument (Book/Page or Instrument #).",
    FailureCategory.UNVERIFIABLE_SOURCE:
        "Retry source retrieval or obtain the image through an alternate channel.",
    FailureCategory.SOURCE_LEGAL_MISMATCH:
        "Reconcile the source legal description against the workbook; determine "
        "which is authoritative.",
    FailureCategory.TITLE_CHAIN_GAP:
        "Obtain the missing vesting instrument (deed, probate, or affidavit of "
        "heirship) to bridge the gap.",
    FailureCategory.RESERVATION_CARRY_FORWARD_FAILURE:
        "Confirm whether a prior reservation was dropped; restore it in the chain.",
    FailureCategory.OGL_WI_MISMATCH:
        "Reconcile the lease reference / depth clause between register, tract, "
        "and WI sheets.",
    FailureCategory.HBP_UNSUPPORTED:
        "Verify well production status supporting the HBP claim.",
    FailureCategory.API_SPEND_BLOCKED:
        "Approve additional spend budget or obtain the document manually.",
    FailureCategory.SUBPROCESS_DEPENDENCY_FAILURE:
        "Check the curl / LibreOffice dependency and credentials on the host.",
    FailureCategory.UNSAFE_LEGAL_INFERENCE:
        "A human examiner must supply the legal determination; automation halted.",
    FailureCategory.BROKEN_WORKBOOK_STRUCTURE:
        "Restore the workbook from the last good version; the file is corrupt.",
    FailureCategory.COMPUTATIONAL_MISMATCH:
        "Review the underlying figures; the components do not reconcile.",
    FailureCategory.FORMULA_DEFECT:
        "Confirm the restored formula matches the intended calculation.",
}


@dataclass
class RepairPlan:
    safe_repairs: list[RepairAction]
    escalations: list[Escalation]

    @property
    def has_safe_repairs(self) -> bool:
        return bool(self.safe_repairs)

    @property
    def has_escalations(self) -> bool:
        return bool(self.escalations)


class RepairPlanner:
    def __init__(self, classifier: FailureClassifier | None = None) -> None:
        self.classifier = classifier or FailureClassifier()

    def plan(self, findings: list[Finding]) -> RepairPlan:
        classified = self.classifier.classify(findings)
        safe: list[RepairAction] = []
        escalations: list[Escalation] = []
        seen_cells: set[str] = set()
        for cf in classified:
            action = self._to_repair_action(cf)
            if action is not None:
                key = str(action.location)
                if key in seen_cells:
                    continue  # same cell already scheduled (e.g. gates 4 & 10)
                seen_cells.add(key)
                safe.append(action)
            else:
                escalations.append(self._to_escalation(cf))
        return RepairPlan(safe_repairs=safe, escalations=escalations)

    def _to_repair_action(self, cf: ClassifiedFinding):
        if not cf.repairable:
            return None
        hint = cf.finding.repair_hint
        action_type = hint.get("action_type")
        if action_type not in _SUPPORTED_ACTIONS:
            return None
        sheet = hint.get("sheet")
        cell = hint.get("cell")
        if not (sheet and cell):
            return None
        new_formula = hint.get("new_formula") or hint.get("new_value") or ""
        if not new_formula:
            return None
        return RepairAction(
            finding_gate_id=cf.finding.gate_id,
            location=CellRef(sheet=sheet, cell=cell),
            action_type=action_type,
            old_value=(str(hint.get("old_value"))
                       if hint.get("old_value") is not None else None),
            new_formula=new_formula,
            rationale=cf.finding.message,
        )

    def _to_escalation(self, cf: ClassifiedFinding) -> Escalation:
        f = cf.finding
        evidence = f.evidence or {}
        blocked = escalate_language(f.category) or f.message
        return Escalation(
            gate_id=f.gate_id,
            gate_name=f.gate_name,
            category=f.category,
            severity=cf.severity,
            failed_gate=f.gate_name,
            location=f.location,
            subject=f.subject or "(unspecified)",
            sources_checked=list(evidence.get("sources_checked", [])),
            sources_missing=list(evidence.get("sources_missing", [])),
            automated_checks_attempted=list(
                evidence.get("automated_checks_attempted", [f.message])),
            repair_blocked_reason=blocked,
            recommended_examiner_action=_RECOMMENDED_ACTION.get(
                f.category, "Human examiner review required."),
            estimated_urgency=_URGENCY.get(cf.severity, "Elevated"),
        )
