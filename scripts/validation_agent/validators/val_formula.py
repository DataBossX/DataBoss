"""
Workbook Integrity Gate + Formula Integrity Gate.

Integrity: the manifest must show a valid OOXML ZIP.
Formula integrity: total rows that are hard-coded numbers where the intended
formula is knowable (e.g. a SUM over the tract's owner rows) are flagged as
REPAIRABLE formula defects. Anything whose intended formula is NOT known stays
non-repairable.
"""
from __future__ import annotations

from typing import List

import openpyxl

from .base_validator import BaseValidator, ValidationResult, PASS, FAIL, ERROR, SEV_LOW, SEV_MED, SEV_HIGH
from .wb_access import read_tract_blocks


class WorkbookIntegrityValidator(BaseValidator):
    gate_name = "Workbook Integrity Gate"

    def run(self) -> List[ValidationResult]:
        m = self.manifest or {}
        if not m:
            return [self._result(ERROR, severity=SEV_HIGH, reason="No manifest available")]
        if not m.get("zip_valid"):
            return [self._result(FAIL, severity=SEV_HIGH, repairable=False,
                reason="Workbook failed ZIP/OOXML integrity",
                recommended_action="Escalate — structural corruption")]
        return [self._result(PASS, severity=SEV_LOW,
            evidence={"sheets": len(m.get("sheet_names", [])),
                      "has_media": m.get("has_media"), "has_drawings": m.get("has_drawings")},
            reason="Workbook is a valid OOXML package")]


class FormulaValidator(BaseValidator):
    gate_name = "Formula Integrity Gate"

    def run(self) -> List[ValidationResult]:
        if not self.workbook_path:
            return [self._result(PASS, severity=SEV_LOW, reason="No workbook path; skipped")]
        results: List[ValidationResult] = []
        blocks = read_tract_blocks(self.workbook_path)
        repairable = 0
        for b in blocks:
            # A tract total that is a literal number is a candidate formula defect,
            # because the intended formula (SUM of the owner rows) is knowable.
            if b["total_is_formula"] is False:
                repairable += 1
                results.append(self._result(FAIL, severity=SEV_MED, repairable=True,
                    affected_subject=b["label"],
                    evidence={"owner_rows": b["owner_rows"], "owner_nma_sum": str(b["owner_nma_sum"])},
                    reason="Tract total is a hard-coded value where a SUM formula is expected",
                    recommended_action="Auto-repair: replace with SUM over owner rows (intended formula known)",
                    confidence=0.85))
        if not results:
            results.append(self._result(PASS, severity=SEV_LOW,
                evidence={"tracts": len(blocks)},
                reason="Tract totals are formulas (or no tract totals present)"))
        return results
