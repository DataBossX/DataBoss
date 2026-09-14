"""Policy-first capability router.

Hard filters run before ranking. Local-only policy makes remote workers
technically ineligible. Deterministic capabilities never route to an LLM.
Agreement between models is not treated as evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .hashing import sha256_bytes
from .receipts import canonical_dumps


DETERMINISTIC_CAPABILITIES = frozenset(
    {
        "hash",
        "inventory",
        "title_math",
        "chain_rules",
        "workbook_compare",
        "candidate_compare",
        "receipt",
        "cache_lookup",
    }
)

LLM_PROVIDERS = frozenset({"llm", "remote_llm", "openai", "anthropic", "gemini"})


@dataclass(frozen=True)
class WorkerSpec:
    worker_id: str
    capabilities: tuple[str, ...]
    provider: str
    requires_network: bool
    quality: float
    expected_cost: float
    latency_ms: int
    supports_structured: bool = True
    max_context_bytes: int = 8_000_000
    modalities: tuple[str, ...] = ("text",)


@dataclass(frozen=True)
class RoutePolicy:
    profile: str = "local_only"
    local_only: bool = True
    allow_egress: bool = False
    require_structured: bool = False
    max_cost: float | None = None
    required_modality: str | None = None
    min_context_bytes: int = 0


@dataclass(frozen=True)
class RouteRequest:
    capability: str
    input_hash: str
    policy: RoutePolicy = field(default_factory=RoutePolicy)
    context_bytes: int = 0
    modality: str = "text"


@dataclass(frozen=True)
class Rejection:
    worker_id: str
    reason: str


@dataclass(frozen=True)
class RouteDecision:
    capability: str
    policy_profile: str
    input_hash: str
    selected_worker_id: str | None
    selected_provider: str | None
    considered: tuple[str, ...]
    rejected: tuple[Rejection, ...]
    blocked_reason: str | None
    decision_hash: str

    @property
    def blocked(self) -> bool:
        return self.selected_worker_id is None


DEFAULT_CATALOG: tuple[WorkerSpec, ...] = (
    WorkerSpec(
        worker_id="local.hash.v1",
        capabilities=("hash", "inventory", "cache_lookup", "receipt"),
        provider="local",
        requires_network=False,
        quality=1.0,
        expected_cost=0.0,
        latency_ms=5,
    ),
    WorkerSpec(
        worker_id="local.title_math.v1",
        capabilities=("title_math",),
        provider="local",
        requires_network=False,
        quality=1.0,
        expected_cost=0.0,
        latency_ms=8,
    ),
    WorkerSpec(
        worker_id="local.chain_rules.v1",
        capabilities=("chain_rules",),
        provider="local",
        requires_network=False,
        quality=1.0,
        expected_cost=0.0,
        latency_ms=12,
    ),
    WorkerSpec(
        worker_id="local.compare.v1",
        capabilities=("workbook_compare", "candidate_compare"),
        provider="local",
        requires_network=False,
        quality=1.0,
        expected_cost=0.0,
        latency_ms=15,
    ),
    WorkerSpec(
        worker_id="local.ocr.v1",
        capabilities=("ocr",),
        provider="local_ocr",
        requires_network=False,
        quality=0.72,
        expected_cost=0.0,
        latency_ms=800,
        modalities=("image", "pdf", "text"),
    ),
    WorkerSpec(
        worker_id="local.extract.rules.v1",
        capabilities=("extract",),
        provider="local_rules",
        requires_network=False,
        quality=0.65,
        expected_cost=0.0,
        latency_ms=20,
    ),
    WorkerSpec(
        worker_id="remote.ocr.cloud.v1",
        capabilities=("ocr",),
        provider="cloud_ocr",
        requires_network=True,
        quality=0.88,
        expected_cost=12.0,
        latency_ms=400,
        modalities=("image", "pdf"),
    ),
    WorkerSpec(
        worker_id="remote.extract.llm.v1",
        capabilities=("extract",),
        provider="llm",
        requires_network=True,
        quality=0.80,
        expected_cost=40.0,
        latency_ms=1200,
    ),
)


def policy_from_profile(profile: str) -> RoutePolicy:
    normalized = (profile or "local_only").strip().lower()
    if normalized in {"remote_allowed", "allow_remote", "egress"}:
        return RoutePolicy(profile=normalized, local_only=False, allow_egress=True)
    return RoutePolicy(profile=normalized or "local_only", local_only=True, allow_egress=False)


def _reject_reason(worker: WorkerSpec, request: RouteRequest) -> str | None:
    policy = request.policy
    if request.capability not in worker.capabilities:
        return "capability_mismatch"
    if policy.local_only and worker.requires_network:
        return "local_only_blocks_remote"
    if not policy.allow_egress and worker.requires_network:
        return "egress_forbidden"
    if request.capability in DETERMINISTIC_CAPABILITIES and worker.provider in LLM_PROVIDERS:
        return "deterministic_capability_rejects_llm"
    if request.capability in DETERMINISTIC_CAPABILITIES and worker.requires_network:
        return "deterministic_capability_rejects_network"
    if policy.require_structured and not worker.supports_structured:
        return "structured_output_required"
    if policy.required_modality and policy.required_modality not in worker.modalities:
        return "modality_mismatch"
    if request.modality and request.modality not in worker.modalities:
        return "modality_mismatch"
    if request.context_bytes > worker.max_context_bytes:
        return "context_too_large"
    if policy.min_context_bytes and worker.max_context_bytes < policy.min_context_bytes:
        return "context_window_too_small"
    if policy.max_cost is not None and worker.expected_cost > policy.max_cost:
        return "over_budget"
    return None


def _rank(workers: Sequence[WorkerSpec]) -> list[WorkerSpec]:
    return sorted(
        workers,
        key=lambda worker: (
            -worker.quality,
            worker.expected_cost,
            worker.latency_ms,
            worker.worker_id,
        ),
    )


def _decision_hash(
    capability: str,
    policy_profile: str,
    input_hash: str,
    selected_worker_id: str | None,
    rejected: Sequence[Rejection],
) -> str:
    payload = {
        "capability": capability,
        "input_hash": input_hash,
        "policy_profile": policy_profile,
        "rejected": [{"reason": item.reason, "worker_id": item.worker_id} for item in rejected],
        "selected_worker_id": selected_worker_id,
    }
    return sha256_bytes(canonical_dumps(payload).encode("utf-8"))


def route(
    request: RouteRequest,
    catalog: Iterable[WorkerSpec] | None = None,
) -> RouteDecision:
    workers = tuple(catalog) if catalog is not None else DEFAULT_CATALOG
    considered = [worker.worker_id for worker in workers]
    rejected: list[Rejection] = []
    eligible: list[WorkerSpec] = []
    for worker in workers:
        reason = _reject_reason(worker, request)
        if reason:
            rejected.append(Rejection(worker.worker_id, reason))
        else:
            eligible.append(worker)

    selected = _rank(eligible)[0] if eligible else None
    blocked_reason = None
    if selected is None:
        if not any(request.capability in worker.capabilities for worker in workers):
            blocked_reason = "no_worker_for_capability"
        elif request.policy.local_only and all(
            worker.requires_network
            for worker in workers
            if request.capability in worker.capabilities
        ):
            blocked_reason = "local_only_no_eligible_worker"
        else:
            blocked_reason = "no_eligible_worker"

    selected_id = selected.worker_id if selected else None
    decision = RouteDecision(
        capability=request.capability,
        policy_profile=request.policy.profile,
        input_hash=request.input_hash,
        selected_worker_id=selected_id,
        selected_provider=selected.provider if selected else None,
        considered=tuple(considered),
        rejected=tuple(rejected),
        blocked_reason=blocked_reason,
        decision_hash=_decision_hash(
            request.capability,
            request.policy.profile,
            request.input_hash,
            selected_id,
            rejected,
        ),
    )
    return decision


def decision_to_dict(decision: RouteDecision) -> dict[str, object]:
    return {
        "blocked": decision.blocked,
        "blocked_reason": decision.blocked_reason,
        "capability": decision.capability,
        "considered": list(decision.considered),
        "decision_hash": decision.decision_hash,
        "input_hash": decision.input_hash,
        "policy_profile": decision.policy_profile,
        "rejected": [
            {"reason": item.reason, "worker_id": item.worker_id} for item in decision.rejected
        ],
        "selected_provider": decision.selected_provider,
        "selected_worker_id": decision.selected_worker_id,
    }


def persist_route_decision(conn, project_id: str, decision: RouteDecision) -> int:
    cursor = conn.execute(
        """
        INSERT INTO model_route_decisions (
            project_id, capability, policy_profile, selected_worker, selected_provider,
            rejection_json, considered_json, input_hash, decision_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            decision.capability,
            decision.policy_profile,
            decision.selected_worker_id,
            decision.selected_provider,
            canonical_dumps(decision_to_dict(decision)["rejected"]),
            canonical_dumps(list(decision.considered)),
            decision.input_hash,
            decision.decision_hash,
        ),
    )
    return int(cursor.lastrowid)
