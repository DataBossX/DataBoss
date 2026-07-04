"""Gate 12: Audit Completeness.

A missing audit trail is fatal. Verifies the run has recorded its run row,
workbook version(s), and audit events in the append-only DB.
"""

from __future__ import annotations

from typing import Any, Dict, List

from core.enums import FailureCategory, Severity
from .base_validator import ValidationResult, ValidatorBase


class AuditCompletenessGate(ValidatorBase):
    gate_name = "Audit Completeness Gate"

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:
        db = context.get("db")
        run_id = context.get("run_id")
        if db is None or run_id is None:
            return [
                self._failed(
                    severity=Severity.FATAL,
                    reason="Audit database/run context unavailable; cannot verify trail.",
                    failure_category=FailureCategory.BROKEN_WORKBOOK_STRUCTURE,
                    recommended_action="Ensure the run is initialized with an audit DB.",
                    repairable=False,
                )
            ]

        runs = db.scalar("SELECT COUNT(*) FROM runs WHERE run_id = ?", (run_id,))
        versions = db.scalar(
            "SELECT COUNT(*) FROM workbook_versions WHERE run_id = ?", (run_id,)
        )
        events = db.scalar(
            "SELECT COUNT(*) FROM audit_events WHERE run_id = ?", (run_id,)
        )

        problems = []
        if not runs:
            problems.append("no run record")
        if not versions:
            problems.append("no workbook version recorded")
        if not events:
            problems.append("no audit events recorded")

        if problems:
            return [
                self._failed(
                    severity=Severity.FATAL,
                    reason="Audit trail incomplete: " + "; ".join(problems),
                    evidence=f"runs={runs} versions={versions} events={events}",
                    failure_category=FailureCategory.BROKEN_WORKBOOK_STRUCTURE,
                    recommended_action="Investigate audit logging failure before certifying.",
                    repairable=False,
                )
            ]
        return [
            self._passed(
                reason=(
                    f"Audit trail present: runs={runs}, versions={versions}, "
                    f"events={events}."
                ),
                confidence=0.95,
            )
        ]
