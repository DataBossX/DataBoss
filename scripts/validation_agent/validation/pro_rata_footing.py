"""Gate G2 — Pro-Rata Net-Acre Footing.

The per-tract REPORT TOTAL cells live on the Title sheet (one "REPORT TOTAL" row
per tract section, value in column C). This gate:

(a) ties each tract's Title REPORT TOTAL to its acreage (±ACRE_TOL);
(b) ties the global sum of tract acreages to GROSS_ACRES (±ACRE_TOL).
"""
from __future__ import annotations

import re

from .. import config
from ..ingestion.sheet_models import SheetValues
from ..ingestion.workbook_map import WorkbookModel
from ..models import Coord, GateId, Severity, ValidationResult
from .base import Validator

_TRACT_HDR = re.compile(r"TRACT\s*(\d+)\s*:", re.IGNORECASE)


class ProRataFootingValidator(Validator):
    gate = GateId.G2_FOOTING

    def _title_sheet_name(self, model: WorkbookModel) -> str | None:
        for name in model.wb.sheetnames:
            if name.strip().lower() == "title":
                return name
        return None

    def _tract_totals(
        self, model: WorkbookModel, values: SheetValues
    ) -> dict[int, tuple[str, float | None]]:
        """Map tract_no -> (coord_str, report_total_value) from the Title sheet."""
        name = self._title_sheet_name(model)
        out: dict[int, tuple[str, float | None]] = {}
        if not name:
            return out
        ws = model.wb[name]
        current: int | None = None
        for r in range(1, ws.max_row + 1):
            b = ws.cell(r, 2).value
            if isinstance(b, str):
                m = _TRACT_HDR.search(b)
                if m:
                    current = int(m.group(1))
                    continue
                if b.strip().upper() == "REPORT TOTAL" and current is not None:
                    v = values.get(name, "C", r)
                    fv = float(v) if isinstance(v, (int, float)) else None
                    out.setdefault(current, (f"C{r}", fv))
        return out

    def validate(
        self, model: WorkbookModel, values: SheetValues
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        totals = self._tract_totals(model, values)
        title = self._title_sheet_name(model) or "Title "
        acre_sum = 0.0
        for tno in config.TRACT_NUMBERS:
            acre_sum += config.TRACT_ACREAGE[tno]
            entry = totals.get(tno)
            if entry is None or entry[1] is None:
                results.append(
                    ValidationResult(
                        gate=self.gate, passed=False, severity=Severity.FAIL,
                        message=f"Tract {tno}: REPORT TOTAL not found on Title",
                        locations=[Coord(title, "C")],
                    )
                )
                continue
            coord, total = entry
            if abs(total - config.TRACT_ACREAGE[tno]) > config.ACRE_TOL:
                results.append(
                    ValidationResult(
                        gate=self.gate, passed=False, severity=Severity.FAIL,
                        message=(
                            f"Tract {tno}: REPORT TOTAL {total:.4g} != acreage "
                            f"{config.TRACT_ACREAGE[tno]}"
                        ),
                        locations=[Coord(title, coord)],
                        metric=total, expected=config.TRACT_ACREAGE[tno],
                    )
                )
        if abs(acre_sum - config.GROSS_ACRES) > config.ACRE_TOL:
            results.append(
                ValidationResult(
                    gate=self.gate, passed=False, severity=Severity.FAIL,
                    message=(
                        f"Sum of tract acreages {acre_sum:.4g} != gross "
                        f"{config.GROSS_ACRES}"
                    ),
                    metric=acre_sum, expected=config.GROSS_ACRES,
                )
            )
        if not results:
            results.append(
                ValidationResult(
                    gate=self.gate, passed=True, severity=Severity.INFO,
                    message=(
                        f"All 10 tract totals tie to acreage; sum "
                        f"{acre_sum:.2f} == {config.GROSS_ACRES}."
                    ),
                    metric=acre_sum, expected=config.GROSS_ACRES,
                )
            )
        return results
