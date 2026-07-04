"""Gate G5 — OGL Register Audit.

(a) every OGL number referenced on Title/WI exists exactly once in the register;
(b) book/page <-> OGL number is a bijection (no dup mappings);
(c) no phantom OGL numbers are cited that the register does not contain.
"""
from __future__ import annotations

import re

from ..ingestion.sheet_models import SheetValues
from ..ingestion.workbook_map import WorkbookModel
from ..models import Coord, GateId, SheetKind, Severity, ValidationResult
from .base import Validator

_OGL_REF = re.compile(r"\bOGL\s*#?\s*(\d{1,3})\b", re.IGNORECASE)


class OGLRegisterAuditValidator(Validator):
    gate = GateId.G5_OGL

    def validate(
        self, model: WorkbookModel, values: SheetValues
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        ogl = model.ogl()
        if ogl is None:
            return [
                ValidationResult(
                    gate=self.gate, passed=False, severity=Severity.FAIL,
                    message="OGL register sheet not found",
                )
            ]
        leases = ogl.leases()
        register_nums = [l.ogl_no for l in leases if l.ogl_no is not None]

        # (a) uniqueness of numbers within the register
        seen: dict[int, int] = {}
        for l in leases:
            if l.ogl_no is None:
                continue
            if l.ogl_no in seen:
                results.append(
                    ValidationResult(
                        gate=self.gate, passed=False, severity=Severity.FAIL,
                        message=f"Duplicate OGL number {l.ogl_no} in register",
                        locations=[Coord(ogl.ws.title, f"A{l.row}")],
                    )
                )
            seen[l.ogl_no] = l.row

        # (b) book/page <-> number bijection
        bp_to_num: dict[str, int] = {}
        for l in leases:
            if l.book_page and l.ogl_no is not None:
                if l.book_page in bp_to_num and bp_to_num[l.book_page] != l.ogl_no:
                    results.append(
                        ValidationResult(
                            gate=self.gate, passed=False, severity=Severity.FAIL,
                            message=(
                                f"Book/page {l.book_page} maps to OGL "
                                f"{bp_to_num[l.book_page]} and {l.ogl_no}"
                            ),
                            locations=[Coord(ogl.ws.title, f"E{l.row}")],
                        )
                    )
                bp_to_num[l.book_page] = l.ogl_no

        # (c) phantom references on Title/WI
        register_set = set(register_nums)
        for kind in (SheetKind.OTHER,):  # Title has a trailing space; handle by name
            pass
        for name in model.wb.sheetnames:
            low = name.strip().lower()
            if low not in ("title", "wi 1", "wi 2"):
                continue
            ws = model.wb[name]
            for row in ws.iter_rows():
                for c in row:
                    if not isinstance(c.value, str):
                        continue
                    text = c.value
                    for m in _OGL_REF.finditer(text):
                        num = int(m.group(1))
                        if num in register_set:
                            continue
                        # Skip range citations like "OGL 64-69" / "109-114".
                        after = text[m.end():m.end() + 1]
                        before = text[max(0, m.start() - 1):m.start()]
                        if after in ("-", "–") or before in ("-", "–"):
                            continue
                        results.append(
                            ValidationResult(
                                gate=self.gate, passed=False,
                                severity=Severity.WARN,
                                message=(
                                    f"{name}!{c.coordinate} cites OGL {num} "
                                    f"absent from register"
                                ),
                                locations=[Coord(name, c.coordinate)],
                            )
                        )

        if not results:
            results.append(
                ValidationResult(
                    gate=self.gate, passed=True, severity=Severity.INFO,
                    message=(
                        f"Register consistent: {len(register_nums)} leases, "
                        f"unique numbers, bijective book/page, no phantom refs."
                    ),
                )
            )
        return results
