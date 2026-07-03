"""Instrument source audit (Gate 6) and Well/HBP support (Gate 9).

Gate 6 -- every material title row must trace to a recorded source: a Book/Page
          or an Instrument Number.  A material row without a source is an
          unverifiable assertion and escalates (never auto-repaired: the source
          reference is a fact, not a formatting artifact).

Gate 9 -- any "held by production" (HBP) claim on an exception/curative sheet
          must be backed by an active well in the wells data.  An HBP claim with
          no supporting active/producing well escalates as HBP_UNSUPPORTED.  The
          supporting well is read from the workbook -- never assumed.
"""

from __future__ import annotations

from ..models import CellRef, FailureCategory, Finding, GateResult, GateStatus, Severity
from ..ingestion.sheet_classifier import SheetCategory
from ._helpers import data_cells_in_column, find_header_column, is_total_row
from .base_validator import ValidatorBase

_HBP_TOKENS = ("hbp", "held by production", "beyond primary term",
               "past primary term", "production support", "secondary term")
_ACTIVE_TOKENS = ("active", "producing", "online", "flowing", "in production")


class InstrumentValidator(ValidatorBase):
    gate_name = "Instrument Source & HBP"
    gate_ids = (6, 9)

    def _run(self, manifest) -> list[GateResult]:
        return [self._source_gate(manifest), self._hbp_gate(manifest)]

    # -- Gate 6 ------------------------------------------------------------
    def _source_gate(self, manifest) -> GateResult:
        material = (manifest.by_category(SheetCategory.RUNSHEET)
                    + manifest.by_category(SheetCategory.OGL_REGISTER))
        if not material:
            return GateResult(6, "Instrument Source Audit", GateStatus.ERROR,
                              detail="No runsheet/OGL register to audit for sources.")

        findings: list[Finding] = []
        rows_checked = 0
        for sheet in material:
            book_col = find_header_column(sheet, "book")
            page_col = find_header_column(sheet, "page")
            inst_col = find_header_column(sheet, "instrument number", "inst #",
                                          "instrument #", "instrument no")
            key_col = (find_header_column(sheet, "grantor", "lessor", "instrument")
                       or (sheet.headers and "A"))
            if not key_col:
                continue
            key_col = key_col if isinstance(key_col, str) else "A"

            for cell in data_cells_in_column(sheet, key_col):
                row = cell.row
                if is_total_row(sheet, row) or cell.value is None:
                    continue
                rows_checked += 1
                book = self._text(sheet, book_col, row)
                page = self._text(sheet, page_col, row)
                inst = self._text(sheet, inst_col, row)
                has_source = bool((book and page) or inst)
                if not has_source:
                    findings.append(Finding(
                        gate_id=6, gate_name="Instrument Source Audit",
                        category=FailureCategory.MISSING_SOURCE,
                        severity=Severity.HIGH,
                        message=(f"{sheet.name} row {row}: material row lacks a "
                                 f"traceable Book/Page or Instrument #."),
                        location=CellRef(sheet=sheet.name, cell=f"{key_col}{row}"),
                        subject=f"{sheet.name} row {row}",
                        repairable=False, escalate=True))

        status = GateStatus.PASS if not findings else GateStatus.FAIL
        detail = (f"All {rows_checked} material rows carry a source."
                  if not findings else
                  f"{len(findings)} material row(s) lack a source reference.")
        return GateResult(6, "Instrument Source Audit", status, findings, detail,
                          {"rows_checked": rows_checked})

    # -- Gate 9 ------------------------------------------------------------
    def _hbp_gate(self, manifest) -> GateResult:
        exceptions = manifest.by_category(SheetCategory.EXCEPTION_CURATIVE)
        wells = manifest.by_category(SheetCategory.WELLS)
        if not exceptions:
            return GateResult(9, "Well/HBP Support", GateStatus.SKIPPED,
                              detail="No exception/curative sheet; no HBP claims to test.")

        active_wells = self._active_wells(wells)
        findings: list[Finding] = []
        claims = 0

        for sheet in exceptions:
            for cell in sheet.cells.values():
                if not isinstance(cell.value, str):
                    continue
                text = cell.value.lower()
                if not any(tok in text for tok in _HBP_TOKENS):
                    continue
                claims += 1
                if not active_wells:
                    findings.append(Finding(
                        gate_id=9, gate_name="Well/HBP Support",
                        category=FailureCategory.HBP_UNSUPPORTED,
                        severity=Severity.HIGH,
                        message=(f"{sheet.name}!{cell.coord}: HBP claim has no active "
                                 f"producing well recorded to support it."),
                        location=CellRef(sheet=sheet.name, cell=cell.coord),
                        subject=f"{sheet.name}!{cell.coord}",
                        repairable=False, escalate=True,
                        evidence={"claim_text": cell.value[:200]}))

        status = GateStatus.PASS if not findings else GateStatus.FAIL
        detail = (f"{claims} HBP claim(s) supported by {len(active_wells)} active well(s)."
                  if not findings else
                  f"{len(findings)} HBP claim(s) lack production support.")
        return GateResult(9, "Well/HBP Support", status, findings, detail,
                          {"hbp_claims": claims, "active_wells": len(active_wells)})

    @staticmethod
    def _active_wells(wells) -> list[str]:
        names: list[str] = []
        for sheet in wells:
            name_col = find_header_column(sheet, "well", "well name", "name")
            status_col = find_header_column(sheet, "status", "state")
            if not name_col:
                continue
            for cell in data_cells_in_column(sheet, name_col):
                if is_total_row(sheet, cell.row) or cell.value is None:
                    continue
                status = ""
                if status_col:
                    scell = sheet.cell(f"{status_col}{cell.row}")
                    status = str(scell.value).lower() if scell and scell.value else ""
                if any(tok in status for tok in _ACTIVE_TOKENS):
                    names.append(str(cell.value))
        return names

    @staticmethod
    def _text(sheet, col, row) -> str:
        if not col:
            return ""
        cell = sheet.cell(f"{col}{row}")
        return str(cell.value).strip() if cell and cell.value is not None else ""
