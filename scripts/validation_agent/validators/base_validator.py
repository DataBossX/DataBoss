"""Validator framework with typed result objects."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

# Status vocabulary.
PASS = "PASS"
FAIL = "FAIL"
ESCALATE = "ESCALATE"
ERROR = "ERROR"

SEVERITY_INFO = "info"
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
SEVERITY_CRITICAL = "critical"


@dataclass
class ValidationResult:
    gate_name: str
    status: str
    severity: str = SEVERITY_INFO
    repairable: bool = False
    affected_sheet: str | None = None
    affected_cell_or_range: str | None = None
    affected_subject: str | None = None
    evidence: Any = None
    reason: str = ""
    recommended_action: str = ""
    confidence: float = 1.0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def ok(self) -> bool:
        return self.status == PASS


class BaseValidator:
    """Base class. Subclasses implement ``run`` and set ``gate_name``."""

    gate_name: str = "UnnamedGate"

    def __init__(self, settings=None):
        self.settings = settings

    def run(self, context: dict) -> list[ValidationResult]:  # pragma: no cover
        raise NotImplementedError

    # Helpers for building results with this gate's name attached.
    def _pass(self, **kw: Any) -> ValidationResult:
        return ValidationResult(gate_name=self.gate_name, status=PASS, **kw)

    def _fail(self, **kw: Any) -> ValidationResult:
        return ValidationResult(gate_name=self.gate_name, status=FAIL, **kw)

    def _escalate(self, **kw: Any) -> ValidationResult:
        return ValidationResult(gate_name=self.gate_name, status=ESCALATE, **kw)

    def _error(self, **kw: Any) -> ValidationResult:
        return ValidationResult(gate_name=self.gate_name, status=ERROR, **kw)
