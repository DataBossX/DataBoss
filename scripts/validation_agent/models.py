"""Typed core vocabulary shared across every component.

Stdlib dataclasses + enums are used deliberately: the module must run on the
DataBossX host and in CI without a third-party model dependency. All models are
JSON-serialisable via :func:`to_jsonable` for the append-only audit log.
"""
from __future__ import annotations

import dataclasses
import enum
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class Severity(enum.Enum):
    INFO = "INFO"
    WARN = "WARN"
    FAIL = "FAIL"


class RiskClass(enum.Enum):
    SAFE = "SAFE"
    NEEDS_SOURCE = "NEEDS_SOURCE"
    UNSAFE = "UNSAFE"


class GateId(enum.Enum):
    G1_CONSERVATION = "G1_CONSERVATION"
    G2_FOOTING = "G2_FOOTING"
    G3_CHAIN = "G3_CHAIN"
    G4_INSTRUMENT = "G4_INSTRUMENT"
    G5_OGL = "G5_OGL"


class FailureCategory(enum.Enum):
    COMPUTATION_CONSERVATION = "COMPUTATION_CONSERVATION"
    COMPUTATION_FOOTING = "COMPUTATION_FOOTING"
    FORMULA_ERROR = "FORMULA_ERROR"
    XML_DAMAGE = "XML_DAMAGE"
    TITLE_GAP_ORPHAN = "TITLE_GAP_ORPHAN"
    TITLE_GAP_CHAIN = "TITLE_GAP_CHAIN"
    PROVENANCE_MISSING = "PROVENANCE_MISSING"
    REGISTER_PHANTOM_OGL = "REGISTER_PHANTOM_OGL"
    REGISTER_MISMATCH = "REGISTER_MISMATCH"
    SPEND_CAP = "SPEND_CAP"


class SheetKind(enum.Enum):
    TRACT_GRID = "TRACT_GRID"
    OGL_REGISTER = "OGL_REGISTER"
    RUNSHEET = "RUNSHEET"
    WI = "WI"
    WELL = "WELL"
    OVERVIEW = "OVERVIEW"
    PLAT = "PLAT"
    RAWDATA = "RAWDATA"
    OTHER = "OTHER"


class LoopState(enum.Enum):
    INGESTED = "INGESTED"
    VALIDATING = "VALIDATING"
    ROUTING = "ROUTING"
    REPAIRING = "REPAIRING"
    RECALC = "RECALC"
    ESCALATED = "ESCALATED"
    CERTIFIED = "CERTIFIED"
    HALTED = "HALTED"


class SourceKind(enum.Enum):
    RAWDATA = "rawdata"
    OKCR_IMAGE = "okcr_image"
    INDEX_PAGE = "index_page"
    FORMULA = "formula"
    PRIOR_VERSION = "prior_version"


# --------------------------------------------------------------------------- #
# Value objects
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Coord:
    sheet: str
    cell: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.sheet}!{self.cell}"


@dataclass(frozen=True)
class SourceRef:
    kind: SourceKind
    locator: str
    sha256: Optional[str] = None


@dataclass
class ValidationResult:
    gate: GateId
    passed: bool
    severity: Severity
    message: str
    locations: list[Coord] = field(default_factory=list)
    metric: Optional[float] = None
    expected: Optional[float] = None


@dataclass
class FixPlan:
    strategy_id: str
    risk: RiskClass
    target: Coord
    before: Any
    after: Any
    justification: str
    source_refs: list[SourceRef] = field(default_factory=list)


@dataclass
class Failure:
    id: str
    gate: GateId
    category: FailureCategory
    detail: str
    coord: Optional[Coord] = None
    proposed_fix: Optional[FixPlan] = None


@dataclass
class GateScore:
    gate: GateId
    passed: bool
    failures: int
    worst: Severity


@dataclass
class Scorecard:
    scores: dict[GateId, GateScore]

    @property
    def all_pass(self) -> bool:
        return all(s.passed for s in self.scores.values())

    @property
    def total_failures(self) -> int:
        return sum(s.failures for s in self.scores.values())


@dataclass
class AuditEntry:
    run_id: str
    actor: str
    action: str
    result: str
    gate: Optional[GateId] = None
    coord: Optional[Coord] = None
    before: Any = None
    after: Any = None
    risk: Optional[RiskClass] = None
    source_refs: list[SourceRef] = field(default_factory=list)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class EscalationTicket:
    run_id: str
    gate: GateId
    category: FailureCategory
    reason: str
    version: int
    failures: list[Failure] = field(default_factory=list)
    would_be_value: Any = None
    empty_source_set: bool = True
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RunContext:
    run_id: str
    source_path: str
    workdir: str
    version: int = 0
    spend_used: Decimal = Decimal("0.00")
    state: LoopState = LoopState.INGESTED


# --------------------------------------------------------------------------- #
# Serialisation helpers (for the JSON columns in the audit DB)
# --------------------------------------------------------------------------- #
def to_jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses / enums / Decimals to JSON-safe values."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, Coord):
        return str(obj)
    if dataclasses.is_dataclass(obj):
        return {k: to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    return str(obj)


def dumps(obj: Any) -> str:
    return json.dumps(to_jsonable(obj), separators=(",", ":"), sort_keys=True)
