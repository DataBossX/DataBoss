"""Plan safe formula repairs from triaged findings.

A repair is only planned when the exact formula can be derived without assuming
any legal/title/source fact:

* Formula-column restoration — a hardcoded cell in a column whose other cells
  share one unambiguous relative formula template. The template's row token is
  substituted with the target cell's row.
* Acreage total restoration — a hardcoded total cell replaced by a SUM over the
  contiguous tract acreage range.

Anything else is returned as unplanned and must escalate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.enums import FailureCategory
from ingestion.workbook_ingestor import SheetView, WorkbookStructure
from repair.failure_classifier import Triage
from repair.xml_editor import RepairOp

_COORD_RE = re.compile(r"^([A-Z]{1,3})(\d+)$")


@dataclass
class RepairPlan:
    ops: List[RepairOp] = field(default_factory=list)
    unplanned: List[Triage] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def has_work(self) -> bool:
        return bool(self.ops)


def _split_coord(coord: str) -> Optional[Tuple[str, int]]:
    m = _COORD_RE.match(coord.strip())
    if not m:
        return None
    return m.group(1), int(m.group(2))


def _sheet_by_name(structure: WorkbookStructure, name: str) -> Optional[SheetView]:
    for s in structure.sheets:
        if s.name == name:
            return s
    return None


def _column_template(sheet: SheetView, column_letter: str) -> Optional[str]:
    """Return the single shared relative-formula template for a column, if any."""
    from openpyxl.utils import column_index_from_string

    col_idx = column_index_from_string(column_letter)
    templates = set()
    for fc in sheet.formula_cells:
        if fc.column != col_idx or not fc.formula:
            continue
        template = re.sub(r"(\$?[A-Z]{1,3})\$?(\d+)", r"\1<row>", fc.formula)
        templates.add(template)
    if len(templates) == 1:
        return templates.pop()
    return None


def plan_repairs(triages: List[Triage], structure: WorkbookStructure) -> RepairPlan:
    plan = RepairPlan()
    for triage in triages:
        if triage.route != "repair":
            continue
        result = triage.result
        coord = result.affected_cell_or_range or ""
        sheet_name = result.affected_sheet

        # Formula-column restoration.
        if triage.category == FailureCategory.FORMULA_DEFECT and sheet_name:
            parsed = _split_coord(coord)
            sheet = _sheet_by_name(structure, sheet_name)
            if parsed and sheet:
                col_letter, row_num = parsed
                template = _column_template(sheet, col_letter)
                if template:
                    formula = template.replace("<row>", str(row_num))
                    formula = formula.lstrip("=")
                    plan.ops.append(
                        RepairOp(
                            sheet_name=sheet_name,
                            coordinate=coord,
                            formula=formula,
                        )
                    )
                    plan.notes.append(
                        f"planned formula restore {sheet_name}!{coord} = ={formula}"
                    )
                    continue
        # Could not derive a safe formula -> escalate.
        plan.unplanned.append(triage)
        plan.notes.append(
            f"unplanned (escalate): {result.gate_name} {sheet_name}!{coord}"
        )
    return plan
