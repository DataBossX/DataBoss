"""Failure analyzers that upgrade a failure to an auto-fixable SAFE FixPlan.

An analyzer inspects a failing ValidationResult plus the workbook and, when the
defect is repairable purely from the workbook's own structure (no title fact
invented), attaches a SAFE FixPlan. This is what lets the Perfection Loop
*repair* rather than merely *escalate*.
"""
from __future__ import annotations

import abc
import re
from typing import Optional

from ..ingestion.workbook_map import WorkbookModel
from ..models import (
    Coord,
    FixPlan,
    RiskClass,
    SourceKind,
    SourceRef,
    ValidationResult,
)


class Analyzer(abc.ABC):
    @abc.abstractmethod
    def analyze(
        self, result: ValidationResult, model: WorkbookModel
    ) -> Optional[FixPlan]:
        ...


# Matches SUMIF('Tract N'!$E$a:$E$b, ">0", 'Tract N'!$C$a:$C$b) with a captured
# end-row on each range.
_SUMIF = re.compile(
    r"SUMIF\(\s*'(?P<sheet>[^']+)'!\$(?P<c1>[A-Z]+)\$(?P<r1>\d+):"
    r"\$[A-Z]+\$(?P<r2>\d+)\s*,\s*\"[^\"]*\"\s*,\s*"
    r"'(?P=sheet)'!\$(?P<c3>[A-Z]+)\$(?P<r3>\d+):\$[A-Z]+\$(?P<r4>\d+)\s*\)",
    re.IGNORECASE,
)


def _norm_bp(s: str) -> str:
    """Normalise a book/page token to the register's unpadded 'BOOK/PAGE' form."""
    m = re.match(r"(\d+)\s*/\s*0*(\d+)", s)
    return f"{int(m.group(1))}/{int(m.group(2))}" if m else s.strip()


_BP_TOKEN = re.compile(r"\b(\d{3,4})\s*/\s*(\d{3,4})\b")


class PhantomOGLRenumberAnalyzer(Analyzer):
    """Repair a G5 phantom OGL citation when a co-located book/page uniquely
    identifies the intended register entry.

    Only fires when the flagged cell contains exactly one book/page that the OGL
    register maps bijectively to a single (different) OGL number — so the correct
    number is *read from the register*, never guessed. Anything ambiguous
    (no book/page, multiple candidates, non-bijective) returns None -> escalates.
    """

    strategy_id = "renumber_phantom_ogl"

    def analyze(
        self, result: ValidationResult, model: WorkbookModel
    ) -> Optional[FixPlan]:
        if "cites OGL" not in result.message or not result.locations:
            return None
        m = re.search(r"cites OGL (\d+)", result.message)
        if not m:
            return None
        phantom = int(m.group(1))
        coord = result.locations[0]
        ws = self._sheet(model, coord.sheet)
        ogl = model.ogl()
        if ws is None or ogl is None:
            return None
        cell = ws[coord.cell]
        if not isinstance(cell.value, str):
            return None
        # Build the register's book/page -> ogl_no map (must be bijective).
        bp_map: dict[str, int] = {}
        for lease in ogl.leases():
            if lease.book_page and lease.ogl_no is not None:
                key = _norm_bp(lease.book_page)
                if key in bp_map and bp_map[key] != lease.ogl_no:
                    return None  # non-bijective -> unsafe, escalate
                bp_map[key] = lease.ogl_no
        candidates = {
            bp_map[_norm_bp(f"{a}/{b}")]
            for a, b in _BP_TOKEN.findall(cell.value)
            if _norm_bp(f"{a}/{b}") in bp_map
        }
        if len(candidates) != 1:
            return None  # zero or ambiguous -> escalate
        correct = candidates.pop()
        if correct == phantom:
            return None
        fixed = re.sub(rf"\bOGL\s*#?\s*{phantom}\b", f"OGL {correct}", cell.value)
        if fixed == cell.value:
            return None
        return FixPlan(
            strategy_id=self.strategy_id,
            risk=RiskClass.SAFE,
            target=Coord(coord.sheet, coord.cell),
            before=cell.value,
            after=fixed,
            justification=(
                f"Cited OGL {phantom} is absent from the register; the cell's own "
                f"book/page maps bijectively to register OGL {correct}. Correct "
                f"number is read from the register, not inferred."
            ),
            source_refs=[SourceRef(SourceKind.FORMULA, f"OGL!register")],
        )

    @staticmethod
    def _sheet(model: WorkbookModel, name: str):
        for n in model.wb.sheetnames:
            if n == name or n.strip() == name.strip():
                return model.wb[n]
        return None


class FootingRangeAnalyzer(Analyzer):
    """Repair a G2 footing break caused by a SUMIF range that stops short of the
    tract grid's data extent.

    The corrected end-row is the grid worksheet's own ``max_row`` — a structural
    fact, not a title fact — so the fix is SAFE. If the range already covers the
    extent (i.e. the break has some other cause), no plan is returned and the
    failure escalates.
    """

    strategy_id = "extend_footing_range"

    def analyze(
        self, result: ValidationResult, model: WorkbookModel
    ) -> Optional[FixPlan]:
        if not result.locations:
            return None
        coord = result.locations[0]
        ws = self._sheet(model, coord.sheet)
        if ws is None:
            return None
        cell = ws[coord.cell]
        formula = cell.value
        if not isinstance(formula, str) or "SUMIF" not in formula.upper():
            return None
        m = _SUMIF.search(formula)
        if not m:
            return None
        grid_ws = self._sheet(model, m.group("sheet"))
        if grid_ws is None:
            return None
        extent = grid_ws.max_row
        cur_end = max(int(m.group("r2")), int(m.group("r4")))
        if cur_end >= extent:
            return None  # not a truncation; let it escalate
        fixed = self._rewrite_end_rows(formula, extent)
        if fixed == formula:
            return None
        return FixPlan(
            strategy_id=self.strategy_id,
            risk=RiskClass.SAFE,
            target=Coord(coord.sheet, coord.cell),
            before=formula,
            after=fixed,
            justification=(
                f"Footing SUMIF stopped at row {cur_end} but '{m.group('sheet')}' "
                f"holds data through row {extent}; extending the range to cover all "
                f"owner rows is derived from the grid's own dimensions and invents "
                f"no title fact."
            ),
            source_refs=[SourceRef(SourceKind.FORMULA, f"{coord.sheet}!{coord.cell}")],
        )

    # -- helpers ---------------------------------------------------------- #
    @staticmethod
    def _sheet(model: WorkbookModel, name: str):
        for n in model.wb.sheetnames:
            if n == name or n.strip() == name.strip():
                return model.wb[n]
        return None

    @staticmethod
    def _rewrite_end_rows(formula: str, extent: int) -> str:
        """Rewrite every ``$COL$a:$COL$b`` end-row to ``extent`` (b only)."""
        def repl(mo: re.Match) -> str:
            return f"{mo.group(1)}:${mo.group(2)}${extent}"
        return re.sub(r"(\$[A-Z]+\$\d+):\$([A-Z]+)\$(\d+)", repl, formula)
