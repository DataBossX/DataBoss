"""EvoSwarm Pydantic v2 strict schemas — the single source of truth.

Every cross-boundary payload (graph state, agent I/O, tool results) is one of
these models. `model_config = ConfigDict(strict=True, extra="forbid")` means no
coercion and no silent extra keys: malformed data fails loudly at the edge
instead of corrupting the swarm state mid-run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

STRICT = ConfigDict(strict=True, extra="forbid", frozen=False)

# A 14-digit Public Land Survey System legal: SS-TTT-RRR style packed key.
PLSSKey = Annotated[str, StringConstraints(pattern=r"^\d{2}-\d{1,2}[NS]-\d{1,2}[EW]$")]
County = Annotated[str, StringConstraints(min_length=3, max_length=40)]

# Money/quantities arrive over HTTP as JSON (strings or numbers). At that trust
# boundary we must accept the JSON type system, so these Decimal fields opt out
# of strict coercion-blocking (field-level strict=False overrides the model's
# strict=True) while every range/precision constraint still applies.
WireDecimal = Annotated[Decimal, Field(strict=False)]


class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    INTAKE = "intake"
    PARSER = "parser"
    OCR = "ocr"
    TITLE = "title_examiner"
    ROYALTY = "royalty_analyst"
    GEO = "geo_analyst"
    VALUATION = "valuation"
    OUTREACH = "outreach"
    COMPLIANCE = "compliance"
    CRITIC = "critic"
    EVOLVER = "evolver"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    NEEDS_REVIEW = "needs_review"
    DONE = "done"
    FAILED = "failed"


class Money(BaseModel):
    """USD with explicit Decimal precision — never float for dollars."""

    model_config = STRICT
    amount: WireDecimal = Field(ge=Decimal("0"))
    currency: Literal["USD"] = "USD"


class AgentSpec(BaseModel):
    """The contract a .yaml spec deserializes into. Validates the whole fleet."""

    model_config = STRICT
    name: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{1,30}$")]
    role: AgentRole
    model: str
    temperature: float = Field(ge=0.0, le=2.0, default=0.0)
    max_tokens: int = Field(gt=0, le=200_000, default=8_192)
    tools: list[str] = Field(default_factory=list)
    system_prompt_ref: str
    sub_team: list[str] = Field(default_factory=list)
    replicas: int = Field(ge=1, le=50, default=1)
    cost_ceiling_usd: Decimal = Field(ge=Decimal("0"), default=Decimal("5.00"))


class Evidence(BaseModel):
    """A single citable fact a downstream agent or human can audit."""

    model_config = STRICT
    source: str
    document_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    quote: str
    confidence: float = Field(ge=0.0, le=1.0)


class Task(BaseModel):
    """The unit of work that flows through the graph state."""

    model_config = STRICT
    id: UUID = Field(default_factory=uuid4)
    county: County
    legal: PLSSKey
    objective: str
    status: TaskStatus = TaskStatus.QUEUED
    assigned_to: AgentRole | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoyaltyInput(BaseModel):
    model_config = STRICT
    net_mineral_acres: WireDecimal = Field(gt=Decimal("0"))
    spacing_unit_acres: WireDecimal = Field(gt=Decimal("0"))
    royalty_rate: WireDecimal = Field(gt=Decimal("0"), le=Decimal("0.5"))
    monthly_production_bbl: WireDecimal = Field(ge=Decimal("0"))
    price_per_bbl: Money


class RoyaltyResult(BaseModel):
    model_config = STRICT
    decimal_interest: Decimal
    gross_monthly: Money
    net_monthly: Money
    explanation: str


class SwarmState(BaseModel):
    """LangGraph channel payload. Strict so a bad node can't poison the run."""

    model_config = STRICT
    task: Task
    scratch: dict[str, Any] = Field(default_factory=dict)
    cost_spent_usd: Decimal = Field(default=Decimal("0"))
    review_required: bool = False
    history: list[str] = Field(default_factory=list)
