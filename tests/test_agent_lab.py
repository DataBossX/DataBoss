from __future__ import annotations

import copy
from pathlib import Path

import pytest

from databossx.agent_lab import AgentPolicyViolation, AgentProviderPolicy


REGISTRY = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "policies"
    / "agent-provider-registry.v1.json"
)
HASH = "a" * 64


def _policy() -> AgentProviderPolicy:
    return AgentProviderPolicy.from_file(REGISTRY)


def _request(**changes):
    request = {
        "project_id": "synthetic-project",
        "task_id": "task-1",
        "task_envelope_sha256": HASH,
        "input_manifest_sha256": HASH,
        "data_classification": "synthetic",
        "egress_decision": "local_only",
        "capability": "extract.instrument_fields",
        "provider_id": "ollama",
        "provider_revision": "0.12.0",
        "model_id": "synthetic-model",
        "model_revision": "sha256:fixture",
        "adapter_version": "1.0.0",
        "prompt_version": "1.0.0",
        "policy_version": "1.0.0",
        "lease_id": "lease-1",
        "fence": 7,
        "expires_at": "2026-08-03T18:00:00Z",
        "time_budget_seconds": 60,
        "token_budget": 4096,
        "cost_budget_usd": 0.01,
    }
    request.update(changes)
    return request


def _outcome(**changes):
    outcome = {
        "outcome_id": "outcome-1",
        "status": "candidate",
        "output_manifest_sha256": HASH,
        "evidence_locators": ["fixture://document/1#page=1&span=20-40"],
        "schema_valid": True,
        "provenance_valid": True,
        "evaluation_results": {"field_accuracy": 1.0},
        "tokens": 500,
        "latency_ms": 200,
        "cost_usd": 0.0,
        "retries": 0,
        "provider_request_id": "local-request-1",
        "requires_human_review": True,
    }
    outcome.update(changes)
    return outcome


def test_authorizes_bounded_local_candidate_request():
    authorized = _policy().authorize(_request())

    assert authorized.provider_id == "ollama"
    assert authorized.fence == 7
    assert authorized.token_budget == 4096


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"provider_id": "unknown"}, "unregistered provider"),
        ({"capability": "emit_terminal"}, "forbidden provider capability"),
        ({"data_classification": "confidential"}, "does not allow data class"),
        ({"egress_decision": "remote_allowed"}, "requires local-only egress"),
        ({"task_envelope_sha256": "bad"}, "must be a 64-character SHA-256"),
        ({"lease_id": ""}, "lease_id is required"),
        ({"fence": 0}, "fence must be finite and greater than zero"),
        ({"time_budget_seconds": float("inf")}, "must be finite"),
        ({"token_budget": -1}, "must be finite and greater than zero"),
        ({"cost_budget_usd": 0}, "must be finite and greater than zero"),
    ],
)
def test_rejects_request_before_provider_call(changes, message):
    with pytest.raises(AgentPolicyViolation, match=message):
        _policy().authorize(_request(**changes))


def test_flowise_is_limited_to_synthetic_deidentified_lab_work():
    authorized = _policy().authorize(
        _request(
            provider_id="flowise",
            egress_decision="isolated_lab",
            data_classification="deidentified",
        )
    )
    assert authorized.provider_id == "flowise"

    with pytest.raises(
        AgentPolicyViolation, match="does not allow data class"
    ):
        _policy().authorize(
            _request(
                provider_id="flowise",
                egress_decision="isolated_lab",
                data_classification="internal",
            )
        )


def test_registry_tampering_fails_closed():
    policy = _policy()
    tampered = copy.deepcopy(policy.registry)
    tampered["providers"][0]["direct_writes_allowed"] = True

    with pytest.raises(AgentPolicyViolation, match="cannot write directly"):
        AgentProviderPolicy(tampered)


def test_validates_candidate_outcome_without_promoting_it():
    candidate = _policy().validate_outcome(_outcome())
    assert candidate.status == "candidate"
    assert candidate.requires_human_review is True


@pytest.mark.parametrize(
    "status", ["succeeded", "approved", "released", "terminal"]
)
def test_provider_outcome_cannot_claim_authority(status):
    with pytest.raises(AgentPolicyViolation, match="cannot imply authority"):
        _policy().validate_outcome(_outcome(status=status))


def test_candidate_outcome_requires_provenance_and_evaluation_shape():
    with pytest.raises(AgentPolicyViolation, match="evidence_locators"):
        _policy().validate_outcome(_outcome(evidence_locators=[""]))
    with pytest.raises(AgentPolicyViolation, match="evaluation_results"):
        _policy().validate_outcome(_outcome(evaluation_results=[]))
