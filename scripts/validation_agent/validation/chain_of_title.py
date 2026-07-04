"""Gate G3 — Chain-of-Title Continuity.

Detects orphan grantors: a row that conveys interest OUT (negative row total on a
tract grid) but whose name does not appear as a prior grantee anywhere in the
same tract and has no locatable source. These are exactly the cells the report
highlights yellow. We surface them as WARN (route to source-verification), not
FAIL, because an orphan is a research task, not a computational defect — the loop
must never auto-invent the missing vesting.
"""
from __future__ import annotations

import re

from ..ingestion.sheet_models import SheetValues
from ..ingestion.workbook_map import WorkbookModel
from ..models import Coord, GateId, Severity, ValidationResult
from .base import Validator

# Administrative / pass-through parties that are never "orphans".
_EXCLUDE = re.compile(r"(court\b|sheriff|treasurer|the public|united states of america)", re.I)
_STOP = {
    "the", "and", "of", "a", "hw", "jr", "sr", "ii", "iii", "iv", "llc", "inc",
    "ltd", "co", "company", "trust", "trustee", "trustees", "aka", "also",
    "known", "as", "estate", "et", "ux", "al", "family", "revocable",
}


def _tokens(name: str) -> frozenset[str]:
    words = re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
    return frozenset(w for w in words if w not in _STOP and len(w) > 1)


class ChainOfTitleValidator(Validator):
    gate = GateId.G3_CHAIN

    def validate(
        self, model: WorkbookModel, values: SheetValues
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for grid in model.tracts():
            owners = grid.owner_rows(values)
            grantee_tokens: list[frozenset[str]] = [
                _tokens(o.name) for o in owners
                if o.name and (o.row_total or 0) > 0
            ]
            for o in owners:
                if not o.name or (o.row_total or 0) >= -1e-6:
                    continue
                if _EXCLUDE.search(o.name):
                    continue
                toks = _tokens(o.name)
                # resolved if this grantor also appears as a grantee (was vested)
                resolved = any(
                    toks and gt and len(toks & gt) / min(len(toks), len(gt)) >= 0.8
                    for gt in grantee_tokens
                )
                if not resolved:
                    results.append(
                        ValidationResult(
                            gate=self.gate,
                            passed=False,
                            severity=Severity.WARN,  # -> source-verification, not auto-fix
                            message=(
                                f"Tract {grid.tract_no} row {o.row}: grantor "
                                f"'{o.name[:40]}' conveys out with no prior vesting "
                                f"found (orphan; highlight/verify)"
                            ),
                            locations=[Coord(grid.ws.title, f"D{o.row}")],
                        )
                    )
        if not results:
            results.append(
                ValidationResult(
                    gate=self.gate,
                    passed=True,
                    severity=Severity.INFO,
                    message="No unresolved orphan grantors detected.",
                )
            )
        return results
