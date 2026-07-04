"""Gate 4: Acreage Footing.

Tract acreage must foot to the expected total (default 637.42, config
overridable). All math uses Decimal — never float comparison. A hardcoded
total that disagrees with the summed tracts is an overridden total and is a
safe, repairable formula defect. A genuine acreage discrepancy is a
computational mismatch.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from openpyxl.utils import get_column_letter

from core.enums import FailureCategory, Severity
from ingestion.workbook_ingestor import SheetView
from .base_validator import ValidationResult, ValidatorBase
from .util import column_index, find_sheets_by_category, parse_decimal

_ACREAGE_TOLERANCE = Decimal("0.01")
_ACREAGE_ALIASES = ("net acres", "gross acres", "acreage", "acres", "net acreage",
                    "gross acreage", "tract acres")
_TOTAL_ALIASES = ("total", "total acres", "grand total", "sum", "footing")


class AcreageFootingGate(ValidatorBase):
    gate_name = "Acreage Footing Gate"

    def _collect(
        self, sheets: List[SheetView]
    ) -> Tuple[Decimal, int, List[str], Optional[Decimal], Optional[str], Optional[str]]:
        running = Decimal("0")
        counted = 0
        cells: List[str] = []
        declared_total: Optional[Decimal] = None
        total_cell: Optional[str] = None
        total_sheet: Optional[str] = None
        for sheet in sheets:
            col = column_index(sheet.headers, *_ACREAGE_ALIASES)
            if col is None:
                continue
            header_offset = (sheet.header_row_index or 0)
            for r_idx, row in enumerate(sheet.rows):
                if col >= len(row):
                    continue
                # detect an explicit total row via first-column label
                label = str(row[0]).strip().lower() if row and row[0] is not None else ""
                val = parse_decimal(row[col])
                excel_row = header_offset + 1 + r_idx
                coord = f"{get_column_letter(col + 1)}{excel_row}"
                if any(t in label for t in _TOTAL_ALIASES):
                    if val is not None:
                        declared_total = val
                        total_cell = coord
                        total_sheet = sheet.name
                    continue
                if val is not None:
                    running += val
                    counted += 1
                    cells.append(coord)
        return running, counted, cells, declared_total, total_cell, total_sheet

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:
        sheets = find_sheets_by_category(context, "tracts")
        settings = context.get("settings")
        expected: Decimal = getattr(settings, "expected_acreage_total", Decimal("637.42"))
        expected = Decimal(str(expected))

        if not sheets:
            return [
                self._escalate(
                    affected_subject="tracts",
                    reason="No tract sheets available for acreage footing.",
                    failure_category=FailureCategory.MISSING_SOURCE,
                    recommended_action="Confirm tract sheets exist and are classified.",
                )
            ]

        summed, counted, cells, declared_total, total_cell, total_sheet = self._collect(sheets)
        results: List[ValidationResult] = []

        if counted == 0:
            return [
                self._escalate(
                    affected_subject="tracts",
                    reason="No acreage values found in tract sheets.",
                    failure_category=FailureCategory.MISSING_SOURCE,
                    recommended_action="Verify the acreage column exists and is populated.",
                )
            ]

        # Overridden/hardcoded total detection.
        if declared_total is not None and abs(declared_total - summed) > _ACREAGE_TOLERANCE:
            results.append(
                self._failed(
                    severity=Severity.MEDIUM,
                    repairable=True,
                    affected_sheet=total_sheet,
                    affected_cell_or_range=total_cell,
                    affected_subject="acreage total",
                    reason=(
                        "Declared acreage total is a hardcoded override that "
                        "disagrees with the summed tracts."
                    ),
                    evidence=f"declared={declared_total} summed={summed}",
                    failure_category=FailureCategory.FORMULA_DEFECT,
                    recommended_action=(
                        "Restore SUM formula for the total cell (exact formula derivable)."
                    ),
                    confidence=0.9,
                )
            )

        # Footing vs expected total.
        diff = abs(summed - expected)
        if diff > _ACREAGE_TOLERANCE:
            results.append(
                self._failed(
                    severity=Severity.HIGH,
                    repairable=False,
                    affected_subject="acreage footing",
                    reason=(
                        f"Tract acreage sums to {summed} but expected {expected} "
                        f"(delta {summed - expected})."
                    ),
                    evidence=f"cells={cells[:20]}",
                    failure_category=FailureCategory.COMPUTATIONAL_MISMATCH,
                    recommended_action=(
                        "Reconcile individual tract acreages against source legal "
                        "descriptions; examiner review required if unreconcilable."
                    ),
                    confidence=0.95,
                )
            )

        if not results:
            results.append(
                self._passed(
                    affected_subject="acreage footing",
                    reason=f"Tract acreage foots to {summed} (expected {expected}).",
                    evidence=f"tracts_counted={counted}",
                    confidence=0.98,
                )
            )
        return results
