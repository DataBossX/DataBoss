"""SafeFixRegistry — only SAFE, source-derivable repair strategies (Golden Law #3).

A strategy may enter this registry ONLY if its ``after`` value is fully derivable
from the workbook itself or a verified SourceRef. No strategy may synthesise a
legal fact (party, date, interest). Anything else is left for the orchestrator to
route to source-verification or human escalation.
"""
from __future__ import annotations

import abc

from ..ingestion.workbook_map import WorkbookModel
from ..models import (
    Failure,
    FailureCategory,
    FixPlan,
    RiskClass,
    SourceKind,
    SourceRef,
)


class SafeFix(abc.ABC):
    """A repair whose result is provably derivable — risk is always SAFE."""

    strategy_id: str
    risk: RiskClass = RiskClass.SAFE

    @abc.abstractmethod
    def can_handle(self, failure: Failure) -> bool:
        ...

    @abc.abstractmethod
    def plan(self, failure: Failure, model: WorkbookModel) -> FixPlan:
        ...


class FullCalcFix(SafeFix):
    """Force recalculation for FORMULA_ERROR rooted in a stale calc chain."""

    strategy_id = "force_full_calc"

    def can_handle(self, failure: Failure) -> bool:
        return failure.category == FailureCategory.FORMULA_ERROR

    def plan(self, failure: Failure, model: WorkbookModel) -> FixPlan:
        return FixPlan(
            strategy_id=self.strategy_id,
            risk=RiskClass.SAFE,
            target=failure.coord or _wb_coord(model),
            before="stale calc chain",
            after="calcChain dropped; fullCalcOnLoad=1",
            justification=(
                "Formula error attributable to stale cached values; forcing a "
                "clean recompute is deterministic and invents no data."
            ),
            source_refs=[SourceRef(SourceKind.FORMULA, "workbook.calcPr")],
        )


class FootingRangeFix(SafeFix):
    """Repair a COMPUTATION_FOOTING failure caused by a truncated SUMIF range.

    The corrected formula is derived purely from the grid's own dimensions — no
    title fact is created — so it qualifies as SAFE. The concrete new formula is
    carried on the failure's proposed_fix (computed by the validator/analyzer).
    """

    strategy_id = "extend_footing_range"

    def can_handle(self, failure: Failure) -> bool:
        return (
            failure.category == FailureCategory.COMPUTATION_FOOTING
            and failure.proposed_fix is not None
            and failure.proposed_fix.risk == RiskClass.SAFE
        )

    def plan(self, failure: Failure, model: WorkbookModel) -> FixPlan:
        assert failure.proposed_fix is not None
        return failure.proposed_fix


class SafeFixRegistry:
    """Ordered registry. Only SAFE strategies are admitted (enforced)."""

    def __init__(self, strategies: list[SafeFix] | None = None) -> None:
        strategies = strategies or [FullCalcFix(), FootingRangeFix()]
        for s in strategies:
            if s.risk != RiskClass.SAFE:
                raise ValueError(f"non-SAFE strategy rejected: {s.strategy_id}")
        self._strategies = strategies

    def plan_for(self, failure: Failure, model: WorkbookModel) -> FixPlan | None:
        for s in self._strategies:
            if s.can_handle(failure):
                fix = s.plan(failure, model)
                if fix.risk != RiskClass.SAFE:  # defence in depth
                    return None
                return fix
        return None


def _wb_coord(model: WorkbookModel):
    from ..models import Coord
    return Coord(model.wb.sheetnames[0], "A1")
