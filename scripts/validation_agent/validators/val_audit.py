"""Workbook Integrity, Sheet Classification, Audit Completeness, and Final
Certification gates.

These are the structural bookend gates of the pipeline. The Final Certification
Gate only PASSes when every other gate has passed and nothing is escalated.
"""

from __future__ import annotations

from typing import Any

from .base_validator import (
    BaseValidator, ValidationResult, PASS, FAIL, ESCALATE, ERROR,
    SEVERITY_CRITICAL, SEVERITY_HIGH,
)
from ingestion.sheet_classifier import CORE_CATEGORIES


class WorkbookIntegrityValidator(BaseValidator):
    gate_name = "Workbook Integrity Gate"

    def run(self, context: dict) -> list[ValidationResult]:
        manifest = context.get("manifest")
        if manifest is None:
            return [self._error(
                severity=SEVERITY_CRITICAL, affected_subject="workbook",
                reason="No manifest available; ingestion failed.",
                recommended_action="Re-ingest workbook.",
            )]
        zip_valid = manifest.get("zip_valid") if isinstance(manifest, dict) \
            else manifest.zip_valid
        if not zip_valid:
            return [self._fail(
                severity=SEVERITY_CRITICAL, repairable=False,
                affected_subject="workbook",
                reason="Workbook ZIP/XML structure is invalid or corrupt.",
                recommended_action="Escalate: structural corruption; do not "
                                   "certify.",
                confidence=0.95,
            )]
        return [self._pass(
            affected_subject="workbook",
            reason="Workbook ZIP/XML structure is valid.",
        )]


class SheetClassificationValidator(BaseValidator):
    gate_name = "Sheet Classification Gate"

    def run(self, context: dict) -> list[ValidationResult]:
        classification = context.get("classification")
        if not classification:
            return [self._error(
                severity=SEVERITY_HIGH, affected_subject="sheets",
                reason="No classification available.",
                recommended_action="Re-run sheet classifier.",
            )]
        missing_core = classification.get("missing_core") or []
        if missing_core:
            return [self._escalate(
                severity=SEVERITY_CRITICAL, repairable=False,
                affected_subject="sheets",
                evidence={"missing_core": missing_core},
                reason=f"Missing core sheet(s): {', '.join(missing_core)}. "
                       f"Core sheets are required "
                       f"({', '.join(sorted(CORE_CATEGORIES))}).",
                recommended_action="Fatal escalation: examiner must supply the "
                                   "missing core sheet(s).",
                confidence=0.95,
            )]
        low = classification.get("low_confidence") or []
        if low:
            return [self._escalate(
                severity=SEVERITY_HIGH, affected_subject="sheets",
                evidence={"low_confidence": low},
                reason=f"{len(low)} sheet(s) classified with low confidence.",
                recommended_action="Examiner should confirm sheet roles.",
                confidence=0.7,
            )]
        return [self._pass(
            affected_subject="sheets",
            reason="All core sheets identified with confidence.",
        )]


class AuditCompletenessValidator(BaseValidator):
    gate_name = "Audit Completeness Gate"

    def run(self, context: dict) -> list[ValidationResult]:
        recorded = context.get("recorded_gate_count", 0)
        expected = context.get("expected_gate_count", 0)
        if expected and recorded < expected:
            return [self._escalate(
                affected_subject="audit trail",
                reason=f"Only {recorded}/{expected} gate results recorded.",
                recommended_action="Re-run pipeline; audit trail incomplete.",
                confidence=0.9,
            )]
        return [self._pass(
            affected_subject="audit trail",
            reason="All gate results recorded to the append-only audit trail.",
        )]


class FinalCertificationValidator(BaseValidator):
    gate_name = "Final Certification Gate"

    def run(self, context: dict) -> list[ValidationResult]:
        prior = context.get("all_results") or []
        blocking = [
            r for r in prior
            if r.get("status") in {FAIL, ESCALATE, ERROR}
            and r.get("gate_name") != self.gate_name
        ]
        if blocking:
            return [self._escalate(
                severity=SEVERITY_HIGH, affected_subject="certification",
                evidence={"blocking_gates": [b.get("gate_name") for b in blocking]},
                reason=f"{len(blocking)} gate(s) not passing; certification "
                       f"withheld.",
                recommended_action="Resolve blocking gates or escalate to "
                                   "examiner. Certification is never forced.",
                confidence=1.0,
            )]
        return [self._pass(
            affected_subject="certification",
            reason="All gates passed. Workbook is eligible for certification.",
        )]
