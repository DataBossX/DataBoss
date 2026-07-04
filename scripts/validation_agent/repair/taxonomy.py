"""Failure taxonomy — the single routing authority (Component 8 support)."""
from __future__ import annotations

from ..models import (
    Failure,
    FailureCategory,
    GateId,
    RiskClass,
    Severity,
    ValidationResult,
)

_ID = {
    GateId.G1_CONSERVATION: FailureCategory.COMPUTATION_CONSERVATION,
    GateId.G2_FOOTING: FailureCategory.COMPUTATION_FOOTING,
    GateId.G3_CHAIN: FailureCategory.TITLE_GAP_ORPHAN,
    GateId.G4_INSTRUMENT: FailureCategory.PROVENANCE_MISSING,
    GateId.G5_OGL: FailureCategory.REGISTER_MISMATCH,
}


class FailureTaxonomy:
    """Classifies a ValidationResult into a (category, risk) route."""

    @staticmethod
    def classify(
        result: ValidationResult, failure: "Failure | None" = None
    ) -> tuple[FailureCategory, RiskClass]:
        cat = _ID.get(result.gate, FailureCategory.XML_DAMAGE)
        # A proposed SAFE fix (from an analyzer) always routes SAFE.
        if failure is not None and failure.proposed_fix is not None:
            if failure.proposed_fix.risk == RiskClass.SAFE:
                return failure.category, RiskClass.SAFE
        # Formula errors override by message content.
        if "#REF" in result.message or "#VALUE" in result.message:
            return FailureCategory.FORMULA_ERROR, RiskClass.SAFE
        if result.gate == GateId.G2_FOOTING:
            # Footing gaps are SAFE only if a truncated range is the cause; the
            # analyzer attaches a SAFE FixPlan when so. Absent that -> UNSAFE.
            return cat, RiskClass.UNSAFE
        if result.gate == GateId.G1_CONSERVATION:
            # Unconserved ARTI columns need the instrument image -> source/escalate.
            return cat, RiskClass.NEEDS_SOURCE
        if result.gate == GateId.G3_CHAIN:
            return FailureCategory.TITLE_GAP_ORPHAN, RiskClass.NEEDS_SOURCE
        if result.gate == GateId.G4_INSTRUMENT:
            return FailureCategory.PROVENANCE_MISSING, RiskClass.NEEDS_SOURCE
        if result.gate == GateId.G5_OGL:
            if result.severity == Severity.FAIL:
                return FailureCategory.REGISTER_MISMATCH, RiskClass.UNSAFE
            return FailureCategory.REGISTER_PHANTOM_OGL, RiskClass.NEEDS_SOURCE
        return cat, RiskClass.UNSAFE

    @staticmethod
    def to_failure(result: ValidationResult, idx: int) -> Failure:
        cat, _ = FailureTaxonomy.classify(result)
        return Failure(
            id=f"F{idx:04d}",
            gate=result.gate,
            category=cat,
            detail=result.message,
            coord=result.locations[0] if result.locations else None,
        )
