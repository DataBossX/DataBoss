"""Gate 11: Source Verification.

Missing, unverifiable, contradictory, or spend-blocked sources escalate. This
gate reads the source-finder index assembled during the run.
"""

from __future__ import annotations

from typing import Any, Dict, List

from core.enums import FailureCategory, Severity
from .base_validator import ValidationResult, ValidatorBase


class SourceVerificationGate(ValidatorBase):
    gate_name = "Source Verification Gate"

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:
        index = context.get("source_index") or {}
        missing = index.get("missing", [])
        blocked = index.get("blocked", [])
        failed = index.get("failed", [])
        contradictory = index.get("contradictory", [])
        found = index.get("found", [])
        results: List[ValidationResult] = []

        for ref in missing:
            results.append(
                self._escalate(
                    affected_subject=str(ref.get("reference_key", ref)),
                    reason="Required source document is missing.",
                    evidence=str(ref),
                    failure_category=FailureCategory.MISSING_SOURCE,
                    recommended_action="Locate/obtain the missing source document.",
                    confidence=0.9,
                )
            )
        for ref in blocked:
            results.append(
                self._escalate(
                    affected_subject=str(ref.get("reference_key", ref)),
                    reason="Source retrieval blocked by spend cap or policy.",
                    evidence=str(ref),
                    failure_category=FailureCategory.API_SPEND_BLOCKED,
                    recommended_action="Examiner must authorize spend or provide doc.",
                    confidence=0.95,
                )
            )
        for ref in failed:
            results.append(
                self._escalate(
                    affected_subject=str(ref.get("reference_key", ref)),
                    reason="Source retrieval failed (auth/access).",
                    evidence=str(ref),
                    failure_category=FailureCategory.API_AUTH_FAILURE,
                    recommended_action="Resolve credentials/access, then re-run.",
                    confidence=0.9,
                )
            )
        for ref in contradictory:
            results.append(
                self._escalate(
                    affected_subject=str(ref.get("reference_key", ref)),
                    reason="Source contradicts the workbook's stated facts.",
                    evidence=str(ref),
                    failure_category=FailureCategory.SOURCE_LEGAL_MISMATCH,
                    recommended_action="Examiner must resolve source/legal mismatch.",
                    confidence=0.9,
                )
            )

        if not results:
            results.append(
                self._passed(
                    affected_subject="sources",
                    reason=f"Source references verified ({len(found)} found).",
                    confidence=0.85,
                )
            )
        return results
