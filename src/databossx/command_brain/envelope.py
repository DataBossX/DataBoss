"""TaskEnvelope drafting.

A natural-language request never becomes execution directly. It becomes a
*draft* envelope: an explicit, hashable statement of what would happen, what it
may touch, what it may not touch, which models are allowed, what has to pass,
and how to roll back. The operator reads the plain-language rendering and either
approves that exact hash or does not.

Changing any field changes ``envelope_hash``, which invalidates any approval
bound to the old hash. That is the whole point.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace

from .autonomy import AutonomyLevel
from .errors import AuthorityError
from .policy import DataSensitivity, RiskLevel
from .redaction import redact
from .util import Clock, canonical_hash, canonical_json, truncate


@dataclass(frozen=True)
class TaskEnvelope:
    task_id: str
    requesting_user: str
    original_transcript: str
    normalized_intent: str
    project_id: str | None
    goal: str
    inputs: tuple = ()
    controlling_artifacts: tuple = ()
    expected_input_hashes: tuple = ()
    expected_outputs: tuple = ()
    allowed_paths: tuple = ()
    prohibited_paths: tuple = ()
    tools: tuple = ()
    assigned_roles: tuple = ()
    model_restrictions: dict = field(default_factory=dict)
    data_sensitivity: DataSensitivity = DataSensitivity.SYNTHETIC
    autonomy_level: AutonomyLevel = AutonomyLevel.DRAFT
    approval_requirements: tuple = ()
    lease_required: bool = False
    fencing_token_required: bool = False
    timeout_seconds: int = 900
    cost_budget: str = "LOW"
    token_budget: int = 0
    retry_limit: int = 1
    validation_gates: tuple = ()
    acceptance_criteria: tuple = ()
    rollback_plan: str = ""
    stop_conditions: tuple = ()
    hold_state: str = "NONE"
    risk: RiskLevel = RiskLevel.LOW
    created_at: str = ""
    expires_at: str | None = None
    state: str = "DRAFT"

    _TUPLE_FIELDS = (
        "inputs",
        "controlling_artifacts",
        "expected_input_hashes",
        "expected_outputs",
        "allowed_paths",
        "prohibited_paths",
        "tools",
        "assigned_roles",
        "approval_requirements",
        "validation_gates",
        "acceptance_criteria",
        "stop_conditions",
    )

    def __post_init__(self):
        for name in self._TUPLE_FIELDS:
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(self, "autonomy_level", AutonomyLevel.parse(self.autonomy_level))
        object.__setattr__(self, "data_sensitivity", DataSensitivity(self.data_sensitivity))
        object.__setattr__(self, "risk", RiskLevel(self.risk))
        if self.autonomy_level >= AutonomyLevel.BOUNDED_WRITER:
            if not self.lease_required or not self.fencing_token_required:
                raise AuthorityError(
                    "A BOUNDED_WRITER envelope must require both a lease and a fencing token.",
                    detail={"task_id": self.task_id},
                )

    # -- serialisation ----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "requesting_user": self.requesting_user,
            "original_transcript": self.original_transcript,
            "normalized_intent": self.normalized_intent,
            "project_id": self.project_id,
            "goal": self.goal,
            "inputs": list(self.inputs),
            "controlling_artifacts": list(self.controlling_artifacts),
            "expected_input_hashes": list(self.expected_input_hashes),
            "expected_outputs": list(self.expected_outputs),
            "allowed_paths": list(self.allowed_paths),
            "prohibited_paths": list(self.prohibited_paths),
            "tools": list(self.tools),
            "assigned_roles": list(self.assigned_roles),
            "model_restrictions": dict(self.model_restrictions),
            "data_sensitivity": self.data_sensitivity.value,
            "autonomy_level": int(self.autonomy_level),
            "autonomy_level_name": self.autonomy_level.name,
            "approval_requirements": list(self.approval_requirements),
            "lease_required": self.lease_required,
            "fencing_token_required": self.fencing_token_required,
            "timeout_seconds": self.timeout_seconds,
            "cost_budget": self.cost_budget,
            "token_budget": self.token_budget,
            "retry_limit": self.retry_limit,
            "validation_gates": list(self.validation_gates),
            "acceptance_criteria": list(self.acceptance_criteria),
            "rollback_plan": self.rollback_plan,
            "stop_conditions": list(self.stop_conditions),
            "hold_state": self.hold_state,
            "risk": self.risk.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "state": self.state,
        }

    #: Fields to_dict() derives for display; they are not constructor arguments.
    _DERIVED_KEYS = ("autonomy_level_name",)

    @classmethod
    def from_dict(cls, payload: dict) -> "TaskEnvelope":
        fields = {key: value for key, value in payload.items() if key not in cls._DERIVED_KEYS}
        return cls(**fields)

    def scope_payload(self) -> dict:
        """The subset an approval is bound to. Excludes mutable bookkeeping."""
        payload = self.to_dict()
        for volatile in ("state", "created_at"):
            payload.pop(volatile, None)
        return payload

    @property
    def envelope_hash(self) -> str:
        return canonical_hash(self.scope_payload())

    def phone_safe(self) -> dict:
        """Redacted view: no absolute paths, no secrets. Safe for a phone."""
        return redact(self.to_dict())

    def with_state(self, state: str) -> "TaskEnvelope":
        return replace(self, state=state)

    # -- explanation ------------------------------------------------------
    def plain_language(self) -> str:
        """One paragraph the operator can act on without reading the JSON."""
        roles = ", ".join(self.assigned_roles) or "no agents"
        models = self.model_restrictions or {}
        cloud = "disabled" if models.get("local_only") or not models.get("cloud_allowed", True) else "allowed"
        writes = "No client artifact will be modified."
        if self.autonomy_level >= AutonomyLevel.BOUNDED_WRITER:
            allowed = ", ".join(self.allowed_paths) or "an authorized worktree"
            writes = f"Writes are confined to {allowed} under a single-writer lease."
        minutes = max(1, round(self.timeout_seconds / 60))
        lines = [
            f"You asked DataBossX to {self.goal.rstrip('.')}.",
            f"Agents: {roles}. Autonomy: {self.autonomy_level.name}.",
            writes,
            f"Estimated runtime cap: {minutes} minutes. Cloud models: {cloud}.",
        ]
        if self.prohibited_paths:
            lines.append(f"Explicitly off limits: {', '.join(self.prohibited_paths)}.")
        if self.approval_requirements:
            lines.append(f"Requires approval: {', '.join(self.approval_requirements)}.")
        if self.hold_state != "NONE":
            lines.append(f"Hold state: {self.hold_state}.")
        lines.append("Start?")
        return " ".join(lines)


class EnvelopeDrafter:
    """Builds envelopes from a plan and persists the draft."""

    def __init__(self, store, clock: Clock | None = None):
        self.store = store
        self.clock = clock or store.clock

    def draft(
        self,
        *,
        requesting_user: str,
        transcript: str,
        normalized_intent: str,
        goal: str,
        project_id: str | None = None,
        autonomy_level: AutonomyLevel = AutonomyLevel.DRAFT,
        plan_id: str | None = None,
        ttl_seconds: int = 3600,
        **overrides,
    ) -> TaskEnvelope:
        task_id = self.store.new_id("task")
        envelope = TaskEnvelope(
            task_id=task_id,
            requesting_user=requesting_user,
            original_transcript=truncate(transcript, 2000),
            normalized_intent=normalized_intent,
            project_id=project_id,
            goal=goal,
            autonomy_level=autonomy_level,
            created_at=self.clock.now_iso(),
            expires_at=self.clock.plus_iso(ttl_seconds),
            **overrides,
        )
        draft_id = self.store.new_id("draft")
        payload = envelope.to_dict()
        self.store.execute(
            """
            INSERT INTO cb_task_drafts (draft_id, plan_id, project_id, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (draft_id, plan_id, project_id, canonical_json(payload), envelope.created_at),
        )
        self.store.execute(
            """
            INSERT INTO cb_task_envelopes (
                envelope_id, draft_id, project_id, envelope_hash, payload_json,
                state, autonomy_level, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?)
            """,
            (
                task_id,
                draft_id,
                project_id,
                envelope.envelope_hash,
                canonical_json(payload),
                int(envelope.autonomy_level),
                envelope.created_at,
                envelope.expires_at,
            ),
        )
        self.store.audit(
            "envelope.drafted",
            "task_envelope",
            task_id,
            {
                "envelope_hash": envelope.envelope_hash,
                "autonomy_level": int(envelope.autonomy_level),
                "goal": goal,
                "roles": list(envelope.assigned_roles),
                "tools": list(envelope.tools),
            },
            project_id=project_id,
        )
        return envelope

    def load(self, envelope_id: str) -> TaskEnvelope | None:
        row = self.store.fetchone(
            "SELECT payload_json FROM cb_task_envelopes WHERE envelope_id = ?", (envelope_id,)
        )
        if row is None:
            return None
        return TaskEnvelope.from_dict(json.loads(row["payload_json"]))
