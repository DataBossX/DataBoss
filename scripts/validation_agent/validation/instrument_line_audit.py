"""Gate G4 — Instrument-Line Audit.

Every OGL register line and every runsheet instrument must resolve to at least
one source: a rawdata row (by book/page or instrument number) or a fetched
okcr/index evidence entry. Coverage must be 1.0.
"""
from __future__ import annotations

import re
from typing import Optional

import openpyxl

from ..ingestion.sheet_models import SheetValues
from ..ingestion.workbook_map import WorkbookModel
from ..models import Coord, GateId, SheetKind, Severity, ValidationResult
from .base import Validator


def _norm_bp(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    m = re.match(r"([A-Za-z]*\s*\d+)\s*/\s*0*(\d+)", str(s))
    if not m:
        return str(s).strip()
    return f"{m.group(1).strip()}/{int(m.group(2))}"


class InstrumentLineAuditValidator(Validator):
    gate = GateId.G4_INSTRUMENT

    def validate(
        self, model: WorkbookModel, values: SheetValues
    ) -> list[ValidationResult]:
        raw_bp, raw_instr = self._rawdata_index(model)
        results: list[ValidationResult] = []
        total = 0
        unresolved = 0

        ogl = model.ogl()
        if ogl:
            for lease in ogl.leases():
                total += 1
                if not self._resolved(lease.book_page, None, raw_bp, raw_instr):
                    unresolved += 1
                    results.append(
                        ValidationResult(
                            gate=self.gate,
                            passed=False,
                            severity=Severity.WARN,
                            message=(
                                f"OGL {lease.ogl_no} (Bk {lease.book_page}) not "
                                f"traceable to a source row"
                            ),
                            locations=[Coord(ogl.ws.title, f"E{lease.row}")],
                        )
                    )

        rs = model.runsheet()
        if rs:
            for r in rs.instruments():
                total += 1
                if not self._resolved(r.book_page, r.instrument_no, raw_bp, raw_instr):
                    unresolved += 1
                    results.append(
                        ValidationResult(
                            gate=self.gate,
                            passed=False,
                            severity=Severity.WARN,
                            message=(
                                f"Runsheet row {r.row} instr {r.instrument_no} "
                                f"(Bk {r.book_page}) not traceable to a source row"
                            ),
                            locations=[Coord(rs.ws.title, f"A{r.row}")],
                        )
                    )

        coverage = 1.0 if total == 0 else (total - unresolved) / total
        summary = ValidationResult(
            gate=self.gate,
            passed=unresolved == 0,
            severity=Severity.INFO if unresolved == 0 else Severity.WARN,
            message=f"Instrument coverage {coverage:.4f} ({total - unresolved}/{total})",
            metric=coverage,
            expected=1.0,
        )
        return [summary] + results

    # -- helpers ---------------------------------------------------------- #
    @staticmethod
    def _resolved(bp, instr, raw_bp: set[str], raw_instr: set[str]) -> bool:
        nbp = _norm_bp(bp)
        if nbp and nbp in raw_bp:
            return True
        if instr and str(instr).strip() in raw_instr:
            return True
        return False

    @staticmethod
    def _rawdata_index(model: WorkbookModel) -> tuple[set[str], set[str]]:
        names = model.sheets_of(SheetKind.RAWDATA)
        bp: set[str] = set()
        instr: set[str] = set()
        if not names:
            return bp, instr
        ws = model.wb[names[0]]
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if isinstance(cell, str):
                    n = _norm_bp(cell)
                    if n and re.match(r"[A-Za-z]*\s*\d+/\d+$", n):
                        bp.add(n)
                    if re.match(r"^\d{4}-\d{5,6}$", cell.strip()):
                        instr.add(cell.strip())
        return bp, instr
