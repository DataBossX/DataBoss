"""Policy tests for the provider-neutral Agent Lab registry."""

from __future__ import annotations

import json
from pathlib import Path


REGISTRY = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "policies"
    / "agent-provider-registry.v1.json"
)


def _load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_registry_keeps_databossx_as_only_authority() -> None:
    registry = _load_registry()
    assert registry["authority"]["canonical_system"] == "DataBossX"
    assert registry["authority"]["external_provider_role"] == "candidate_worker_only"
    assert registry["default_decision"] == "deny_unregistered_provider_or_capability"


def test_every_provider_is_optional_and_cannot_write_directly() -> None:
    registry = _load_registry()
    providers = registry["providers"]

    assert providers
    assert len({provider["id"] for provider in providers}) == len(providers)
    for provider in providers:
        assert provider["required"] is False
        assert provider["direct_writes_allowed"] is False
        assert provider["gates"]


def test_external_providers_cannot_issue_authority_or_release() -> None:
    registry = _load_registry()
    forbidden = set(registry["authority"]["forbidden_capabilities"])

    assert {
        "activate_command",
        "issue_writer_ack",
        "issue_lease",
        "issue_fence",
        "emit_start_claim",
        "emit_terminal",
        "write_protected_workbook",
        "promote_artifact",
        "remove_hold",
        "release_external",
    } <= forbidden


def test_invocation_contract_binds_provenance_authority_and_budgets() -> None:
    registry = _load_registry()
    request_fields = set(registry["invocation_contract"]["required_fields"])
    result_fields = set(registry["invocation_contract"]["required_result_fields"])

    assert {
        "task_envelope_sha256",
        "input_manifest_sha256",
        "data_classification",
        "egress_decision",
        "provider_revision",
        "model_revision",
        "policy_version",
        "lease_id",
        "fence",
        "expires_at",
        "time_budget_seconds",
        "token_budget",
        "cost_budget_usd",
    } <= request_fields
    assert {
        "output_manifest_sha256",
        "evidence_locators",
        "schema_valid",
        "provenance_valid",
        "evaluation_results",
        "requires_human_review",
    } <= result_fields


def test_long_running_workers_remain_bounded_and_recoverable() -> None:
    registry = _load_registry()
    controls = set(registry["long_running_worker_controls"])

    assert {
        "durable_checkpoint",
        "idempotency_key",
        "expiring_lease",
        "monotonic_fence",
        "heartbeat",
        "cancellation",
        "bounded_retry",
        "circuit_breaker",
        "dead_letter_review",
        "time_token_cost_budgets",
        "restart_reconciliation",
    } <= controls
