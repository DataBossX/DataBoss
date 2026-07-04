"""
Well/HBP Support Gate + Audit Completeness Gate + Final Certification Gate.

* Well/HBP: production/HBP support carried "per recital" or unconfirmed always
  escalates — HBP is never machine-certified.
* Audit Completeness: verifies the run recorded audit events and validation
  results (proof-of-work).
* Final Certification: PASS only if every prior gate passed and nothing is
  escalated; otherwise the run must escalate.
"""
from __future__ import annotations

from typing import List

from .base_validator import BaseValidator, ValidationResult, PASS, FAIL, ESCALATE, SEV_MED, SEV_HIGH
from .wb_access import scan_for_markers

HBP_UNSUPPORTED = ["per recital", "not confirmed", "not independently confirmed",
                   "hbp per recital", "held-by-production status not confirmed",
                   "production, spacing, and held-by-production", "not verified"]


class WellHbpValidator(BaseValidator):
    gate_name = "Well / HBP Support Gate"

    def run(self) -> List[ValidationResult]:
        if not self.workbook_path:
            return [self._result(ESCALATE, severity=SEV_MED, reason="No workbook path provided")]
        hits = scan_for_markers(self.workbook_path, HBP_UNSUPPORTED)
        if not hits:
            # Absence of a disclaimer is NOT proof of HBP; still require examiner sign-off.
            return [self._result(ESCALATE, severity=SEV_MED, repairable=False,
                reason="HBP support not machine-verifiable; examiner must confirm production/OCC well file",
                recommended_action="Obtain OCC Form 1002A + production; never auto-certify HBP")]
        return [self._result(ESCALATE, severity=SEV_HIGH, repairable=False,
            affected_sheet=hits[0]["sheet"], affected_cell_or_range=hits[0]["cell"],
            evidence={"sample": hits[0]["text"]},
            reason="HBP carried per lease recital / not confirmed of record",
            recommended_action="Human examiner: confirm HBP via OCC well file + production; do not auto-repair",
            confidence=0.95)]


class AuditCompletenessValidator(BaseValidator):
    gate_name = "Audit Completeness Gate"

    def run(self) -> List[ValidationResult]:
        ev = int(self.config.get("audit_event_count", 0))
        vr = int(self.config.get("validation_result_count", 0))
        if ev > 0 and vr > 0:
            return [self._result(PASS, severity=SEV_MED,
                evidence={"audit_events": ev, "validation_results": vr},
                reason="Run has append-only audit + validation records")]
        return [self._result(FAIL, severity=SEV_MED, repairable=False,
            evidence={"audit_events": ev, "validation_results": vr},
            reason="Insufficient audit trail recorded",
            recommended_action="Ensure orchestrator logs every step")]


class FinalCertificationValidator(BaseValidator):
    gate_name = "Final Certification Gate"

    def run(self) -> List[ValidationResult]:
        prior: List[ValidationResult] = self.config.get("prior_results", [])
        fails = [r for r in prior if r.status == FAIL]
        escalations = [r for r in prior if r.status == ESCALATE]
        errors = [r for r in prior if r.status == ERROR_STATUS]
        if not fails and not escalations and not errors:
            return [self._result(PASS, severity=SEV_HIGH,
                reason="All gates passed — workbook eligible for certification")]
        return [self._result(ESCALATE, severity=SEV_HIGH, repairable=False,
            evidence={"fails": len(fails), "escalations": len(escalations), "errors": len(errors)},
            reason="Cannot certify: open failures/escalations remain",
            recommended_action="Route to human escalation matrix; deliver escalation packet")]


ERROR_STATUS = "ERROR"
