"""Typed validator base, ValidationResult, and Escalation models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from core.enums import FailureCategory, GateStatus, Severity, Urgency


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class ValidationResult(BaseModel):
    """Immutable-ish result of a single gate evaluation."""

    gate_name: str
    status: GateStatus
    severity: Severity = Severity.INFO
    repairable: bool = False
    affected_sheet: Optional[str] = None
    affected_cell_or_range: Optional[str] = None
    affected_subject: Optional[str] = None
    evidence: Optional[str] = None
    reason: Optional[str] = None
    recommended_action: Optional[str] = None
    confidence: float = 1.0
    failure_category: Optional[FailureCategory] = None
    created_at: str = Field(default_factory=_now)

    def as_row(self) -> Dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "status": self.status.value,
            "severity": self.severity.value,
            "repairable": 1 if self.repairable else 0,
            "affected_sheet": self.affected_sheet,
            "affected_cell_or_range": self.affected_cell_or_range,
            "affected_subject": self.affected_subject,
            "evidence": self.evidence,
            "reason": self.reason,
            "recommended_action": self.recommended_action,
            "confidence": float(self.confidence),
            "failure_category": self.failure_category.value
            if self.failure_category
            else None,
            "created_at": self.created_at,
        }

    @property
    def passed(self) -> bool:
        return self.status == GateStatus.PASS

    @property
    def needs_escalation(self) -> bool:
        return self.status == GateStatus.ESCALATE


class Escalation(BaseModel):
    """A complete, examiner-ready escalation packet."""

    failed_gate: str
    workbook_location: Optional[str] = None
    subject: Optional[str] = None
    sources_checked: List[str] = Field(default_factory=list)
    sources_missing: List[str] = Field(default_factory=list)
    checks_attempted: List[str] = Field(default_factory=list)
    reason_repair_blocked: Optional[str] = None
    recommended_examiner_action: Optional[str] = None
    urgency: Urgency = Urgency.HIGH
    failure_category: Optional[FailureCategory] = None
    created_at: str = Field(default_factory=_now)

    def as_row(self) -> Dict[str, Any]:
        return {
            "failed_gate": self.failed_gate,
            "workbook_location": self.workbook_location,
            "subject": self.subject,
            "sources_checked": "; ".join(self.sources_checked) or None,
            "sources_missing": "; ".join(self.sources_missing) or None,
            "checks_attempted": "; ".join(self.checks_attempted) or None,
            "reason_repair_blocked": self.reason_repair_blocked,
            "recommended_examiner_action": self.recommended_examiner_action,
            "urgency": self.urgency.value,
            "failure_category": self.failure_category.value
            if self.failure_category
            else None,
            "created_at": self.created_at,
        }


class ValidatorBase:
    """Base class for all gates.

    Subclasses set ``gate_name`` and implement ``validate(context)`` returning a
    list of ``ValidationResult``. The ``context`` is a plain dict assembled by
    the orchestrator (manifest, classification, workbook path, settings, etc.).
    """

    gate_name: str = "UnnamedGate"

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:  # noqa: D401
        raise NotImplementedError

    # convenience constructors ---------------------------------------- #
    def _passed(self, **kwargs: Any) -> ValidationResult:
        return ValidationResult(
            gate_name=self.gate_name, status=GateStatus.PASS, **kwargs
        )

    def _failed(self, **kwargs: Any) -> ValidationResult:
        kwargs.setdefault("severity", Severity.HIGH)
        return ValidationResult(
            gate_name=self.gate_name, status=GateStatus.FAIL, **kwargs
        )

    def _escalate(self, **kwargs: Any) -> ValidationResult:
        kwargs.setdefault("severity", Severity.HIGH)
        return ValidationResult(
            gate_name=self.gate_name, status=GateStatus.ESCALATE, **kwargs
        )

    def _skip(self, reason: str, **kwargs: Any) -> ValidationResult:
        return ValidationResult(
            gate_name=self.gate_name,
            status=GateStatus.SKIP,
            severity=Severity.INFO,
            reason=reason,
            **kwargs,
        )
