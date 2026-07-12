"""Provider-neutral, offline policy enforcement and blind candidate scoring."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class PolicyStatus(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ProviderPolicy:
    provider: str
    enabled: bool = False
    allowed_modalities: frozenset[str] = field(default_factory=frozenset)
    max_pages: int = 0
    max_cost: float = 0.0
    manual_approval_required: bool = True

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider name is required")
        if self.max_pages < 0 or self.max_cost < 0:
            raise ValueError("provider limits cannot be negative")


@dataclass(frozen=True)
class TournamentConfig:
    providers: tuple[ProviderPolicy, ...]
    required_schema_fields: tuple[str, ...] = ()
    score_weights: Mapping[str, int] = field(
        default_factory=lambda: {
            "evidence": 30,
            "citation": 20,
            "schema": 20,
            "legal": 15,
            "math": 15,
        }
    )

    def __post_init__(self) -> None:
        names = [provider.provider for provider in self.providers]
        if len(set(names)) != len(names):
            raise ValueError("provider policies must be unique")
        if set(self.score_weights) != {"evidence", "citation", "schema", "legal", "math"}:
            raise ValueError("score weights must cover evidence/citation/schema/legal/math")
        if any(value < 0 for value in self.score_weights.values()):
            raise ValueError("score weights cannot be negative")


@dataclass(frozen=True)
class CandidateOutput:
    candidate_id: str
    provider: str
    model: str
    modality: str
    page_count: int
    estimated_cost: float
    output: Mapping[str, Any]
    evidence_refs: tuple[str, ...] = ()
    citations: tuple[str, ...] = ()
    manual_approval: bool = False
    schema_valid: bool | None = None
    legal_valid: bool | None = None
    math_valid: bool | None = None


@dataclass(frozen=True)
class PolicyResult:
    status: PolicyStatus
    reasons: tuple[str, ...]

    @property
    def allowed(self) -> bool:
        return self.status is PolicyStatus.ALLOWED


@dataclass(frozen=True)
class BlindScore:
    candidate_id: str
    blind_id: str
    eligible: bool
    total: int
    dimensions: Mapping[str, int]
    policy_reasons: tuple[str, ...]
    defects: tuple[str, ...]


@dataclass(frozen=True)
class FieldConflict:
    field: str
    candidate_values: Mapping[str, Any]
    status: str = "UNRESOLVED"


@dataclass(frozen=True)
class TournamentResult:
    scores: tuple[BlindScore, ...]
    ranking: tuple[str, ...]
    conflicts: tuple[FieldConflict, ...]
    agreements: Mapping[str, Any]
    truth_established: bool = False


def enforce_provider_policy(
    policy: ProviderPolicy,
    *,
    modality: str,
    page_count: int,
    estimated_cost: float,
    manual_approval: bool,
) -> PolicyResult:
    reasons: list[str] = []
    if not policy.enabled:
        reasons.append("provider is disabled")
    if modality not in policy.allowed_modalities:
        reasons.append(f"modality {modality!r} is not allowed")
    if page_count < 0 or page_count > policy.max_pages:
        reasons.append("page limit exceeded")
    if estimated_cost < 0 or estimated_cost > policy.max_cost:
        reasons.append("cost limit exceeded")
    if policy.manual_approval_required and not manual_approval:
        reasons.append("manual approval required")
    return PolicyResult(
        PolicyStatus.BLOCKED if reasons else PolicyStatus.ALLOWED,
        tuple(reasons),
    )


def _blind_id(candidate: CandidateOutput) -> str:
    stable = json.dumps(
        {
            "candidate_id": candidate.candidate_id,
            "output": candidate.output,
            "evidence_refs": candidate.evidence_refs,
            "citations": candidate.citations,
        },
        sort_keys=True,
        default=str,
    )
    return "BLIND-" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:12].upper()


def _ratio(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def _score_candidate(
    candidate: CandidateOutput,
    config: TournamentConfig,
    verified_evidence_refs: frozenset[str],
    policy: PolicyResult,
) -> BlindScore:
    refs = tuple(dict.fromkeys(ref for ref in candidate.evidence_refs if ref))
    citations = tuple(dict.fromkeys(ref for ref in candidate.citations if ref))
    supported_refs = sum(ref in verified_evidence_refs for ref in refs)
    supported_citations = sum(ref in verified_evidence_refs for ref in citations)
    required = config.required_schema_fields
    populated = sum(
        field_name in candidate.output and candidate.output[field_name] not in (None, "")
        for field_name in required
    )
    if candidate.schema_valid is False:
        schema_ratio = 0.0
    elif candidate.schema_valid is True and not required:
        schema_ratio = 1.0
    else:
        schema_ratio = _ratio(populated, len(required))
    legal_score = 1.0 if candidate.legal_valid is True else 0.0
    math_score = 1.0 if candidate.math_valid is True else 0.0
    ratios = {
        "evidence": _ratio(supported_refs, len(refs)),
        "citation": _ratio(supported_citations, len(citations)),
        "schema": schema_ratio,
        "legal": legal_score,
        "math": math_score,
    }
    dimensions = {
        name: round(config.score_weights[name] * ratios[name])
        for name in config.score_weights
    }
    defects: list[str] = []
    if ratios["evidence"] < 1:
        defects.append("unverified or missing evidence references")
    if ratios["citation"] < 1:
        defects.append("unverified or missing citations")
    if ratios["schema"] < 1:
        defects.append("schema incomplete or invalid")
    if candidate.legal_valid is not True:
        defects.append("legal validation not proven")
    if candidate.math_valid is not True:
        defects.append("math validation not proven")
    return BlindScore(
        candidate_id=candidate.candidate_id,
        blind_id=_blind_id(candidate),
        eligible=policy.allowed,
        total=sum(dimensions.values()) if policy.allowed else 0,
        dimensions=dimensions,
        policy_reasons=policy.reasons,
        defects=tuple(defects),
    )


def score_candidates_blind(
    config: TournamentConfig,
    candidates: Sequence[CandidateOutput],
    *,
    verified_evidence_refs: Sequence[str] = (),
) -> TournamentResult:
    """Score already-supplied outputs; this function performs no network I/O."""

    policies = {policy.provider: policy for policy in config.providers}
    verified_refs = frozenset(verified_evidence_refs)
    scored: list[BlindScore] = []
    for candidate in candidates:
        policy = policies.get(candidate.provider)
        if policy is None:
            policy_result = PolicyResult(
                PolicyStatus.BLOCKED, ("provider has no configured policy",)
            )
        else:
            policy_result = enforce_provider_policy(
                policy,
                modality=candidate.modality,
                page_count=candidate.page_count,
                estimated_cost=candidate.estimated_cost,
                manual_approval=candidate.manual_approval,
            )
        scored.append(
            _score_candidate(
                candidate,
                config,
                verified_refs,
                policy_result,
            )
        )

    fields = sorted({field_name for candidate in candidates for field_name in candidate.output})
    conflicts: list[FieldConflict] = []
    agreements: dict[str, Any] = {}
    for field_name in fields:
        values = {
            candidate.candidate_id: candidate.output[field_name]
            for candidate in candidates
            if field_name in candidate.output and candidate.output[field_name] not in (None, "")
        }
        normalized = {
            json.dumps(value, sort_keys=True, default=str): value for value in values.values()
        }
        if len(normalized) > 1:
            conflicts.append(FieldConflict(field_name, values))
        elif normalized and len(values) > 1:
            # Agreement is recorded for review, never promoted to verified truth.
            agreements[field_name] = next(iter(normalized.values()))
    ranking = tuple(
        score.candidate_id
        for score in sorted(
            scored,
            key=lambda item: (-int(item.eligible), -item.total, item.blind_id),
        )
    )
    return TournamentResult(
        scores=tuple(scored),
        ranking=ranking,
        conflicts=tuple(conflicts),
        agreements=agreements,
        truth_established=False,
    )
