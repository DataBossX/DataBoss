"""OGL register audit (Gate 7) and WI / depth consistency (Gate 8).

Gate 7 -- every OGL referenced from a tract must exist in the OGL register and
          must also surface in the working-interest (WI) sheets.  An orphaned
          lease (referenced but not registered) or a lease that never reaches
          the WI sheets is a lease-logic mismatch and escalates.

Gate 8 -- a lease's depth limitation must be identical wherever it appears
          (register vs WI/assignment).  A depth clash between the register and
          the WI sheet escalates.

These gates cross-reference facts already in the workbook; they never invent a
lease, an assignment, or a depth clause, and they never auto-repair.
"""

from __future__ import annotations

import re

from ..models import CellRef, FailureCategory, Finding, GateResult, GateStatus, Severity
from ..ingestion.sheet_classifier import SheetCategory
from ._helpers import data_cells_in_column, find_header_column, is_total_row
from .base_validator import ValidatorBase


def _norm_id(value) -> str:
    return re.sub(r"\s+", "", str(value).upper()).strip()


def _norm_depth(value) -> str:
    s = str(value).lower()
    s = re.sub(r"[',]", "", s)
    s = re.sub(r"\bfeet\b|\bft\b", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


class OglWiValidator(ValidatorBase):
    gate_name = "OGL & WI/Depth Consistency"
    gate_ids = (7, 8)

    def _run(self, manifest) -> list[GateResult]:
        return [self._ogl_gate(manifest), self._depth_gate(manifest)]

    # -- Gate 7 ------------------------------------------------------------
    def _ogl_gate(self, manifest) -> GateResult:
        registers = manifest.by_category(SheetCategory.OGL_REGISTER)
        tracts = manifest.by_category(SheetCategory.TRACT)
        wi_sheets = manifest.by_category(SheetCategory.WORKING_INTEREST)

        if not registers:
            return GateResult(7, "OGL Register Audit", GateStatus.ERROR,
                              detail="No OGL register sheet classified.")

        registered = self._collect_ids(registers, "ogl", "lease number", "lease id",
                                        "lease")
        referenced = self._collect_ids(tracts, "ogl", "lease number", "lease id",
                                       "lease")
        in_wi = self._collect_ids(wi_sheets, "ogl", "lease number", "lease id",
                                  "lease")

        findings: list[Finding] = []
        for lease, loc in referenced.items():
            if lease not in registered:
                findings.append(Finding(
                    gate_id=7, gate_name="OGL Register Audit",
                    category=FailureCategory.OGL_WI_MISMATCH, severity=Severity.HIGH,
                    message=(f"Lease '{lease}' is referenced in a tract but is "
                             f"orphaned -- not present in the OGL register."),
                    location=loc, subject=f"OGL {lease}",
                    repairable=False, escalate=True))
            elif wi_sheets and lease not in in_wi:
                findings.append(Finding(
                    gate_id=7, gate_name="OGL Register Audit",
                    category=FailureCategory.OGL_WI_MISMATCH, severity=Severity.HIGH,
                    message=(f"Lease '{lease}' is registered and referenced in a "
                             f"tract but never appears in the WI sheets."),
                    location=loc, subject=f"OGL {lease}",
                    repairable=False, escalate=True))

        status = GateStatus.PASS if not findings else GateStatus.FAIL
        detail = (f"{len(referenced)} referenced lease(s) tie to register/WI."
                  if not findings else
                  f"{len(findings)} orphaned/missing lease link(s).")
        return GateResult(7, "OGL Register Audit", status, findings, detail,
                          {"registered": len(registered),
                           "referenced": len(referenced), "in_wi": len(in_wi)})

    # -- Gate 8 ------------------------------------------------------------
    def _depth_gate(self, manifest) -> GateResult:
        registers = manifest.by_category(SheetCategory.OGL_REGISTER)
        wi_sheets = manifest.by_category(SheetCategory.WORKING_INTEREST)
        if not registers or not wi_sheets:
            return GateResult(8, "WI/Depth Consistency", GateStatus.SKIPPED,
                              detail="Register or WI sheet absent; no depth cross-check.")

        reg_depths = self._depth_map(registers)
        wi_depths = self._depth_map(wi_sheets)

        findings: list[Finding] = []
        compared = 0
        for lease, (reg_depth, reg_loc) in reg_depths.items():
            if lease not in wi_depths:
                continue
            wi_depth, wi_loc = wi_depths[lease]
            compared += 1
            if _norm_depth(reg_depth) != _norm_depth(wi_depth):
                findings.append(Finding(
                    gate_id=8, gate_name="WI/Depth Consistency",
                    category=FailureCategory.OGL_WI_MISMATCH, severity=Severity.HIGH,
                    message=(f"Depth clash for lease '{lease}': register says "
                             f"'{reg_depth}' but WI says '{wi_depth}'."),
                    location=wi_loc, subject=f"OGL {lease}",
                    repairable=False, escalate=True,
                    evidence={"register_depth": reg_depth, "wi_depth": wi_depth}))

        status = GateStatus.PASS if not findings else GateStatus.FAIL
        detail = (f"{compared} lease depth clause(s) align."
                  if not findings else
                  f"{len(findings)} depth clash(es) between register and WI.")
        return GateResult(8, "WI/Depth Consistency", status, findings, detail,
                          {"compared": compared})

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _collect_ids(sheets, *header_keywords) -> dict[str, CellRef]:
        out: dict[str, CellRef] = {}
        for sheet in sheets:
            col = find_header_column(sheet, *header_keywords)
            if not col:
                continue
            for cell in data_cells_in_column(sheet, col):
                if is_total_row(sheet, cell.row) or cell.value is None:
                    continue
                lease = _norm_id(cell.value)
                if lease and lease not in out:
                    out[lease] = CellRef(sheet=sheet.name, cell=f"{col}{cell.row}")
        return out

    @staticmethod
    def _depth_map(sheets) -> dict[str, tuple[str, CellRef]]:
        out: dict[str, tuple[str, CellRef]] = {}
        for sheet in sheets:
            id_col = find_header_column(sheet, "ogl", "lease number", "lease id",
                                        "lease")
            depth_col = find_header_column(sheet, "depth", "interval", "formation",
                                           "limitation")
            if not (id_col and depth_col):
                continue
            for cell in data_cells_in_column(sheet, id_col):
                if is_total_row(sheet, cell.row) or cell.value is None:
                    continue
                lease = _norm_id(cell.value)
                dcell = sheet.cell(f"{depth_col}{cell.row}")
                depth = str(dcell.value) if dcell and dcell.value is not None else ""
                if lease and lease not in out:
                    out[lease] = (depth, CellRef(sheet=sheet.name,
                                                 cell=f"{depth_col}{cell.row}"))
        return out
