"""Gate 1: Workbook Integrity."""

from __future__ import annotations

from typing import Any, Dict, List

from core.enums import FailureCategory, GateStatus, Severity
from ingestion.workbook_ingestor import WorkbookStructure
from .base_validator import ValidationResult, ValidatorBase


class WorkbookIntegrityGate(ValidatorBase):
    gate_name = "Workbook Integrity Gate"

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:
        structure: WorkbookStructure = context["structure"]
        results: List[ValidationResult] = []

        if not structure.zip_valid:
            return [
                self._failed(
                    severity=Severity.FATAL,
                    reason="Workbook ZIP structure is invalid or corrupt.",
                    evidence=f"path={structure.path}",
                    failure_category=FailureCategory.BROKEN_WORKBOOK_STRUCTURE,
                    recommended_action="Re-export the workbook; inspect for corruption.",
                    repairable=False,
                )
            ]

        if not structure.sheets:
            return [
                self._failed(
                    severity=Severity.FATAL,
                    reason="Workbook contains no readable sheets.",
                    failure_category=FailureCategory.BROKEN_WORKBOOK_STRUCTURE,
                    recommended_action="Verify the source workbook is complete.",
                    repairable=False,
                )
            ]

        # Presence of required OOXML parts.
        required_parts = ["[Content_Types].xml", "xl/workbook.xml"]
        missing_parts = [p for p in required_parts if p not in structure.zip_entries]
        if missing_parts:
            results.append(
                self._failed(
                    severity=Severity.FATAL,
                    reason="Workbook is missing required OOXML parts.",
                    evidence=f"missing={missing_parts}",
                    failure_category=FailureCategory.BROKEN_WORKBOOK_STRUCTURE,
                    recommended_action="Repackage/repair the workbook structure.",
                    repairable=False,
                )
            )

        if structure.is_xlsm and not structure.has_vba:
            results.append(
                ValidationResult(
                    gate_name=self.gate_name,
                    status=GateStatus.PASS,
                    severity=Severity.LOW,
                    reason="XLSM extension without a VBA project (informational).",
                    confidence=0.9,
                )
            )

        if not results:
            results.append(
                self._passed(
                    reason=(
                        f"Valid workbook: {len(structure.sheets)} sheets, "
                        f"vba={structure.has_vba}, drawings={structure.has_drawings}, "
                        f"media={structure.has_media}."
                    ),
                    evidence=f"sha256={structure.sha256}",
                )
            )
        return results
