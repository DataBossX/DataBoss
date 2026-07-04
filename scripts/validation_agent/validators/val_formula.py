"""Gate 10: Formula Integrity.

Cells that are hardcoded numeric literals inside a column that is otherwise
formula-driven are formula defects. They are repairable ONLY when the exact
formula for that region can be derived safely (i.e. the surrounding cells share
an unambiguous formula pattern). Otherwise the finding is reported but not
marked repairable.
"""

from __future__ import annotations

from typing import Any, Dict, List

from core.enums import FailureCategory, Severity
from ingestion.workbook_ingestor import SheetView
from .base_validator import ValidationResult, ValidatorBase


def _column_formula_pattern(sheet: SheetView, column: int) -> str | None:
    """Return a shared relative-formula pattern for a column, if unambiguous.

    We compare formulas cell-by-cell after stripping the row number; if every
    formula in the column normalizes to the same template, the pattern is safe.
    """
    import re

    templates = set()
    for fc in sheet.formula_cells:
        if fc.column != column or not fc.formula:
            continue
        template = re.sub(r"(\$?[A-Z]{1,3})\$?\d+", r"\1<row>", fc.formula)
        templates.add(template)
    if len(templates) == 1:
        return templates.pop()
    return None


class FormulaIntegrityGate(ValidatorBase):
    gate_name = "Formula Integrity Gate"

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:
        structure = context["structure"]
        results: List[ValidationResult] = []
        total_hardcoded = 0

        for sheet in structure.sheets:
            for cell in sheet.hardcoded_in_formula_regions:
                total_hardcoded += 1
                pattern = _column_formula_pattern(sheet, cell.column)
                repairable = pattern is not None
                results.append(
                    self._failed(
                        severity=Severity.MEDIUM if repairable else Severity.HIGH,
                        repairable=repairable,
                        affected_sheet=sheet.name,
                        affected_cell_or_range=cell.coordinate,
                        affected_subject="formula region",
                        reason=(
                            "Hardcoded value in an otherwise formula-driven column."
                        ),
                        evidence=(
                            f"value={cell.value} "
                            f"derivable_pattern={pattern!r}"
                        ),
                        failure_category=FailureCategory.FORMULA_DEFECT,
                        recommended_action=(
                            "Restore column formula (exact pattern derivable)."
                            if repairable
                            else "Examiner review: formula pattern is ambiguous."
                        ),
                        confidence=0.85 if repairable else 0.6,
                    )
                )

        if not results:
            results.append(
                self._passed(
                    reason="No hardcoded values detected in formula regions.",
                    confidence=0.9,
                )
            )
        return results
