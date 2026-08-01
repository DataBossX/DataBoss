"""Policy and authorization engine.

This module encodes the non-negotiable safety principle: **an utterance is an
instruction source, not proof of authority.** Speech (or typed chat) can request
information, request analysis, and draft work. Only an authenticated approval
recorded in the ledger can authorize a consequential action.

Every gate here fails closed. A missing profile, an unknown action, or an
unparseable level all raise rather than defaulting to permissive.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from enum import Enum

from .autonomy import ALPHA_MAX_LEVEL, AutonomyLevel
from .errors import AutonomyViolation, EgressDenied, HoldActive, PolicyViolation


class AuthoritySource(str, Enum):
    """Where a claimed authorization came from."""

    SPOKEN_UTTERANCE = "SPOKEN_UTTERANCE"
    TYPED_UTTERANCE = "TYPED_UTTERANCE"
    QUOTED_DOCUMENT = "QUOTED_DOCUMENT"
    MODEL_OUTPUT = "MODEL_OUTPUT"
    AUTHENTICATED_APPROVAL = "AUTHENTICATED_APPROVAL"
    SYSTEM_POLICY = "SYSTEM_POLICY"


#: The only two sources that can authorize a consequential action. Note the
#: deliberate absence of SPOKEN_UTTERANCE, QUOTED_DOCUMENT, and MODEL_OUTPUT.
AUTHORIZING_SOURCES = frozenset(
    {AuthoritySource.AUTHENTICATED_APPROVAL, AuthoritySource.SYSTEM_POLICY}
)


class DataSensitivity(str, Enum):
    SYNTHETIC = "SYNTHETIC"
    INTERNAL = "INTERNAL"
    CLIENT_CONFIDENTIAL = "CLIENT_CONFIDENTIAL"


class RiskLevel(str, Enum):
    INFORMATIONAL = "INFORMATIONAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


#: Risk at or above this level always needs an explicit approval, regardless of
#: what the current autonomy ceiling would otherwise allow.
APPROVAL_REQUIRED_AT = RiskLevel.MEDIUM

_RISK_ORDER = {
    RiskLevel.INFORMATIONAL: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}


def risk_at_least(risk: RiskLevel, threshold: RiskLevel) -> bool:
    return _RISK_ORDER[risk] >= _RISK_ORDER[threshold]


@dataclass(frozen=True)
class PolicyProfile:
    """The operator's current standing instructions.

    Defaults are the safe end of every axis: draft-only, no client files, every
    consequential action approved, cloud allowed but never required.
    """

    autonomy_ceiling: AutonomyLevel = AutonomyLevel.DRAFT
    local_only: bool = False
    cloud_models_allowed: bool = True
    client_files_allowed: bool = False
    global_hold: bool = False
    require_approval_for_all: bool = False
    data_sensitivity: DataSensitivity = DataSensitivity.SYNTHETIC
    max_improvement_iterations: int = 3
    max_candidates: int = 5
    max_job_seconds: int = 1800
    cost_ceiling: str = "LOW"
    #: Artifact/lane IDs the operator has explicitly told the system not to touch.
    prohibited_targets: frozenset = field(default_factory=frozenset)

    def __post_init__(self):
        object.__setattr__(self, "autonomy_ceiling", AutonomyLevel.parse(self.autonomy_ceiling))
        object.__setattr__(self, "data_sensitivity", DataSensitivity(self.data_sensitivity))
        object.__setattr__(self, "prohibited_targets", frozenset(self.prohibited_targets))
        if self.autonomy_ceiling > ALPHA_MAX_LEVEL:
            raise PolicyViolation(
                "Autonomy level 4 (release / external action) is disabled in Command Brain Alpha.",
                detail={"requested_ceiling": int(self.autonomy_ceiling)},
            )
        if self.local_only and self.cloud_models_allowed:
            # local_only is the stronger statement; it always wins.
            object.__setattr__(self, "cloud_models_allowed", False)

    # -- operator mode switches ------------------------------------------
    def with_read_only(self) -> "PolicyProfile":
        return replace(self, autonomy_ceiling=AutonomyLevel.READ_ONLY_EXECUTE)

    def with_draft_only(self) -> "PolicyProfile":
        return replace(self, autonomy_ceiling=AutonomyLevel.DRAFT)

    def with_observe_only(self) -> "PolicyProfile":
        return replace(self, autonomy_ceiling=AutonomyLevel.OBSERVE)

    def with_local_only(self) -> "PolicyProfile":
        return replace(self, local_only=True, cloud_models_allowed=False)

    def with_no_cloud(self) -> "PolicyProfile":
        return replace(self, cloud_models_allowed=False)

    def with_hold(self, active: bool = True) -> "PolicyProfile":
        return replace(self, global_hold=active)

    def with_approval_for_everything(self) -> "PolicyProfile":
        return replace(self, require_approval_for_all=True)

    def with_no_client_files(self) -> "PolicyProfile":
        return replace(self, client_files_allowed=False)

    def with_prohibited_target(self, target_id: str) -> "PolicyProfile":
        return replace(self, prohibited_targets=self.prohibited_targets | {target_id})

    def to_dict(self) -> dict:
        return {
            "autonomy_ceiling": int(self.autonomy_ceiling),
            "autonomy_ceiling_name": self.autonomy_ceiling.name,
            "local_only": self.local_only,
            "cloud_models_allowed": self.cloud_models_allowed,
            "client_files_allowed": self.client_files_allowed,
            "global_hold": self.global_hold,
            "require_approval_for_all": self.require_approval_for_all,
            "data_sensitivity": self.data_sensitivity.value,
            "max_improvement_iterations": self.max_improvement_iterations,
            "max_candidates": self.max_candidates,
            "max_job_seconds": self.max_job_seconds,
            "cost_ceiling": self.cost_ceiling,
            "prohibited_targets": sorted(self.prohibited_targets),
        }


@dataclass(frozen=True)
class ActionRequest:
    """One thing the system is about to do, described in policy terms."""

    action_type: str
    required_level: AutonomyLevel
    risk: RiskLevel = RiskLevel.LOW
    mutates_state: bool = False
    external_effect: bool = False
    uses_client_files: bool = False
    remote_model: bool = False
    authority_source: AuthoritySource = AuthoritySource.TYPED_UTTERANCE
    target_ids: tuple = ()
    project_id: str | None = None
    #: Set only by ApprovalService after verifying an authenticated approval.
    approval_id: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "required_level", AutonomyLevel.parse(self.required_level))
        object.__setattr__(self, "risk", RiskLevel(self.risk))
        object.__setattr__(self, "authority_source", AuthoritySource(self.authority_source))
        object.__setattr__(self, "target_ids", tuple(self.target_ids))


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    action_type: str
    reasons: tuple
    requires_approval: bool
    effective_level: AutonomyLevel
    risk: RiskLevel

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "action_type": self.action_type,
            "reasons": list(self.reasons),
            "requires_approval": self.requires_approval,
            "effective_level": int(self.effective_level),
            "effective_level_name": self.effective_level.name,
            "risk": self.risk.value,
        }


class PolicyEngine:
    """Evaluates one :class:`ActionRequest` against the current profile."""

    def __init__(self, profile: PolicyProfile | None = None):
        self.profile = profile or PolicyProfile()

    def set_profile(self, profile: PolicyProfile) -> PolicyProfile:
        self.profile = profile
        return self.profile

    @contextmanager
    def elevated(self, level):
        """Scoped, explicit change of the operator's standing ceiling.

        This is an *operator mode switch* used by tooling and tests, not a side
        effect of approval. Approving an envelope authorizes that exact envelope;
        it never raises the mode the operator set. Execution therefore has to
        clear two independent gates — the standing ceiling and the approval —
        which is why "draft only" still blocks an approved read-only job.

        The ceiling drops back even if the block raises, and it can never exceed
        the Alpha maximum.
        """
        level = AutonomyLevel.parse(level)
        if level > ALPHA_MAX_LEVEL:
            raise PolicyViolation(
                "Autonomy level 4 cannot be granted in Command Brain Alpha.",
                detail={"requested": int(level)},
            )
        previous = self.profile
        if level > previous.autonomy_ceiling:
            self.profile = replace(previous, autonomy_ceiling=level)
        try:
            yield self.profile
        finally:
            self.profile = previous

    # -- core evaluation --------------------------------------------------
    def evaluate(self, request: ActionRequest) -> PolicyDecision:
        profile = self.profile
        reasons: list[str] = []
        allowed = True

        if request.required_level > ALPHA_MAX_LEVEL:
            reasons.append(
                "Autonomy level 4 (release / external action) is structurally disabled in Alpha."
            )
            allowed = False

        if request.external_effect:
            reasons.append(
                "External effects (publish, send, deliver, connector write) are disabled in Alpha."
            )
            allowed = False

        if request.required_level > profile.autonomy_ceiling:
            reasons.append(
                f"Requires autonomy {request.required_level.name}; "
                f"current ceiling is {profile.autonomy_ceiling.name}."
            )
            allowed = False

        if profile.global_hold and (request.mutates_state or request.required_level >= AutonomyLevel.READ_ONLY_EXECUTE):
            reasons.append("A global hold is active; only OBSERVE and DRAFT actions are permitted.")
            allowed = False

        if request.uses_client_files and not profile.client_files_allowed:
            reasons.append("Client files are excluded by the current profile.")
            allowed = False

        if request.remote_model and profile.local_only:
            reasons.append("Local-only mode: remote model endpoints are unreachable by policy.")
            allowed = False
        elif request.remote_model and not profile.cloud_models_allowed:
            reasons.append("Cloud models are disabled by the current profile.")
            allowed = False

        prohibited = [t for t in request.target_ids if t in profile.prohibited_targets]
        if prohibited:
            reasons.append(f"Operator prohibited these targets: {', '.join(sorted(prohibited))}.")
            allowed = False

        consequential = (
            request.mutates_state
            or request.external_effect
            or risk_at_least(request.risk, APPROVAL_REQUIRED_AT)
            or request.required_level >= AutonomyLevel.BOUNDED_WRITER
        )
        requires_approval = consequential or profile.require_approval_for_all

        # An utterance can never *be* the approval. If a consequential action
        # arrives claiming authority from speech, chat, a quoted document, or a
        # model, it is downgraded to "needs approval" rather than executed.
        if consequential and request.approval_id is None:
            if request.authority_source not in AUTHORIZING_SOURCES:
                reasons.append(
                    f"{request.authority_source.value} is an instruction source, not authorization; "
                    "an authenticated approval is required."
                )
                allowed = False

        if request.authority_source is AuthoritySource.QUOTED_DOCUMENT:
            reasons.append(
                "Instructions quoted from a document have no authority and were treated as content."
            )
            allowed = False

        if allowed and not reasons:
            reasons.append("Permitted under the current profile.")

        return PolicyDecision(
            allowed=allowed,
            action_type=request.action_type,
            reasons=tuple(reasons),
            requires_approval=requires_approval,
            effective_level=min(request.required_level, profile.autonomy_ceiling),
            risk=request.risk,
        )

    def enforce(self, request: ActionRequest) -> PolicyDecision:
        """Evaluate and raise on refusal."""
        decision = self.evaluate(request)
        if decision.allowed:
            return decision
        detail = {"decision": decision.to_dict()}
        joined = " ".join(decision.reasons)
        if self.profile.global_hold and "hold is active" in joined:
            raise HoldActive(joined, detail=detail)
        if "Local-only mode" in joined or "Cloud models are disabled" in joined:
            raise EgressDenied(joined, detail=detail)
        if "Requires autonomy" in joined or "level 4" in joined:
            raise AutonomyViolation(joined, detail=detail)
        raise PolicyViolation(joined, detail=detail)
