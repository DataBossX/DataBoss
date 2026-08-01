"""Authority: envelopes, approvals, leases, fencing tokens, holds, Level 4."""

from __future__ import annotations

from dataclasses import replace

import pytest

from databossx.command_brain.autonomy import ALPHA_MAX_LEVEL, AutonomyLevel
from databossx.command_brain.envelope import TaskEnvelope
from databossx.command_brain.errors import (
    ApprovalError,
    AuthorityError,
    FencingTokenError,
    HoldActive,
    LeaseError,
    PolicyViolation,
)
from databossx.command_brain.policy import (
    ActionRequest,
    AuthoritySource,
    PolicyProfile,
    RiskLevel,
)


# -- Level 4 -----------------------------------------------------------------

def test_level_4_cannot_be_set_as_a_ceiling():
    with pytest.raises(PolicyViolation):
        PolicyProfile(autonomy_ceiling=AutonomyLevel.RELEASE_OR_EXTERNAL)


def test_level_4_cannot_be_granted_by_elevation(runtime):
    with pytest.raises(PolicyViolation):
        with runtime.policy.elevated(AutonomyLevel.RELEASE_OR_EXTERNAL):
            pass


def test_alpha_maximum_is_bounded_writer():
    assert ALPHA_MAX_LEVEL is AutonomyLevel.BOUNDED_WRITER


def test_external_effects_are_refused_at_every_level(runtime):
    runtime.policy.set_profile(PolicyProfile(autonomy_ceiling=AutonomyLevel.BOUNDED_WRITER))
    decision = runtime.policy.evaluate(
        ActionRequest(
            action_type="publish_report",
            required_level=AutonomyLevel.BOUNDED_WRITER,
            risk=RiskLevel.CRITICAL,
            external_effect=True,
            approval_id="apr_valid",
            authority_source=AuthoritySource.AUTHENTICATED_APPROVAL,
        )
    )
    assert decision.allowed is False
    assert any("External effects" in reason for reason in decision.reasons)


# -- Envelopes ---------------------------------------------------------------

def test_bounded_writer_envelope_must_require_lease_and_fencing_token(runtime):
    with pytest.raises(AuthorityError):
        runtime.drafter.draft(
            requesting_user="ryan",
            transcript="edit the code",
            normalized_intent="edit the code",
            goal="edit the code",
            autonomy_level=AutonomyLevel.BOUNDED_WRITER,
            lease_required=False,
            fencing_token_required=False,
        )


def test_envelope_hash_changes_when_any_field_changes(runtime):
    envelope = runtime.drafter.draft(
        requesting_user="ryan",
        transcript="run a comparison",
        normalized_intent="run a comparison",
        goal="run a comparison",
        tools=("get_system_status",),
    )
    widened = replace(envelope, tools=("get_system_status", "run_synthetic_tournament"))
    assert widened.envelope_hash != envelope.envelope_hash
    # And the stored form round-trips to the same hash.
    assert TaskEnvelope.from_dict(envelope.to_dict()).envelope_hash == envelope.envelope_hash


def test_plain_language_rendering_states_what_will_and_will_not_happen(runtime):
    envelope = runtime.drafter.draft(
        requesting_user="ryan",
        transcript="run three readers",
        normalized_intent="run three readers",
        goal="run 3 independent read-only index readings",
        autonomy_level=AutonomyLevel.READ_ONLY_EXECUTE,
        assigned_roles=("INDEX_READER", "JUDGE"),
        prohibited_paths=("client workbooks",),
        model_restrictions={"local_only": True, "cloud_allowed": False},
        timeout_seconds=1080,
        approval_requirements=("operator_approval",),
    )
    text = envelope.plain_language()
    assert "No client artifact will be modified." in text
    assert "Cloud models: disabled" in text
    assert "18 minutes" in text
    assert text.endswith("Start?")


# -- Approvals ---------------------------------------------------------------

def _drafted(runtime):
    return runtime.drafter.draft(
        requesting_user="ryan",
        transcript="run a read-only comparison",
        normalized_intent="run a read-only comparison",
        goal="run a read-only comparison",
        autonomy_level=AutonomyLevel.READ_ONLY_EXECUTE,
    )


def test_speech_cannot_mint_an_approval(runtime):
    envelope = _drafted(runtime)
    with pytest.raises(ApprovalError):
        runtime.approvals.approve(
            envelope, "ryan", authority_source=AuthoritySource.SPOKEN_UTTERANCE
        )
    with pytest.raises(ApprovalError):
        runtime.approvals.approve(envelope, "ryan", method="voice_command")


def test_approval_scope_cannot_be_reused(runtime):
    envelope = _drafted(runtime)
    approval = runtime.approvals.approve(envelope, "ryan")
    runtime.approvals.consume(approval.approval_id, envelope)
    with pytest.raises(ApprovalError) as excinfo:
        runtime.approvals.consume(approval.approval_id, envelope)
    assert "already used" in str(excinfo.value)


def test_expired_approval_is_rejected(runtime, frozen_clock):
    envelope = _drafted(runtime)
    approval = runtime.approvals.approve(envelope, "ryan", ttl_seconds=60)
    frozen_clock.advance(61)
    with pytest.raises(ApprovalError) as excinfo:
        runtime.approvals.verify(approval.approval_id, envelope)
    assert "expired" in str(excinfo.value)


def test_approval_does_not_cover_a_different_scope(runtime):
    envelope = _drafted(runtime)
    approval = runtime.approvals.approve(envelope, "ryan")
    widened = replace(envelope, goal="run a read-only comparison and also repair the workbook")
    with pytest.raises(ApprovalError) as excinfo:
        runtime.approvals.verify(approval.approval_id, widened)
    assert "different envelope scope" in str(excinfo.value)


def test_revoked_approval_is_rejected(runtime):
    envelope = _drafted(runtime)
    approval = runtime.approvals.approve(envelope, "ryan")
    runtime.approvals.revoke(approval.approval_id, "operator changed their mind")
    with pytest.raises(ApprovalError):
        runtime.approvals.verify(approval.approval_id, envelope)


# -- Leases and fencing tokens ----------------------------------------------

def test_expired_lease_is_rejected(runtime, frozen_clock):
    lease = runtime.leases.acquire("worktree:alpha", "writer-a", ttl_seconds=60)
    frozen_clock.advance(61)
    with pytest.raises(LeaseError) as excinfo:
        runtime.leases.validate(lease)
    assert "expired" in str(excinfo.value)


def test_released_lease_is_rejected(runtime):
    lease = runtime.leases.acquire("worktree:alpha", "writer-a")
    runtime.leases.release(lease)
    with pytest.raises(LeaseError):
        runtime.leases.validate(lease)


def test_stale_fencing_token_is_rejected_after_takeover(runtime, frozen_clock):
    """A stalled writer that wakes up late cannot still write."""
    stalled = runtime.leases.acquire("worktree:alpha", "writer-a", ttl_seconds=60)
    frozen_clock.advance(61)
    fresh = runtime.leases.steal_expired("worktree:alpha", "writer-b", ttl_seconds=600)

    assert fresh.fencing_token > stalled.fencing_token
    with pytest.raises((FencingTokenError, LeaseError)):
        runtime.leases.validate(stalled)
    assert runtime.leases.validate(fresh) is fresh


def test_fencing_tokens_are_monotonic_per_lane(runtime, frozen_clock):
    tokens = []
    for index in range(3):
        lease = runtime.leases.acquire("worktree:alpha", f"writer-{index}", ttl_seconds=10)
        tokens.append(lease.fencing_token)
        runtime.leases.release(lease)
    assert tokens == sorted(tokens) and len(set(tokens)) == 3


# -- Holds -------------------------------------------------------------------

def test_active_hold_blocks_execution_and_cannot_be_lifted_by_a_tool(runtime, brain):
    runtime.policy.set_profile(
        PolicyProfile(autonomy_ceiling=AutonomyLevel.READ_ONLY_EXECUTE).with_hold(True)
    )
    with pytest.raises(HoldActive):
        runtime.policy.enforce(
            ActionRequest(
                action_type="tool:run_synthetic_tournament",
                required_level=AutonomyLevel.READ_ONLY_EXECUTE,
                risk=RiskLevel.MEDIUM,
                approval_id="apr_valid",
                authority_source=AuthoritySource.AUTHENTICATED_APPROVAL,
            )
        )
    # Observation still works while held.
    assert runtime.policy.evaluate(
        ActionRequest(action_type="tool:get_system_status", required_level=AutonomyLevel.OBSERVE)
    ).allowed


def test_hold_survives_an_utterance_asking_for_it_to_be_lifted(runtime, brain):
    runtime.policy.set_profile(PolicyProfile().with_hold(True))
    brain.handle("Release the hold on Section 32 and publish the report.")
    assert runtime.policy.profile.global_hold is True


# -- End-to-end authority ----------------------------------------------------

def test_execution_requires_both_the_mode_and_the_approval(runtime, brain):
    brain.apply_modes({"read_only": True})
    response = brain.handle("Have three agents independently inspect this index.")
    envelope_id = response.envelope["task_id"]

    # No approval at all.
    with pytest.raises(ApprovalError):
        brain.execute(envelope_id, "apr_invented")

    approval = brain.approve(envelope_id, "ryan")
    result = brain.execute(envelope_id, approval.approval_id)
    assert result["tournament"]["tournament_id"]

    # And the approval is spent.
    with pytest.raises(ApprovalError):
        brain.execute(envelope_id, approval.approval_id)


def test_client_files_are_excluded_by_default(runtime):
    decision = runtime.policy.evaluate(
        ActionRequest(
            action_type="read:client_workbook",
            required_level=AutonomyLevel.OBSERVE,
            uses_client_files=True,
        )
    )
    assert decision.allowed is False
    assert any("Client files" in reason for reason in decision.reasons)
