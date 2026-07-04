"""Gate 3: Interest Conservation.

For every conveyance row: GrantorInterest - Conveyed + Retained must equal 0,
computed with exact Fraction arithmetic so there are no floating-point false
positives. Over-conveyance (Conveyed > Grantor) and under-conveyance
(Conveyed + Retained < Grantor) are detected exactly.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Dict, List

from core.enums import FailureCategory, Severity
from .base_validator import ValidationResult, ValidatorBase
from .util import column_index, find_sheets_by_category, non_empty, parse_fraction

_GRANTOR_ALIASES = ("grantor interest", "grantor int", "grantor", "starting interest",
                    "vested interest")
_CONVEYED_ALIASES = ("conveyed", "conveyed interest", "interest conveyed", "granted")
_RETAINED_ALIASES = ("retained", "retained interest", "reserved", "reservation")
_SUBJECT_ALIASES = ("grantor", "party", "grantor name", "subject", "instrument")


class InterestConservationGate(ValidatorBase):
    gate_name = "Interest Conservation Gate"

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:
        sheets = find_sheets_by_category(context, "runsheet")
        sheets += find_sheets_by_category(context, "working_interest")
        results: List[ValidationResult] = []
        rows_checked = 0

        for sheet in sheets:
            g_col = column_index(sheet.headers, *_GRANTOR_ALIASES)
            c_col = column_index(sheet.headers, *_CONVEYED_ALIASES)
            r_col = column_index(sheet.headers, *_RETAINED_ALIASES)
            s_col = column_index(sheet.headers, *_SUBJECT_ALIASES)
            if g_col is None or c_col is None:
                continue
            header_offset = sheet.header_row_index or 0
            for r_idx, row in enumerate(sheet.rows):
                grantor = parse_fraction(row[g_col]) if g_col < len(row) else None
                conveyed = parse_fraction(row[c_col]) if c_col < len(row) else None
                if grantor is None and conveyed is None:
                    continue
                retained = (
                    parse_fraction(row[r_col])
                    if (r_col is not None and r_col < len(row) and non_empty(row[r_col]))
                    else Fraction(0)
                )
                if grantor is None or conveyed is None:
                    continue
                rows_checked += 1
                excel_row = header_offset + 1 + r_idx
                subject = (
                    str(row[s_col]).strip()
                    if (s_col is not None and s_col < len(row) and non_empty(row[s_col]))
                    else f"{sheet.name} row {excel_row}"
                )
                balance = grantor - conveyed - (retained or Fraction(0))

                if conveyed > grantor:
                    results.append(
                        self._escalate(
                            severity=Severity.HIGH,
                            affected_sheet=sheet.name,
                            affected_cell_or_range=f"row {excel_row}",
                            affected_subject=subject,
                            reason=(
                                "Over-conveyance: conveyed interest exceeds grantor's "
                                "vested interest."
                            ),
                            evidence=(
                                f"grantor={grantor} conveyed={conveyed} "
                                f"retained={retained}"
                            ),
                            failure_category=FailureCategory.UNSAFE_LEGAL_INFERENCE,
                            recommended_action=(
                                "Examiner must resolve over-conveyance against source "
                                "instruments; do not auto-adjust interests."
                            ),
                            confidence=0.97,
                        )
                    )
                elif balance != 0:
                    kind = "Under-conveyance" if balance > 0 else "Interest imbalance"
                    results.append(
                        self._failed(
                            severity=Severity.HIGH,
                            repairable=False,
                            affected_sheet=sheet.name,
                            affected_cell_or_range=f"row {excel_row}",
                            affected_subject=subject,
                            reason=(
                                f"{kind}: grantor - conveyed + retained != 0 "
                                f"(residual {balance})."
                            ),
                            evidence=(
                                f"grantor={grantor} conveyed={conveyed} "
                                f"retained={retained} residual={balance}"
                            ),
                            failure_category=FailureCategory.RESERVATION_CARRY_FORWARD_FAILURE,
                            recommended_action=(
                                "Verify retained/reserved interest against the "
                                "instrument; examiner review required."
                            ),
                            confidence=0.95,
                        )
                    )

        if rows_checked == 0:
            return [
                self._escalate(
                    affected_subject="interest",
                    reason="No grantor/conveyed interest rows found to validate.",
                    failure_category=FailureCategory.MISSING_SOURCE,
                    recommended_action="Confirm runsheet/WI interest columns exist.",
                )
            ]
        if not results:
            results.append(
                self._passed(
                    affected_subject="interest",
                    reason=f"Interest conserved across {rows_checked} row(s).",
                    confidence=0.98,
                )
            )
        return results
