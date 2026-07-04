"""Validator framework: typed result objects and a base class."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

PASS, FAIL, ESCALATE, ERROR = "PASS", "FAIL", "ESCALATE", "ERROR"
SEV_INFO, SEV_LOW, SEV_MED, SEV_HIGH, SEV_FATAL = "INFO", "LOW", "MEDIUM", "HIGH", "FATAL"


@dataclass
class ValidationResult:
    gate_name: str
    status: str                      # PASS / FAIL / ESCALATE / ERROR
    severity: str = SEV_MED
    repairable: bool = False
    affected_sheet: Optional[str] = None
    affected_cell_or_range: Optional[str] = None
    affected_subject: Optional[str] = None
    evidence: Any = None
    reason: str = ""
    recommended_action: str = ""
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def ok(self) -> bool:
        return self.status == PASS


class BaseValidator:
    gate_name = "base"

    def __init__(self, manifest: Optional[Dict] = None, classifications=None,
                 workbook_path: Optional[str] = None, config: Optional[Dict] = None):
        self.manifest = manifest or {}
        self.classifications = classifications or []
        self.workbook_path = workbook_path
        self.config = config or {}

    def run(self) -> List[ValidationResult]:  # pragma: no cover - overridden
        raise NotImplementedError

    # helpers
    def _result(self, status: str, **kw) -> ValidationResult:
        return ValidationResult(gate_name=self.gate_name, status=status, **kw)
