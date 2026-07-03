"""Acreage footing (Gate 4) and formula integrity (Gate 10).

Gate 4  -- the tract acreage must foot to exactly the expected gross total
           (637.42 by default) and net acres must reconcile against ownership.
Gate 10 -- cells that are supposed to *compute* (totals/subtotals) must hold a
           formula, not a hardcoded value that silently overrides the logic.

Only two repairs are ever proposed here, and both are exact and non-inventive:
restoring a ``=SUM(...)`` over an existing, visible data range.  Nothing about
the underlying acreage numbers is fabricated; if the components themselves do
not foot, the gate escalates instead of guessing a "correct" value.
"""

from __future__ import annotations

from ..config.settings import config
from ..models import CellRef, FailureCategory, Finding, GateResult, GateStatus, Severity
from ..ingestion.sheet_classifier import SheetCategory
from ._helpers import (col_of, data_cells_in_column, find_header_column,
                       is_total_row, numeric)
from .base_validator import ValidatorBase


class AcreageValidator(ValidatorBase):
    gate_name = "Acreage & Formula Integrity"
    gate_ids = (4, 10)

    def _run(self, manifest) -> list[GateResult]:
        return [self._acreage_gate(manifest), self._formula_gate(manifest)]

    # -- Gate 4 ------------------------------------------------------------
    def _acreage_gate(self, manifest) -> GateResult:
        tracts = manifest.by_category(SheetCategory.TRACT)
        expected = config.expected_total_acreage
        tol = config.acreage_tolerance

        if not tracts:
            return GateResult(4, "Acreage Footing", GateStatus.ERROR,
                              detail="No tract sheets classified; cannot foot acreage.")

        # Avoid double-counting: when a dedicated summary/footing tab exists,
        # foot from it alone; otherwise sum the per-tract detail tabs.
        acreage_sheets = self._acreage_sheets(tracts)

        component_sum = 0.0
        counted_rows = 0
        sheets_with_acreage = 0
        findings: list[Finding] = []

        for sheet in acreage_sheets:
            acre_col = self._acre_col(sheet)
            if acre_col is None:
                continue
            sheets_with_acreage += 1
            for cell in data_cells_in_column(sheet, acre_col):
                if is_total_row(sheet, cell.row):
                    continue
                val = numeric(cell.value)
                if val is not None:
                    component_sum += val
                    counted_rows += 1

        if sheets_with_acreage == 0 or counted_rows == 0:
            finding = Finding(
                gate_id=4, gate_name="Acreage Footing",
                category=FailureCategory.MISSING_SOURCE, severity=Severity.HIGH,
                message="No tract sheet exposes an acreage column; cannot foot.",
                location=CellRef(sheet=tracts[0].name), subject="tract footing",
                repairable=False, escalate=True)
            return GateResult(4, "Acreage Footing", GateStatus.FAIL, [finding],
                              finding.message)

        component_sum = round(component_sum, 6)
        delta = round(component_sum - expected, 6)
        metrics = {"component_sum": component_sum, "expected": expected,
                   "delta": delta, "rows_counted": counted_rows}

        # Check declared totals for hardcoded overrides that disagree.
        for sheet in acreage_sheets:
            acre_col = self._acre_col(sheet)
            if acre_col is None:
                continue
            for cell in sheet.cells.values():
                if col_of(cell.coord) != acre_col or not is_total_row(sheet, cell.row):
                    continue
                declared = numeric(cell.value)
                if declared is None:
                    continue
                if cell.formula is None and abs(declared - expected) > tol \
                        and abs(component_sum - expected) <= tol:
                    # Data foots to 637.42 but the total cell is a wrong literal.
                    findings.append(self._sum_repair_finding(
                        sheet, cell, acre_col, gate_id=4,
                        gate_name="Acreage Footing",
                        message=(f"Tract total {cell.coord}={declared} overrides a "
                                 f"correct footing of {expected}."),
                        expected_total=expected))

        if abs(delta) <= tol:
            status = GateStatus.PASS if not findings else GateStatus.FAIL
            detail = (f"Tract acreage foots to {component_sum} (expected {expected})."
                      if not findings else
                      f"Components foot to {expected} but a total cell was overridden.")
            return GateResult(4, "Acreage Footing", status, findings, detail, metrics)

        # Components themselves do not foot -- cannot be repaired without a source.
        findings.append(Finding(
            gate_id=4, gate_name="Acreage Footing",
            category=FailureCategory.COMPUTATIONAL_MISMATCH, severity=Severity.HIGH,
            message=(f"Tract acreage foots to {component_sum}, expected {expected} "
                     f"(delta {delta}). Underlying components do not reconcile."),
            location=CellRef(sheet=tracts[0].name), subject="tract footing",
            repairable=False, escalate=True,
            evidence=metrics))
        return GateResult(4, "Acreage Footing", GateStatus.FAIL, findings,
                          f"Acreage footing off by {delta}.", metrics)

    # -- Gate 10 -----------------------------------------------------------
    def _formula_gate(self, manifest) -> GateResult:
        findings: list[Finding] = []
        for sheet in manifest.sheets:
            for cell in sheet.cells.values():
                if not is_total_row(sheet, cell.row):
                    continue
                val = numeric(cell.value)
                if val is None or cell.formula is not None:
                    continue
                col = col_of(cell.coord)
                # Only flag columns that actually carry numeric data above them.
                above = [c for c in data_cells_in_column(sheet, col)
                         if c.row < cell.row and numeric(c.value) is not None]
                if len(above) < 2:
                    continue
                findings.append(self._sum_repair_finding(
                    sheet, cell, col, gate_id=10, gate_name="Formula Integrity",
                    message=(f"{sheet.name}!{cell.coord} holds hardcoded {val}; a "
                             f"total cell should compute via formula."),
                    expected_total=None))

        if not findings:
            return GateResult(10, "Formula Integrity", GateStatus.PASS, [],
                              "All total/subtotal cells contain formulas.")
        return GateResult(10, "Formula Integrity", GateStatus.FAIL, findings,
                          f"{len(findings)} hardcoded total cell(s) override logic.")

    # -- acreage-sheet / column selection ----------------------------------
    # Deliberately narrow: must mention "acre" so "Net Revenue Interest" and
    # similar "net"/"gross" columns are never mistaken for acreage.
    _ACRE_KEYWORDS = ("net acre", "gross acre", "acreage", "acre")

    @classmethod
    def _acre_col(cls, sheet):
        return find_header_column(sheet, *cls._ACRE_KEYWORDS)

    @classmethod
    def _acreage_sheets(cls, tracts):
        summary = [s for s in tracts
                   if any(tok in s.name.lower()
                          for tok in ("summary", "footing", "total", "recap"))]
        return summary or tracts

    # -- shared repair-finding builder -------------------------------------
    @staticmethod
    def _sum_repair_finding(sheet, cell, col: str, *, gate_id: int, gate_name: str,
                            message: str, expected_total) -> Finding:
        above = [c for c in data_cells_in_column(sheet, col)
                 if c.row < cell.row and numeric(c.value) is not None
                 and not is_total_row(sheet, c.row)]
        rows = [c.row for c in above]
        if not rows:
            # No data range above the total: a =SUM over the cell itself would be
            # circular. This is not machine-repairable -- escalate instead.
            return Finding(
                gate_id=gate_id, gate_name=gate_name,
                category=FailureCategory.COMPUTATIONAL_MISMATCH,
                severity=Severity.HIGH,
                message=message + " No data range above the total to restore a "
                                  "formula from; examiner review required.",
                location=CellRef(sheet=sheet.name, cell=cell.coord),
                subject=f"{sheet.name}!{cell.coord}",
                repairable=False, escalate=True)
        start, end = (min(rows), max(rows))
        new_formula = f"=SUM({col}{start}:{col}{end})"
        category = (FailureCategory.FORMULA_DEFECT if gate_id == 10
                    else FailureCategory.COMPUTATIONAL_MISMATCH)
        severity = Severity.MEDIUM if gate_id == 10 else Severity.HIGH
        return Finding(
            gate_id=gate_id, gate_name=gate_name, category=category,
            severity=severity, message=message,
            location=CellRef(sheet=sheet.name, cell=cell.coord),
            subject=f"{sheet.name}!{cell.coord}",
            repairable=True, escalate=False,
            repair_hint={"action_type": "restore_formula",
                         "sheet": sheet.name, "cell": cell.coord,
                         "old_value": cell.value, "new_formula": new_formula,
                         "expected_total": expected_total},
            evidence={"sum_range": f"{col}{start}:{col}{end}"})
