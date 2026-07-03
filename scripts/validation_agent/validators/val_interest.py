"""Interest conservation (Gate 3).

For every conveyance row on a runsheet, ownership must be conserved:

        grantor_interest - conveyed - retained == 0     (exact rational math)

All arithmetic runs through :class:`fractions.Fraction`, so a value stored as
``0.125`` and one stored as ``1/8`` reconcile exactly and there are no
floating-point false positives.

Repair policy (Golden Law #3/#4):
    * Pure *representational* drift (a decimal that rounds to the exact
      fraction the other two columns imply) is repairable via fraction
      normalization -- no legal fact changes.
    * A genuine over/under-conveyance, or a blank/implied reservation, is NOT
      repairable: inventing the missing interest would fabricate a fact, so the
      gate escalates.
"""

from __future__ import annotations

from fractions import Fraction

from ..config.settings import config
from ..models import CellRef, FailureCategory, Finding, GateResult, GateStatus, Severity
from ..ingestion.sheet_classifier import SheetCategory
from ._helpers import (data_cells_in_column, find_header_column,
                       is_total_row, parse_fraction)
from .base_validator import ValidatorBase


class InterestValidator(ValidatorBase):
    gate_name = "Interest Conservation"
    gate_ids = (3,)

    def _run(self, manifest) -> list[GateResult]:
        runsheets = manifest.by_category(SheetCategory.RUNSHEET)
        if not runsheets:
            return [GateResult(3, "Interest Conservation", GateStatus.ERROR,
                               detail="No runsheet classified; cannot test interest.")]

        findings: list[Finding] = []
        rows_checked = 0

        for sheet in runsheets:
            g_col = find_header_column(sheet, "grantor interest", "grantor int",
                                       "grantor")
            c_col = find_header_column(sheet, "conveyed", "conveyance", "granted")
            r_col = find_header_column(sheet, "retained", "reserved", "reservation")
            if not (g_col and c_col):
                findings.append(Finding(
                    gate_id=3, gate_name="Interest Conservation",
                    category=FailureCategory.MISSING_SOURCE, severity=Severity.HIGH,
                    message=(f"Runsheet '{sheet.name}' lacks grantor/conveyed "
                             f"columns; interest math cannot be evaluated."),
                    location=CellRef(sheet=sheet.name), subject=sheet.name,
                    repairable=False, escalate=True))
                continue

            for g_cell in data_cells_in_column(sheet, g_col):
                row = g_cell.row
                if is_total_row(sheet, row):
                    continue
                if g_cell.value is None:
                    continue
                rows_checked += 1
                g = parse_fraction(g_cell.value)
                c = parse_fraction(self._value_at(sheet, c_col, row))
                r_raw = self._value_at(sheet, r_col, row) if r_col else None
                r = parse_fraction(r_raw) if r_raw is not None else Fraction(0)

                if g is None or c is None:
                    findings.append(self._escalate(
                        sheet, row, g_col,
                        FailureCategory.MISSING_SOURCE,
                        f"Row {row}: interest value is missing or unparseable."))
                    continue

                residual = g - c - (r if r is not None else Fraction(0))
                if residual == 0:
                    continue

                # Blank reservation that would exactly absorb the residual: an
                # unrecorded reservation -- cannot be invented.
                if (r_raw is None or str(r_raw).strip() == "") and residual > 0:
                    findings.append(Finding(
                        gate_id=3, gate_name="Interest Conservation",
                        category=FailureCategory.RESERVATION_CARRY_FORWARD_FAILURE,
                        severity=Severity.HIGH,
                        message=(f"Row {row}: grantor {g} exceeds conveyed {c} with "
                                 f"no recorded reservation ({residual} unaccounted)."),
                        location=CellRef(sheet=sheet.name,
                                         cell=f"{g_col}{row}"),
                        subject=f"{sheet.name} row {row}",
                        repairable=False, escalate=True,
                        evidence={"residual": str(residual)}))
                    continue

                float_residual = abs(float(residual))
                if float_residual <= config.interest_tolerance:
                    # Representational drift only: normalize to the exact fraction.
                    exact = c + (r if r is not None else Fraction(0))
                    findings.append(Finding(
                        gate_id=3, gate_name="Interest Conservation",
                        category=FailureCategory.COMPUTATIONAL_MISMATCH,
                        severity=Severity.HIGH,
                        message=(f"Row {row}: grantor interest is a rounded decimal; "
                                 f"normalize to exact fraction {exact}."),
                        location=CellRef(sheet=sheet.name, cell=f"{g_col}{row}"),
                        subject=f"{sheet.name} row {row}",
                        repairable=True, escalate=False,
                        repair_hint={"action_type": "normalize_fraction",
                                     "sheet": sheet.name, "cell": f"{g_col}{row}",
                                     "old_value": g_cell.value,
                                     "new_value": f"{exact.numerator}/{exact.denominator}"},
                        evidence={"residual": str(residual)}))
                    continue

                # Genuine over/under-conveyance.
                direction = "over-conveyance" if residual < 0 else "under-conveyance"
                findings.append(Finding(
                    gate_id=3, gate_name="Interest Conservation",
                    category=FailureCategory.COMPUTATIONAL_MISMATCH,
                    severity=Severity.HIGH,
                    message=(f"Row {row}: {direction} of {abs(residual)} "
                             f"(grantor {g} vs conveyed {c} + retained "
                             f"{r if r is not None else 0})."),
                    location=CellRef(sheet=sheet.name, cell=f"{g_col}{row}"),
                    subject=f"{sheet.name} row {row}",
                    repairable=False, escalate=True,
                    evidence={"residual": str(residual)}))

        status = GateStatus.PASS if not findings else GateStatus.FAIL
        detail = (f"Interest conserved across {rows_checked} row(s)."
                  if not findings else
                  f"{len(findings)} conservation issue(s) across {rows_checked} rows.")
        return [GateResult(3, "Interest Conservation", status, findings, detail,
                           {"rows_checked": rows_checked})]

    @staticmethod
    def _value_at(sheet, col, row):
        if col is None:
            return None
        cell = sheet.cell(f"{col}{row}")
        return cell.value if cell else None

    @staticmethod
    def _escalate(sheet, row, col, category, message) -> Finding:
        return Finding(
            gate_id=3, gate_name="Interest Conservation", category=category,
            severity=Severity.HIGH, message=message,
            location=CellRef(sheet=sheet.name, cell=f"{col}{row}"),
            subject=f"{sheet.name} row {row}", repairable=False, escalate=True)
