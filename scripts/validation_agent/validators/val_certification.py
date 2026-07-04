"""Gate 13: Final Certification.

Certification passes only when every other gate passed with no open FAIL or
ESCALATE. This gate aggregates prior results; it never fabricates a pass.
"""

from __future__ import annotations

from typing import Any, Dict, List

from core.enums import GateStatus, Severity
from .base_validator import ValidationResult, ValidatorBase


class FinalCertificationGate(ValidatorBase):
    gate_name = "Final Certification Gate"

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:
        prior: List[ValidationResult] = context.get("prior_results", [])
        fails = [r for r in prior if r.status == GateStatus.FAIL]
        escalations = [r for r in prior if r.status == GateStatus.ESCALATE]

        if fails or escalations:
            return [
                self._failed(
                    severity=Severity.HIGH,
                    reason=(
                        f"Cannot certify: {len(fails)} failing gate(s), "
                        f"{len(escalations)} escalation(s) open."
                    ),
                    evidence=(
                        "fails=" + ", ".join(sorted({r.gate_name for r in fails}))
                        + " | escalations="
                        + ", ".join(sorted({r.gate_name for r in escalations}))
                    ),
                    recommended_action="Resolve all gates before certification.",
                    repairable=False,
                )
            ]
        return [
            self._passed(
                reason="All gates passed. Workbook is eligible for certification.",
                confidence=0.99,
            )
        ]
