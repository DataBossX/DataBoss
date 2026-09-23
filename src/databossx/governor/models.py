from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


HARD_VETOES = (
    "client_evidence",
    "workbook_mutation",
    "external_release",
    "second_control_plane",
    "secret_exposure",
    "history_rewrite",
    "auto_merge",
    "permission_expansion",
)


@dataclass(frozen=True)
class ImprovementProposal:
    proposal_id: str
    title: str
    evidence: list[str]
    value_score: float
    risk_score: float
    cost_score: float
    reversibility: str
    confidence: float
    autonomy_level: str
    vetoes: list[str] = field(default_factory=list)
    status: str = "proposed"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskEnvelope:
    envelope_id: str
    proposal_id: str
    base_commit: str
    inputs: list[str]
    capabilities: list[str]
    allowlist: list[str]
    budgets: dict[str, int]
    tests: list[str]
    autonomy_level: str
    envelope_hash: str
    state: str = "COMPILED"


@dataclass(frozen=True)
class CycleReceipt:
    receipt_id: str
    envelope_hash: str
    outcome: str
    payload: dict[str, Any]
