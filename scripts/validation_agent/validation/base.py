"""Validator ABC and the suite runner that aggregates a Scorecard."""
from __future__ import annotations

import abc

from ..ingestion.sheet_models import SheetValues
from ..ingestion.workbook_map import WorkbookModel
from ..models import GateId, GateScore, Scorecard, Severity, ValidationResult


class Validator(abc.ABC):
    """Read-only, deterministic, offline gate. Never mutates; never hits network."""

    gate: GateId

    @abc.abstractmethod
    def validate(
        self, model: WorkbookModel, values: SheetValues
    ) -> list[ValidationResult]:
        ...


class ValidatorSuite:
    """Runs gates in fixed order G1..G5 and folds results into a Scorecard."""

    def __init__(self, validators: list[Validator]) -> None:
        # Deterministic order by gate id.
        self._validators = sorted(validators, key=lambda v: v.gate.value)

    def run_all(
        self, model: WorkbookModel, values: SheetValues
    ) -> tuple[list[ValidationResult], Scorecard]:
        results: list[ValidationResult] = []
        scores: dict[GateId, GateScore] = {}
        for v in self._validators:
            gate_results = v.validate(model, values)
            results.extend(gate_results)
            fails = [r for r in gate_results if not r.passed]
            worst = Severity.INFO
            for r in gate_results:
                if r.severity == Severity.FAIL:
                    worst = Severity.FAIL
                elif r.severity == Severity.WARN and worst != Severity.FAIL:
                    worst = Severity.WARN
            scores[v.gate] = GateScore(
                gate=v.gate,
                passed=not fails,
                failures=len(fails),
                worst=worst,
            )
        return results, Scorecard(scores=scores)
