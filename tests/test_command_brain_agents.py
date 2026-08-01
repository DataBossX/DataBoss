"""Agent registry, dispatch, and model-gateway honesty."""

from __future__ import annotations

import pytest

from databossx.command_brain.autonomy import AutonomyLevel
from databossx.command_brain.errors import (
    AgentNotRegistered,
    AuthorityError,
    EgressDenied,
    ModelUnavailable,
    SchemaViolation,
    WriterCollision,
)
from databossx.command_brain.judge import IndependenceViolation, assert_independent
from databossx.command_brain.model_gateway import Modality, VerificationState
from databossx.command_brain.policy import PolicyProfile
from databossx.command_brain.roles import ROLES, get_role, list_roles

REQUIRED_ROLES = {
    "COMMANDER", "PLANNER", "CODE_BUILDER", "CODE_REVIEWER", "REPORT_READER",
    "INDEX_READER", "RUNSHEET_RECONCILER", "TITLE_ANALYSIS_ASSISTANT",
    "FORMULA_VALIDATOR", "PAGE_RENDER_REVIEWER", "SECURITY_REVIEWER", "JUDGE",
    "HUMAN_REVIEW",
}


def test_every_declared_role_is_registered():
    assert REQUIRED_ROLES <= set(ROLES)


def test_every_role_declares_a_complete_permission_envelope():
    for role in list_roles():
        assert role["description"]
        assert role["permitted_tools"]
        assert role["output_schema_hash"]
        assert role["timeout_seconds"] > 0
        assert role["retry_limit"] >= 0
        assert role["cost_limit"]
        assert role["project_scope"]
        assert role["max_autonomy"] <= 3


def test_only_the_code_builder_is_a_writer():
    writers = [role_id for role_id, role in ROLES.items() if role.is_writer]
    assert writers == ["CODE_BUILDER"]
    assert ROLES["CODE_BUILDER"].required_approvals == ("task_envelope", "writer_ack")


def test_unregistered_agent_is_rejected(runtime):
    with pytest.raises(AgentNotRegistered):
        runtime.dispatcher.dispatch("SUPER_AGENT", "deterministic.commander", {})


def test_unregistered_model_is_rejected(runtime):
    with pytest.raises(ModelUnavailable):
        runtime.dispatcher.dispatch("COMMANDER", "gpt-omniscient", {})


def test_unverified_model_reports_not_verified_and_cannot_be_used(runtime):
    adapter = runtime.gateway.get("local.openai_compatible")
    assert adapter.health.state is VerificationState.NOT_VERIFIED

    catalog = {entry["model_id"]: entry for entry in runtime.model_catalog()}
    assert catalog["local.openai_compatible"]["verification_state"] == "NOT_VERIFIED"
    assert catalog["handoff.claude_code"]["verification_state"] == "NOT_VERIFIED"

    with runtime.policy.elevated(AutonomyLevel.READ_ONLY_EXECUTE):
        with pytest.raises(ModelUnavailable):
            runtime.dispatcher.dispatch("CODE_REVIEWER", "local.openai_compatible", {})


def test_verification_state_is_never_assumed_green(runtime):
    """A model only becomes VERIFIED after a probe that actually succeeded."""
    verified = set(runtime.gateway.verified_models())
    assert "deterministic.reconciler" in verified
    assert "local.openai_compatible" not in verified
    # Simulated adapters are LIMITED, never VERIFIED.
    assert all(not model.startswith("simulated.") for model in verified)


def test_quarantined_model_cannot_be_invoked(runtime):
    adapter = runtime.gateway.get("simulated.reader.careful")
    adapter.quarantine("suspected drift")
    with runtime.policy.elevated(AutonomyLevel.READ_ONLY_EXECUTE):
        with pytest.raises(ModelUnavailable) as excinfo:
            runtime.dispatcher.dispatch("INDEX_READER", "simulated.reader.careful", {})
    assert "quarantin" in str(excinfo.value).lower()


def test_agent_output_is_schema_validated(runtime):
    """A model returning the wrong shape is a refusal, not a partial success."""
    adapter = runtime.gateway.get("deterministic.commander")
    adapter._fn = lambda request: {"unexpected": "shape"}
    with pytest.raises(SchemaViolation):
        runtime.dispatcher.dispatch("COMMANDER", "deterministic.commander", {})

    row = runtime.store.fetchone(
        "SELECT status, error_code FROM cb_agent_assignments WHERE role_id = 'COMMANDER'"
    )
    assert row["status"] == "REJECTED"
    assert row["error_code"] == "SCHEMA_VIOLATION"


def test_a_verified_deterministic_agent_runs_read_only_and_writes_a_receipt(runtime):
    result = runtime.dispatcher.dispatch(
        "COMMANDER",
        "deterministic.commander",
        {"summary": "Section 32 is awaiting examiner review.", "facts": []},
    )
    assert result.verification_state == "VERIFIED"
    assert result.simulated is False
    assert result.receipt_id
    receipt = runtime.store.get_receipt(result.receipt_id)
    assert receipt["payload"]["model_id"] == "deterministic.commander"
    assert receipt["payload"]["output_hash"] == result.output_hash


def test_simulated_agent_results_are_labelled_simulated(runtime):
    with runtime.policy.elevated(AutonomyLevel.READ_ONLY_EXECUTE):
        result = runtime.dispatcher.dispatch(
            "INDEX_READER",
            "simulated.reader.careful",
            {"page_ids": [page.page_id for page in runtime.corpus.pages], "candidate_id": "cand_x"},
            modality=Modality.VISION,
        )
    assert result.simulated is True
    assert result.output["simulated"] is True
    assert "SIMULATED" in result.output["reasoning_summary"]


def test_writer_role_requires_an_envelope(runtime):
    """Even with the mode raised and an approval in hand, no envelope means no write."""
    with runtime.policy.elevated(AutonomyLevel.BOUNDED_WRITER):
        with pytest.raises(AuthorityError) as excinfo:
            runtime.dispatcher.dispatch(
                "CODE_BUILDER", "handoff.claude_code", {}, approval_id="apr_claimed"
            )
    assert "TaskEnvelope" in str(excinfo.value)


def test_writer_dispatch_from_an_utterance_alone_is_refused(runtime):
    """No approval at all: speech cannot start a writer, whatever the mode."""
    from databossx.command_brain.errors import PolicyViolation

    with runtime.policy.elevated(AutonomyLevel.BOUNDED_WRITER):
        with pytest.raises(PolicyViolation) as excinfo:
            runtime.dispatcher.dispatch("CODE_BUILDER", "handoff.claude_code", {})
    assert "not authorization" in str(excinfo.value)


def test_simultaneous_writers_on_one_lane_are_rejected(runtime):
    lane = "worktree:command-brain-alpha"
    runtime.leases.acquire(lane, "writer-a", ttl_seconds=600)
    with pytest.raises(WriterCollision) as excinfo:
        runtime.leases.acquire(lane, "writer-b", ttl_seconds=600)
    assert "already leased" in str(excinfo.value)


def test_a_writer_cannot_take_the_lane_it_already_holds_twice(runtime):
    lane = "artifact:workbook"
    runtime.leases.acquire(lane, "writer-a")
    with pytest.raises(WriterCollision):
        runtime.leases.acquire(lane, "writer-a")


def test_agent_cannot_be_the_only_judge_of_its_own_result():
    with pytest.raises(IndependenceViolation):
        assert_independent("simulated.reader.careful", "simulated.reader.careful")
    # An independent validator alongside it is acceptable.
    assert_independent(
        "simulated.reader.careful",
        "simulated.reader.careful",
        validators=("deterministic.judge",),
    )


def test_local_only_mode_makes_remote_endpoints_unreachable(runtime):
    runtime.policy.set_profile(PolicyProfile().with_local_only().with_read_only())
    eligible = runtime.gateway.eligible(runtime.policy.profile)
    assert all(runtime.gateway.get(model).descriptor.is_local for model in eligible)

    with pytest.raises(EgressDenied):
        runtime.dispatcher.dispatch("CODE_REVIEWER", "handoff.claude_code", {})


def test_code_handoff_states_its_own_authority_status(runtime):
    from databossx.command_brain.dispatcher import build_code_handoff

    handoff = build_code_handoff(
        repository="DataBossX/DataBoss",
        branch="claude/databossx-command-brain-alpha-gh8syu",
        worktree="<isolated worktree>",
        scope="Add a validator",
        allowed_files=["src/databossx/command_brain/"],
        prohibited_files=["runtime/", "client workbooks"],
        tests=["command_brain_selftest"],
        acceptance_criteria=["Tests pass"],
    )
    assert handoff["authority_status"] == "AWAITING_AUTHORIZATION"
    assert handoff["final_sentinel"] == "DATABOSSX_COMMAND_BRAIN_AWAITING_AUTHORIZATION"


def test_model_catalog_reports_every_required_field(runtime):
    for entry in runtime.model_catalog():
        for field in (
            "provider", "model_id", "modalities", "context_limit", "tool_use",
            "structured_output", "is_local", "verification_state", "cost_category",
            "latency_category", "data_sensitivity_policy", "permitted_project_classes",
            "last_verified_at", "simulated",
        ):
            assert field in entry, f"{entry['model_id']} missing {field}"


def test_vision_capability_is_not_claimed_for_text_only_models(runtime):
    descriptor = runtime.gateway.get("local.openai_compatible").descriptor
    assert not descriptor.supports(Modality.VISION)
    with pytest.raises(ModelUnavailable):
        runtime.gateway.invoke(
            "deterministic.commander",
            __import__(
                "databossx.command_brain.model_gateway", fromlist=["ModelRequest"]
            ).ModelRequest(capability="read", payload={}, modality=Modality.VISION),
            runtime.policy.profile,
        )


def test_role_output_schemas_exist_for_every_dispatchable_role():
    for role_id, role in ROLES.items():
        assert role.output_schema, f"{role_id} has no output contract"
        assert get_role(role_id) is role
