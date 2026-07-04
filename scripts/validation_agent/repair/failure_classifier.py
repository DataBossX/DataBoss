"""Failure taxonomy and routing.

Maps each failing/escalating ValidationResult to a FailureCategory and a route:
``repair`` (safe deterministic math/formula/format) or ``escalate`` (anything
touching legal, title, source, or economic facts).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from core.enums import (
    SAFE_REPAIR_CATEGORIES,
    FailureCategory,
    GateStatus,
)
from validators.base_validator import ValidationResult


@dataclass(frozen=True)
class Triage:
    result: ValidationResult
    category: FailureCategory
    route: str  # "repair" | "escalate"
    rationale: str


def classify(result: ValidationResult) -> Triage:
    category = result.failure_category or FailureCategory.UNSAFE_LEGAL_INFERENCE

    # Explicit escalation from a validator always escalates.
    if result.status == GateStatus.ESCALATE:
        return Triage(
            result=result,
            category=category,
            route="escalate",
            rationale="validator escalated; human examiner required",
        )

    # Only safe categories that the validator marked repairable may be repaired.
    if category in SAFE_REPAIR_CATEGORIES and result.repairable:
        return Triage(
            result=result,
            category=category,
            route="repair",
            rationale="safe deterministic repair (formula/math/format)",
        )

    return Triage(
        result=result,
        category=category,
        route="escalate",
        rationale="not a safe auto-repair category or not marked repairable",
    )


def triage_results(results: List[ValidationResult]) -> List[Triage]:
    actionable = [
        r for r in results if r.status in (GateStatus.FAIL, GateStatus.ESCALATE)
    ]
    return [classify(r) for r in actionable]
