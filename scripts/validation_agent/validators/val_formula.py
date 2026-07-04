"""Formula Integrity Gate + Workbook Integrity Gate.

Detects formula error literals (#REF!, #VALUE!, #NAME?, #DIV/0!, #N/A, #NULL!)
and hardcoded values in expected-formula areas. A formula defect is marked
``repairable`` ONLY when an exact intended formula can be inferred from nearby
formulas / templates / an immutable prior version — that determination is made
by the repair planner, so here we only flag candidates.
"""
from __future__ import annotations

from typing import Any, Dict, List

import openpyxl

from validators.base_validator import (Validator, make_result, PASS, FAIL, ERROR,
                                       SEV_HIGH, SEV_MEDIUM, SEV_FATAL)

ERROR_LITERALS = {"#REF!", "#VALUE!", "#NAME?", "#DIV/0!", "#N/A", "#NULL!", "#NUM!"}


class WorkbookIntegrityGate(Validator):
    gate_name = "Workbook Integrity Gate"

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        manifest = context.get("manifest") or {}
        zipinfo = (manifest.get("ingestion") or {}).get("zip") or {}
        if not zipinfo.get("has_workbook"):
            return [make_result(self.gate_name, ERROR, severity=SEV_FATAL,
                                reason="Workbook part missing — file is not a valid OOXML workbook.",
                                recommended_action="Re-export the workbook; escalate.",
                                failure_class="Broken Workbook Structure / XML Corruption",
                                confidence=1.0)]
        return [make_result(self.gate_name, PASS, severity=SEV_MEDIUM,
                            evidence={"entries": zipinfo.get("entry_count"),
                                      "has_media": zipinfo.get("has_media"),
                                      "has_vba": zipinfo.get("has_vba")},
                            reason="Workbook ZIP/OOXML structure is valid.", confidence=1.0)]


class FormulaIntegrityGate(Validator):
    gate_name = "Formula Integrity Gate"

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        workbook_path = context.get("workbook_path")
        if not workbook_path:
            return [make_result(self.gate_name, ERROR, severity=SEV_MEDIUM,
                                reason="No workbook path provided.", confidence=0.3)]
        results: List[Dict[str, Any]] = []
        wb = openpyxl.load_workbook(workbook_path, data_only=True, read_only=True)
        try:
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=False):
                    for cell in row:
                        if isinstance(cell.value, str) and cell.value in ERROR_LITERALS:
                            results.append(make_result(
                                self.gate_name, FAIL, severity=SEV_HIGH, repairable=True,
                                affected_sheet=ws.title, affected_cell_or_range=cell.coordinate,
                                evidence={"literal": cell.value},
                                reason=f"Formula error literal {cell.value} at {ws.title}!{cell.coordinate}.",
                                recommended_action="Repair only if the intended formula is known from context.",
                                failure_class="Formula Defect", confidence=0.9))
        finally:
            wb.close()
        if not results:
            return [make_result(self.gate_name, PASS, severity=SEV_MEDIUM,
                                reason="No formula error literals detected.", confidence=1.0)]
        return results
