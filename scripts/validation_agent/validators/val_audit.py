"""Audit Completeness Gate + Final Certification Gate.

Audit Completeness confirms the run has left the required append-only proof.
Final Certification passes ONLY when every other gate passed with zero
escalations — otherwise it routes to ESCALATE. Certification is never granted
while any legal/source/HBP item is open.
"""
from __future__ import annotations

from typing import Any, Dict, List

from validators.base_validator import (Validator, make_result, PASS, ESCALATE, FAIL,
                                       SEV_HIGH, SEV_MEDIUM)


class AuditCompletenessGate(Validator):
    gate_name = "Audit Completeness Gate"

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        counts = context.get("audit_counts") or {}
        needed = ["runs", "workbook_versions", "validation_results", "audit_events"]
        missing = [t for t in needed if counts.get(t, 0) < 1]
        if missing:
            return [make_result(self.gate_name, FAIL, severity=SEV_HIGH,
                                reason=f"Append-only proof missing rows in: {', '.join(missing)}",
                                recommended_action="Ensure all stages log to the DB.",
                                failure_class="Unsafe Legal Inference", confidence=0.9)]
        return [make_result(self.gate_name, PASS, severity=SEV_MEDIUM,
                            evidence=counts, reason="Append-only audit trail present for the run.",
                            confidence=1.0)]


class FinalCertificationGate(Validator):
    gate_name = "Final Certification Gate"

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        prior = context.get("gate_results", [])
        fails = [r for r in prior if r["status"] == "FAIL"]
        escalations = [r for r in prior if r["status"] == "ESCALATE"]
        errors = [r for r in prior if r["status"] == "ERROR"]
        if fails or escalations or errors:
            return [make_result(self.gate_name, ESCALATE, severity=SEV_HIGH,
                evidence={"fails": len(fails), "escalations": len(escalations),
                          "errors": len(errors)},
                reason="Certification withheld: unresolved gate failures/escalations remain.",
                recommended_action="Route to examiner; deliver escalation packet.",
                failure_class="Unsafe Legal Inference", confidence=1.0)]
        return [make_result(self.gate_name, PASS, severity=SEV_HIGH,
                            reason="All gates passed with no escalations — eligible for certification.",
                            confidence=1.0)]
