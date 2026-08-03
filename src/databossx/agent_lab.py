"""Fail-closed policy boundary for optional AI providers.

Providers are candidate workers only. This module validates an invocation
before an adapter is allowed to call Flowise, a local model server, a training
lab, or any future provider. It contains no networking or provider SDKs.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


class AgentPolicyViolation(ValueError):
    """An external worker request violates the canonical DataBossX policy."""


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentPolicyViolation(f"{field} is required")
    return value


def _require_sha256(value: object, field: str) -> str:
    text = _require_text(value, field)
    if _SHA256.fullmatch(text) is None:
        raise AgentPolicyViolation(f"{field} must be a 64-character SHA-256")
    return text.lower()


def _require_budget(
    value: object, field: str, *, integral: bool = False
) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AgentPolicyViolation(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise AgentPolicyViolation(
            f"{field} must be finite and greater than zero"
        )
    if integral:
        if number != int(number):
            raise AgentPolicyViolation(f"{field} must be an integer")
        return int(number)
    return number


@dataclass(frozen=True)
class AuthorizedCapabilityRequest:
    """A normalized request that passed the external-provider policy gate."""

    project_id: str
    task_id: str
    task_envelope_sha256: str
    input_manifest_sha256: str
    data_classification: str
    egress_decision: str
    capability: str
    provider_id: str
    provider_revision: str
    model_id: str
    model_revision: str
    adapter_version: str
    prompt_version: str
    policy_version: str
    lease_id: str
    fence: int
    expires_at: str
    time_budget_seconds: float
    token_budget: int
    cost_budget_usd: float


@dataclass(frozen=True)
class ValidatedCandidateOutcome:
    """A normalized candidate result with no authority to commit state."""

    outcome_id: str
    status: str
    output_manifest_sha256: str
    evidence_locators: tuple[str, ...]
    schema_valid: bool
    provenance_valid: bool
    evaluation_results: Mapping[str, Any]
    tokens: int
    latency_ms: float
    cost_usd: float
    retries: int
    provider_request_id: str
    requires_human_review: bool


class AgentProviderPolicy:
    """Load and enforce one versioned provider registry."""

    def __init__(self, registry: Mapping[str, Any]):
        if registry.get("schema") != "databossx.agent_provider_registry.v1":
            raise AgentPolicyViolation("unsupported provider registry schema")
        authority = registry.get("authority")
        if not isinstance(authority, Mapping):
            raise AgentPolicyViolation(
                "provider registry authority is missing"
            )
        if authority.get("canonical_system") != "DataBossX":
            raise AgentPolicyViolation(
                "DataBossX must remain the canonical system"
            )
        if authority.get("external_provider_role") != "candidate_worker_only":
            raise AgentPolicyViolation(
                "external providers must remain candidate workers"
            )

        providers = registry.get("providers")
        if not isinstance(providers, list) or not providers:
            raise AgentPolicyViolation("provider registry has no providers")
        by_id: dict[str, Mapping[str, Any]] = {}
        for provider in providers:
            if not isinstance(provider, Mapping):
                raise AgentPolicyViolation("provider entry is not an object")
            provider_id = _require_text(provider.get("id"), "provider.id")
            if provider_id in by_id:
                raise AgentPolicyViolation(
                    f"duplicate provider ID: {provider_id}"
                )
            if provider.get("required") is not False:
                raise AgentPolicyViolation(
                    f"provider {provider_id} must remain optional"
                )
            if provider.get("direct_writes_allowed") is not False:
                raise AgentPolicyViolation(
                    f"provider {provider_id} cannot write directly"
                )
            by_id[provider_id] = provider

        self.registry = dict(registry)
        self.providers = by_id
        self.forbidden_capabilities = frozenset(
            str(value) for value in authority.get("forbidden_capabilities", ())
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "AgentProviderPolicy":
        source = Path(path)
        try:
            registry = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AgentPolicyViolation(
                f"cannot load provider registry: {exc}"
            ) from None
        if not isinstance(registry, Mapping):
            raise AgentPolicyViolation(
                "provider registry root is not an object"
            )
        return cls(registry)

    def authorize(
        self, request: Mapping[str, Any]
    ) -> AuthorizedCapabilityRequest:
        """Normalize a request before any provider side effect."""

        provider_id = _require_text(request.get("provider_id"), "provider_id")
        provider = self.providers.get(provider_id)
        if provider is None:
            raise AgentPolicyViolation(f"unregistered provider: {provider_id}")

        capability = _require_text(request.get("capability"), "capability")
        if capability in self.forbidden_capabilities:
            raise AgentPolicyViolation(
                f"forbidden provider capability: {capability}"
            )

        data_classification = _require_text(
            request.get("data_classification"), "data_classification"
        )
        allowed_classes = provider.get("data_classes_allowed", ())
        if data_classification not in allowed_classes:
            raise AgentPolicyViolation(
                f"provider {provider_id} does not allow data class "
                f"{data_classification}"
            )

        egress_decision = _require_text(
            request.get("egress_decision"), "egress_decision"
        )
        network_policy = provider.get("network_policy")
        if (
            network_policy == "loopback_only"
            and egress_decision != "local_only"
        ):
            raise AgentPolicyViolation(
                f"provider {provider_id} requires local-only egress"
            )
        if (
            network_policy == "isolated_training_environment"
            and egress_decision != "isolated_lab"
        ):
            raise AgentPolicyViolation(
                f"provider {provider_id} requires the isolated lab"
            )

        fence = _require_budget(request.get("fence"), "fence", integral=True)
        token_budget = _require_budget(
            request.get("token_budget"), "token_budget", integral=True
        )

        return AuthorizedCapabilityRequest(
            project_id=_require_text(request.get("project_id"), "project_id"),
            task_id=_require_text(request.get("task_id"), "task_id"),
            task_envelope_sha256=_require_sha256(
                request.get("task_envelope_sha256"), "task_envelope_sha256"
            ),
            input_manifest_sha256=_require_sha256(
                request.get("input_manifest_sha256"), "input_manifest_sha256"
            ),
            data_classification=data_classification,
            egress_decision=egress_decision,
            capability=capability,
            provider_id=provider_id,
            provider_revision=_require_text(
                request.get("provider_revision"), "provider_revision"
            ),
            model_id=_require_text(request.get("model_id"), "model_id"),
            model_revision=_require_text(
                request.get("model_revision"), "model_revision"
            ),
            adapter_version=_require_text(
                request.get("adapter_version"), "adapter_version"
            ),
            prompt_version=_require_text(
                request.get("prompt_version"), "prompt_version"
            ),
            policy_version=_require_text(
                request.get("policy_version"), "policy_version"
            ),
            lease_id=_require_text(request.get("lease_id"), "lease_id"),
            fence=int(fence),
            expires_at=_require_text(request.get("expires_at"), "expires_at"),
            time_budget_seconds=float(
                _require_budget(
                    request.get("time_budget_seconds"), "time_budget_seconds"
                )
            ),
            token_budget=int(token_budget),
            cost_budget_usd=float(
                _require_budget(
                    request.get("cost_budget_usd"), "cost_budget_usd"
                )
            ),
        )

    def validate_outcome(
        self, outcome: Mapping[str, Any]
    ) -> ValidatedCandidateOutcome:
        """Validate a result while preserving candidate-only status."""

        status = _require_text(outcome.get("status"), "status")
        if status not in {"candidate", "failed_retryable", "failed_terminal"}:
            raise AgentPolicyViolation(
                "provider outcome status cannot imply authority"
            )

        locators = outcome.get("evidence_locators")
        if not isinstance(locators, list) or any(
            not isinstance(locator, str) or not locator.strip()
            for locator in locators
        ):
            raise AgentPolicyViolation(
                "evidence_locators must be a list of non-empty strings"
            )

        evaluation_results = outcome.get("evaluation_results")
        if not isinstance(evaluation_results, Mapping):
            raise AgentPolicyViolation("evaluation_results must be an object")

        for field in (
            "schema_valid",
            "provenance_valid",
            "requires_human_review",
        ):
            if not isinstance(outcome.get(field), bool):
                raise AgentPolicyViolation(f"{field} must be boolean")

        tokens = outcome.get("tokens")
        retries = outcome.get("retries")
        if (
            isinstance(tokens, bool)
            or not isinstance(tokens, int)
            or tokens < 0
        ):
            raise AgentPolicyViolation("tokens must be a non-negative integer")
        if (
            isinstance(retries, bool)
            or not isinstance(retries, int)
            or retries < 0
        ):
            raise AgentPolicyViolation(
                "retries must be a non-negative integer"
            )

        latency_ms = outcome.get("latency_ms")
        cost_usd = outcome.get("cost_usd")
        for value, field in (
            (latency_ms, "latency_ms"),
            (cost_usd, "cost_usd"),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0
            ):
                raise AgentPolicyViolation(
                    f"{field} must be finite and non-negative"
                )

        return ValidatedCandidateOutcome(
            outcome_id=_require_text(outcome.get("outcome_id"), "outcome_id"),
            status=status,
            output_manifest_sha256=_require_sha256(
                outcome.get("output_manifest_sha256"), "output_manifest_sha256"
            ),
            evidence_locators=tuple(locators),
            schema_valid=outcome["schema_valid"],
            provenance_valid=outcome["provenance_valid"],
            evaluation_results=dict(evaluation_results),
            tokens=tokens,
            latency_ms=float(latency_ms),
            cost_usd=float(cost_usd),
            retries=retries,
            provider_request_id=_require_text(
                outcome.get("provider_request_id"), "provider_request_id"
            ),
            requires_human_review=outcome["requires_human_review"],
        )
