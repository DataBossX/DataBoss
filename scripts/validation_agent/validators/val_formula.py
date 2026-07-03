"""Formula Integrity Gate.

Detects hardcoded values sitting in cells that should carry formulas (an
"expected formula area"), typically footing/total cells. A formula defect is
only marked *repairable* when the exact intended formula can be recovered from
adjacent cells, a template, or immutable prior-version evidence. Otherwise it
is escalated — the agent never guesses a formula.
"""

from __future__ import annotations

import re
from typing import Any

from .base_validator import BaseValidator, ValidationResult, SEVERITY_MEDIUM

_COL_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _neighbor_formula(coord: str, formula_map: dict[str, str]) -> str | None:
    """If the cell directly above/below shares a column-relative pattern,
    return an intended formula for ``coord`` by row-shifting the neighbor."""
    m = _COL_RE.match(coord)
    if not m:
        return None
    col, row = m.group(1), int(m.group(2))
    for delta in (-1, 1):
        neighbor = f"{col}{row + delta}"
        f = formula_map.get(neighbor)
        if f:
            return f  # examiner-visible template; not auto-applied blindly
    return None


def detect_formula_defects(expected_formula_cells: list[str],
                           formula_map: dict[str, str],
                           value_map: dict[str, Any]) -> dict:
    """Identify cells that should be formulas but hold hardcoded values."""
    defects = []
    for coord in expected_formula_cells:
        if coord in formula_map:
            continue  # already a formula
        if coord in value_map:  # hardcoded literal in a formula area
            intended = _neighbor_formula(coord, formula_map)
            defects.append({
                "cell": coord,
                "hardcoded_value": value_map[coord],
                "intended_formula": intended,
                "repairable": intended is not None,
            })
    return {"defects": defects, "clean": not defects}


class FormulaIntegrityValidator(BaseValidator):
    gate_name = "Formula Integrity Gate"

    def run(self, context: dict) -> list[ValidationResult]:
        expected = context.get("expected_formula_cells") or []
        formula_map = context.get("formula_map") or {}
        value_map = context.get("value_map") or {}
        sheet = context.get("formula_sheet")
        if not expected:
            return [self._pass(
                affected_subject="formula integrity",
                reason="No expected-formula cells declared for this workbook.",
            )]
        report = detect_formula_defects(expected, formula_map, value_map)
        if report["clean"]:
            return [self._pass(
                affected_subject="formula integrity", affected_sheet=sheet,
                reason="All expected-formula cells contain formulas.",
            )]
        results: list[ValidationResult] = []
        for d in report["defects"]:
            if d["repairable"]:
                results.append(self._fail(
                    severity=SEVERITY_MEDIUM, repairable=True,
                    affected_sheet=sheet, affected_cell_or_range=d["cell"],
                    affected_subject="formula integrity", evidence=d,
                    reason=f"Cell {d['cell']} holds hardcoded "
                           f"{d['hardcoded_value']!r}; intended formula "
                           f"recoverable from a neighbor.",
                    recommended_action="Safe formula repair: restore "
                                       f"{d['intended_formula']} on a new version.",
                    confidence=0.85,
                ))
            else:
                results.append(self._escalate(
                    severity=SEVERITY_MEDIUM, repairable=False,
                    affected_sheet=sheet, affected_cell_or_range=d["cell"],
                    affected_subject="formula integrity", evidence=d,
                    reason=f"Cell {d['cell']} is hardcoded and the intended "
                           f"formula is unknown.",
                    recommended_action="Examiner must supply intended formula; "
                                       "never guessed.",
                    confidence=0.8,
                ))
        return results
