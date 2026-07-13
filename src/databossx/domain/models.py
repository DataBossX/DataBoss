"""Pydantic v2 domain models for every entity in the DataBossX build plan.

These models are the canonical, evidence-grounded representation of the
core kernel entities (projects, sources, assets, claims, tasks, review,
tooling, audit) plus the title-product extensions (tracts, instruments,
chain of title, interest ledger, exceptions, workbook candidates).

Design rules enforced here:
  * Value objects (immutable facts once recorded) use
    ``ConfigDict(frozen=True)``.
  * Mutable entities (things whose lifecycle state changes over time, e.g.
    ``Task``, ``SourceSnapshot``, ``Conflict``) use
    ``ConfigDict(frozen=False)``.
  * All identifiers are ``str`` (expected to be UUID4 values minted by
    callers).
  * All datetimes are timezone-aware UTC.
  * Interests / fractions are represented as integer numerator/denominator
    pairs, never bare floats, to preserve exact rational math.
  * Credentials are never modeled directly -- only opaque
    ``credential_ref`` pointers into an external secret store.
"""

from __future__ import annotations

import warnings
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ``ToolDefinition.schema_json`` intentionally reuses this name (it is the
# field name specified by the build plan) even though pydantic v1 exposed a
# deprecated ``BaseModel.schema_json()`` method of the same name. This does
# not affect behavior in pydantic v2; silence the benign shadowing warning.
warnings.filterwarnings(
    "ignore",
    message='Field name "schema_json" in "ToolDefinition" shadows an attribute',
    category=UserWarning,
)

__all__ = [
    # Core evidence & memory
    "Project",
    "SourceConnection",
    "SourceSnapshot",
    "Asset",
    "AssetVersion",
    "DerivedArtifact",
    "EvidenceSpan",
    "Claim",
    "ClaimSupport",
    "Conflict",
    # Work entities
    "WorkflowDefinition",
    "Run",
    "Task",
    "TaskDependency",
    "TaskAttempt",
    "TaskLease",
    "WorkerCapability",
    "ReviewGate",
    "ReviewDecision",
    "Approval",
    "ArtifactVersion",
    "ModelRouteDecision",
    "ToolDefinition",
    "ToolRun",
    "AuditEvent",
    # Title extensions
    "TitleProject",
    "Jurisdiction",
    "Tract",
    "Instrument",
    "InstrumentParty",
    "RecordingReference",
    "ChainLink",
    "InterestLedgerEntry",
    "TitleException",
    "CurativeItem",
    "WorkbookCandidate",
]

# ---------------------------------------------------------------------------
# Core evidence & memory
# ---------------------------------------------------------------------------


class Project(BaseModel):
    """A unit of engagement work with jurisdiction and policy scoping."""

    model_config = ConfigDict(frozen=False)

    id: str
    name: str
    jurisdiction: str
    policy_set: str
    confidentiality: str
    lifecycle_state: str
    created_at: datetime
    updated_at: datetime


class SourceConnection(BaseModel):
    """A configured pointer to an external or local source of documents.

    Never holds the credential itself -- only ``credential_ref``, an opaque
    pointer resolved by a secret store at connector runtime.
    """

    model_config = ConfigDict(frozen=False)

    id: str
    project_id: str
    provider: str
    root_path: str
    capabilities: list[str] = Field(default_factory=list)
    credential_ref: Optional[str] = None


class SourceSnapshot(BaseModel):
    """A point-in-time scan result of a ``SourceConnection``."""

    model_config = ConfigDict(frozen=False)

    id: str
    connection_id: str
    cursor: Optional[str] = None
    scan_time: datetime
    completeness: str
    manifest_hash: str
    status: str


class Asset(BaseModel):
    """A logical document identified within a project/snapshot."""

    model_config = ConfigDict(frozen=False)

    id: str
    project_id: str
    snapshot_id: str
    logical_path: str
    mime_type: str
    created_at: datetime


class AssetVersion(BaseModel):
    """An immutable, content-addressed version of an ``Asset``."""

    model_config = ConfigDict(frozen=True)

    id: str
    asset_id: str
    locator: str
    provider_version: Optional[str] = None
    byte_hash: str
    size_bytes: int
    custody_time: datetime
    vault_path: str


class DerivedArtifact(BaseModel):
    """An artifact derived from one or more asset versions (append-only)."""

    model_config = ConfigDict(frozen=True)

    id: str
    parent_asset_version_ids: list[str]
    recipe_version: str
    artifact_type: str
    vault_path: str
    byte_hash: str
    created_at: datetime


class EvidenceSpan(BaseModel):
    """A precise, citable location within an asset version."""

    model_config = ConfigDict(frozen=True)

    id: str
    asset_version_id: str
    page_or_sheet: Optional[str] = None
    row_or_region: Optional[str] = None
    text_excerpt: str
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    bbox_json: Optional[str] = None
    created_at: datetime


ClaimValueState = Literal[
    "proved",
    "qualified",
    "assumed",
    "missing",
    "unknown",
    "inferred",
    "externally_researched",
]


class Claim(BaseModel):
    """An asserted fact with a provenance-bound confidence state.

    Claims are revised, not mutated: a revision creates a new ``Claim`` row
    pointing back at the prior one via ``revision_of``.
    """

    model_config = ConfigDict(frozen=False)

    id: str
    project_id: str
    subject: str
    predicate: str
    value: str
    value_state: ClaimValueState
    confidence: float = Field(ge=0.0, le=1.0)
    source_span_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    revised_at: Optional[datetime] = None
    revision_of: Optional[str] = None


class ClaimSupport(BaseModel):
    """Links a ``Claim`` to a supporting ``EvidenceSpan``."""

    model_config = ConfigDict(frozen=True)

    id: str
    claim_id: str
    span_id: str
    support_rule_version: str


ConflictMateriality = Literal["high", "medium", "low"]


class Conflict(BaseModel):
    """A detected disagreement between claims requiring resolution."""

    model_config = ConfigDict(frozen=False)

    id: str
    project_id: str
    claim_ids: list[str]
    materiality: ConflictMateriality
    resolution_note: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Work entities
# ---------------------------------------------------------------------------


class WorkflowDefinition(BaseModel):
    """A named, versioned workflow template."""

    model_config = ConfigDict(frozen=False)

    id: str
    name: str
    version: str
    description: str


class Run(BaseModel):
    """An instantiation of a ``WorkflowDefinition`` against a ``Project``."""

    model_config = ConfigDict(frozen=False)

    id: str
    workflow_id: str
    project_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    metadata_json: Optional[str] = None


TaskStatus = Literal[
    "PLANNED",
    "BLOCKED",
    "READY",
    "LEASED",
    "RUNNING",
    "WAITING_HUMAN",
    "SUCCEEDED",
    "FAILED_RETRYABLE",
    "FAILED_TERMINAL",
]


class Task(BaseModel):
    """A unit of work within a ``Run``, tracked through a state machine."""

    model_config = ConfigDict(frozen=False)

    id: str
    run_id: str
    name: str
    status: TaskStatus
    worker_type: str
    input_json: str
    output_json: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    lease_expires_at: Optional[datetime] = None
    attempt_count: int = 0


class TaskDependency(BaseModel):
    """A directed edge in the task graph: upstream must succeed first."""

    model_config = ConfigDict(frozen=True)

    upstream_task_id: str
    downstream_task_id: str


class TaskAttempt(BaseModel):
    """A single execution attempt of a ``Task``."""

    model_config = ConfigDict(frozen=False)

    id: str
    task_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    outcome: Optional[str] = None
    error_message: Optional[str] = None


class TaskLease(BaseModel):
    """A time-bounded exclusive claim on a ``Task`` held by a worker."""

    model_config = ConfigDict(frozen=False)

    id: str
    task_id: str
    worker_id: str
    granted_at: datetime
    expires_at: datetime
    heartbeat_at: Optional[datetime] = None


class WorkerCapability(BaseModel):
    """A declared capability of a worker type."""

    model_config = ConfigDict(frozen=False)

    id: str
    worker_type: str
    capability: str
    version: str
    description: str


class ReviewGate(BaseModel):
    """A human review checkpoint attached to a task."""

    model_config = ConfigDict(frozen=False)

    id: str
    task_id: str
    gate_type: str
    required_role: str
    prompt_for_reviewer: str


ReviewDecisionKind = Literal["approved", "rejected", "deferred"]


class ReviewDecision(BaseModel):
    """A reviewer's decision at a ``ReviewGate``."""

    model_config = ConfigDict(frozen=True)

    id: str
    gate_id: str
    reviewer: str
    decision: ReviewDecisionKind
    note: Optional[str] = None
    decided_at: datetime


class Approval(BaseModel):
    """Binds a review decision to the exact artifact hash it approved."""

    model_config = ConfigDict(frozen=True)

    id: str
    gate_id: str
    decision_id: str
    artifact_hash: str
    artifact_type: str
    approved_by: str
    approved_at: datetime
    expires_at: Optional[datetime] = None


class ArtifactVersion(BaseModel):
    """A version of a produced artifact, optionally approved for release."""

    model_config = ConfigDict(frozen=False)

    id: str
    artifact_type: str
    project_id: str
    vault_path: str
    byte_hash: str
    created_at: datetime
    approved: bool = False
    approval_id: Optional[str] = None


class ModelRouteDecision(BaseModel):
    """A record of which model/provider a task was routed to, and why."""

    model_config = ConfigDict(frozen=True)

    id: str
    task_id: str
    provider: str
    model_name: str
    reason: str
    input_hash: str
    created_at: datetime


ToolPrivilegeLevel = Literal["read_only", "local_write", "external_write"]


class ToolDefinition(BaseModel):
    """A registered tool a worker may invoke, capped at a privilege level."""

    model_config = ConfigDict(frozen=False)

    id: str
    name: str
    version: str
    description: str
    schema_json: str
    max_privilege_level: ToolPrivilegeLevel


class ToolRun(BaseModel):
    """A single invocation of a ``ToolDefinition`` within a task."""

    model_config = ConfigDict(frozen=False)

    id: str
    task_id: str
    tool_id: str
    input_hash: str
    output_hash: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str


class AuditEvent(BaseModel):
    """An immutable, append-only record of a significant system event."""

    model_config = ConfigDict(frozen=True)

    id: str
    event_type: str
    actor: Optional[str] = None
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    artifact_hash: Optional[str] = None
    payload_json: Optional[str] = None
    occurred_at: datetime


# ---------------------------------------------------------------------------
# Title extensions
# ---------------------------------------------------------------------------


class TitleProject(Project):
    """A ``Project`` specialized for title research over a legal tract."""

    model_config = ConfigDict(frozen=False)

    section: str
    township: str
    range: str
    county: str
    state: str
    search_from_date: Optional[datetime] = None
    search_to_date: Optional[datetime] = None


class Jurisdiction(BaseModel):
    """A county/state jurisdiction and its recording/search standards."""

    model_config = ConfigDict(frozen=False)

    id: str
    state: str
    county: str
    search_standards_url: Optional[str] = None


class Tract(BaseModel):
    """A legal tract of land under title examination."""

    model_config = ConfigDict(frozen=False)

    id: str
    project_id: str
    label: str
    legal_description: str
    gross_acres_numerator: Optional[int] = None
    gross_acres_denominator: Optional[int] = None


class Instrument(BaseModel):
    """A recorded legal instrument (deed, lease, assignment, etc.)."""

    model_config = ConfigDict(frozen=False)

    id: str
    project_id: str
    asset_version_id: str
    instrument_type: str
    effective_date: Optional[datetime] = None
    execution_date: Optional[datetime] = None
    recording_date: Optional[datetime] = None
    book: Optional[str] = None
    page: Optional[str] = None
    instrument_no: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None


InstrumentPartyRole = Literal[
    "grantor",
    "grantee",
    "lessor",
    "lessee",
    "assignor",
    "assignee",
    "decedent",
    "other",
]


class InstrumentParty(BaseModel):
    """A party named on an ``Instrument`` and their role."""

    model_config = ConfigDict(frozen=False)

    id: str
    instrument_id: str
    role: InstrumentPartyRole
    name: str
    normalized_name: Optional[str] = None


class RecordingReference(BaseModel):
    """The recording-office citation for an ``Instrument``."""

    model_config = ConfigDict(frozen=True)

    id: str
    instrument_id: str
    book: str
    page: str
    county: str
    state: str
    recording_date: datetime


class ChainLink(BaseModel):
    """An edge in the chain of title connecting two parties via an instrument."""

    model_config = ConfigDict(frozen=False)

    id: str
    project_id: str
    from_party: Optional[str] = None
    to_party: Optional[str] = None
    instrument_id: str
    link_type: str
    tract_id: Optional[str] = None
    effective_date: Optional[datetime] = None


InterestType = Literal["WI", "NRI", "ORRI", "royalty", "NMA", "other"]


class InterestLedgerEntry(BaseModel):
    """An exact rational (numerator/denominator) interest ledger entry.

    Interests are never stored as bare floats; ``as_decimal`` is a derived
    convenience view only.
    """

    model_config = ConfigDict(frozen=False)

    id: str
    project_id: str
    tract_id: str
    instrument_id: str
    interest_type: InterestType
    numerator: int
    denominator: int
    as_of_date: Optional[datetime] = None
    notes: Optional[str] = None

    @property
    def as_decimal(self) -> float:
        """Return the interest as a float (numerator / denominator)."""
        return self.numerator / self.denominator


TitleExceptionSeverity = Literal["fatal", "material", "minor"]
TitleExceptionStatus = Literal["open", "curative_pending", "waived", "resolved"]


class TitleException(BaseModel):
    """A defect in title requiring curative action or waiver."""

    model_config = ConfigDict(frozen=False)

    id: str
    project_id: str
    exception_type: str
    description: str
    instruments_affected: list[str] = Field(default_factory=list)
    severity: TitleExceptionSeverity
    status: TitleExceptionStatus


CurativeItemStatus = Literal["open", "in_progress", "complete"]


class CurativeItem(BaseModel):
    """A tracked action required to cure a ``TitleException``."""

    model_config = ConfigDict(frozen=False)

    id: str
    exception_id: str
    action_required: str
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    status: CurativeItemStatus


class WorkbookCandidate(BaseModel):
    """A candidate control workbook proposed for a project, pending selection."""

    model_config = ConfigDict(frozen=False)

    id: str
    project_id: str
    asset_version_id: str
    candidate_label: str
    structural_score: Optional[float] = None
    evidence_score: Optional[float] = None
    selected: bool = False
    selected_by: Optional[str] = None
    selected_at: Optional[datetime] = None
    superseded_by: Optional[str] = None
