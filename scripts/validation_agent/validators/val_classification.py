"""Gate 2: Sheet Classification."""

from __future__ import annotations

from typing import Any, Dict, List

from core.enums import FailureCategory, Severity
from ingestion.sheet_classifier import ClassificationReport
from .base_validator import ValidationResult, ValidatorBase


class SheetClassificationGate(ValidatorBase):
    gate_name = "Sheet Classification Gate"

    @staticmethod
    def _count_tract_entries(context: Dict[str, Any], classification: ClassificationReport) -> int:
        """Count tract data rows across tract-classified sheets (excludes totals)."""
        from ingestion.workbook_ingestor import WorkbookStructure

        structure: WorkbookStructure = context.get("structure")  # type: ignore
        if structure is None:
            return 0
        tract_names = {c.sheet_name for c in classification.by_category("tracts")}
        total = 0
        for sheet in structure.sheets:
            if sheet.name not in tract_names:
                continue
            for row in sheet.rows:
                label = str(row[0]).strip().lower() if row and row[0] is not None else ""
                if not label:
                    continue
                if any(t in label for t in ("total", "grand total", "sum", "footing")):
                    continue
                total += 1
        return total

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:
        classification: ClassificationReport = context["classification"]
        settings = context.get("settings")
        expected_tracts = getattr(settings, "expected_tract_count", 10)
        results: List[ValidationResult] = []

        # Low-confidence sheets escalate (never guess).
        for c in classification.classifications:
            if c.escalate:
                results.append(
                    self._escalate(
                        affected_sheet=c.sheet_name,
                        reason=c.reason,
                        evidence=f"scores={c.scores}",
                        confidence=c.confidence,
                        failure_category=FailureCategory.BROKEN_WORKBOOK_STRUCTURE,
                        recommended_action=(
                            "Human must confirm the classification of this sheet."
                        ),
                    )
                )

        counts = classification.category_counts()
        tract_sheet_count = counts.get("tracts", 0)
        tract_entry_count = self._count_tract_entries(context, classification)

        # Core expectation: 10 tracts identified (rows across tract sheets, or
        # one tract per sheet), OGL register present, WI sheet present.
        identified_tracts = max(tract_entry_count, tract_sheet_count)
        if tract_sheet_count < 1:
            results.append(
                self._escalate(
                    affected_subject="tracts",
                    reason="No tract sheet identified.",
                    evidence=f"counts={counts}",
                    failure_category=FailureCategory.BROKEN_WORKBOOK_STRUCTURE,
                    recommended_action="Confirm a tracts sheet exists.",
                )
            )
        elif identified_tracts != expected_tracts:
            results.append(
                self._failed(
                    severity=Severity.MEDIUM,
                    affected_subject="tracts",
                    reason=(
                        f"Expected {expected_tracts} tracts but identified "
                        f"{identified_tracts}."
                    ),
                    evidence=f"tract_sheets={tract_sheet_count} tract_rows={tract_entry_count}",
                    failure_category=FailureCategory.BROKEN_WORKBOOK_STRUCTURE,
                    recommended_action="Verify tract rows/sheets are complete.",
                    confidence=0.6,
                )
            )
        if counts.get("ogl_register", 0) < 1:
            results.append(
                self._escalate(
                    affected_subject="ogl_register",
                    reason="No OGL register sheet identified.",
                    evidence=f"counts={counts}",
                    failure_category=FailureCategory.OGL_MISMATCH_WI_GAP,
                    recommended_action="Confirm OGL register sheet exists.",
                )
            )
        if counts.get("working_interest", 0) < 1:
            results.append(
                self._escalate(
                    affected_subject="working_interest",
                    reason="No working-interest sheet identified.",
                    evidence=f"counts={counts}",
                    failure_category=FailureCategory.OGL_MISMATCH_WI_GAP,
                    recommended_action="Confirm working-interest sheet exists.",
                )
            )

        if not results:
            results.append(
                self._passed(
                    reason=(
                        f"All sheets classified with confidence; counts={counts}."
                    ),
                    confidence=0.95,
                )
            )
        return results
