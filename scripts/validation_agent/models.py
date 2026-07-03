"""Shared, immutable data contracts for the DataBossX Validation & Repair Agent.

Every module in the system exchanges these structures.  They are intentionally
plain, fully-typed dataclasses so they serialize cleanly to JSON for the
append-only audit layer and the Streamlit dashboard.

Golden Law alignment:
    * No legal or title fact is ever invented here -- these are containers only.
    * Results carry enough provenance (sheet, cell, range) to build an
      examiner-grade escalation payload without guessing.
"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


class Severity(enum.Enum):
    """Ordered severity ladder used across gates and the failure taxonomy."""

    MEDIUM = "medium"
    HIGH = "high"
    SYSTEM_HIGH = "system_high"
    CRITICAL = "critical"
    FATAL = "fatal"

    @property
    def rank(self) -> int:
        order = {
            Severity.MEDIUM: 1,
            Severity.HIGH: 2,
            Severity.SYSTEM_HIGH: 3,
            Severity.CRITICAL: 4,
            Severity.FATAL: 5,
        }
        return order[self]


class GateStatus(enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"  # the gate itself could not be evaluated
    SKIPPED = "skipped"


class FailureCategory(enum.Enum):
    """Section 6 -- Failure Taxonomy.  The value is the canonical DB token."""

    COMPUTATIONAL_MISMATCH = "computational_mismatch"
    FORMULA_DEFECT = "formula_defect"
    BROKEN_WORKBOOK_STRUCTURE = "broken_workbook_structure"
    MISSING_SOURCE = "missing_source"
    UNVERIFIABLE_SOURCE = "unverifiable_source"
    SOURCE_LEGAL_MISMATCH = "source_legal_mismatch"
    TITLE_CHAIN_GAP = "title_chain_gap"
    RESERVATION_CARRY_FORWARD_FAILURE = "reservation_carry_forward_failure"
    OGL_WI_MISMATCH = "ogl_wi_mismatch"
    HBP_UNSUPPORTED = "hbp_unsupported"
    API_SPEND_BLOCKED = "api_spend_blocked"
    SUBPROCESS_DEPENDENCY_FAILURE = "subprocess_dependency_failure"
    UNSAFE_LEGAL_INFERENCE = "unsafe_legal_inference"


@dataclass(frozen=True)
class CellRef:
    """A precise, human-readable location inside the workbook."""

    sheet: str
    cell: Optional[str] = None
    range: Optional[str] = None

    def __str__(self) -> str:
        loc = self.sheet
        if self.cell:
            loc += f"!{self.cell}"
        elif self.range:
            loc += f"!{self.range}"
        return loc


@dataclass
class Finding:
    """A single problem discovered by a validator.

    `repairable` and `category` are assigned by the validator using the shared
    taxonomy so the RepairPlanner can segregate work without re-deriving intent.
    """

    gate_id: int
    gate_name: str
    category: FailureCategory
    severity: Severity
    message: str
    location: Optional[CellRef] = None
    subject: Optional[str] = None  # tract / instrument row / OGL / WI row
    repairable: bool = False
    escalate: bool = False
    # Machine-verifiable repair hint (e.g. the exact formula to restore).
    repair_hint: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["severity"] = self.severity.value
        d["location"] = str(self.location) if self.location else None
        return d


@dataclass
class GateResult:
    """Structured output every validator gate must return."""

    gate_id: int
    gate_name: str
    status: GateStatus
    findings: list[Finding] = field(default_factory=list)
    detail: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "gate_name": self.gate_name,
            "status": self.status.value,
            "detail": self.detail,
            "metrics": self.metrics,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class RepairAction:
    """A machine-verifiable, non-destructive workbook mutation."""

    finding_gate_id: int
    location: CellRef
    action_type: str  # "restore_formula" | "normalize_fraction" | ...
    old_value: Optional[str]
    new_formula: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["location"] = str(self.location)
        return d


@dataclass
class Escalation:
    """Section 7 -- the exhaustive human-in-the-loop payload.

    All nine required fields are mandatory; the OutputGenerator refuses to
    certify or bundle a run if any escalation is missing a field.
    """

    gate_id: int
    gate_name: str
    category: FailureCategory
    severity: Severity
    # 1..9 of the Escalation Payload Requirements:
    failed_gate: str
    location: Optional[CellRef]
    subject: str
    sources_checked: list[str]
    sources_missing: list[str]
    automated_checks_attempted: list[str]
    repair_blocked_reason: str
    recommended_examiner_action: str
    estimated_urgency: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["severity"] = self.severity.value
        d["location"] = str(self.location) if self.location else None
        return d
