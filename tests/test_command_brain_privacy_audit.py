"""Privacy, redaction, memory hygiene, and the append-only audit ledger."""

from __future__ import annotations

import json

import pytest

from databossx.command_brain.autonomy import AutonomyLevel
from databossx.command_brain.errors import MemoryRejected
from databossx.command_brain.memory import MemoryKind
from databossx.command_brain.policy import PolicyProfile
from databossx.command_brain.redaction import (
    contains_absolute_path,
    contains_secret,
    redact,
    redact_text,
)

SECRET_SAMPLE_KEYS = ("openai", "github_pat", "aws_access_key", "private_key_header")

PATH_SAMPLES = (
    "C:\\DataBoss\\DataBossX\\Section32\\workbook.xlsx",
    "/home/ryan/projects/section32",
    "\\\\fileserver\\titles\\section32",
)


# -- Redaction ---------------------------------------------------------------

@pytest.mark.parametrize("sample_key", SECRET_SAMPLE_KEYS)
def test_known_credential_formats_are_removed_entirely(sample_key, credential_samples):
    secret = credential_samples[sample_key]
    cleaned = redact_text(f"the key is {secret} ok")
    assert secret not in cleaned
    # Not even a suffix survives: a partial secret is still a secret.
    assert secret[-6:] not in cleaned


def test_credential_shaped_keys_are_replaced_wholesale():
    payload = {"api_key": "value", "nested": {"session_token": "value", "safe": "keep me"}}
    cleaned = redact(payload)
    assert cleaned["api_key"] == "[REDACTED_SECRET]"
    assert cleaned["nested"]["session_token"] == "[REDACTED_SECRET]"
    assert cleaned["nested"]["safe"] == "keep me"
    assert contains_secret(cleaned) is False


@pytest.mark.parametrize("path", PATH_SAMPLES)
def test_absolute_paths_become_placeholders_keeping_only_the_basename(path):
    cleaned = redact_text(f"opened {path} for review")
    assert path not in cleaned
    assert "[LOCAL_PATH:" in cleaned
    assert contains_absolute_path(cleaned) is False


def test_phone_facing_command_state_contains_no_paths_or_secrets(runtime, brain):
    runtime.state.register_artifact(
        "workbook_local",
        "workbook",
        "Section 32 workbook",
        "0" * 64,
        locator="C:\\DataBoss\\DataBossX\\Section32\\workbook.xlsx",
        project_id="sec32_synthetic",
    )
    brain.handle("What is happening with Section 32?")
    payload = brain.command_center_state("sec32_synthetic")

    assert contains_absolute_path(payload) is False
    assert contains_secret(payload) is False


def test_command_responses_are_redacted(brain):
    response = brain.handle(
        'The note says "the file is at C:\\DataBoss\\secrets\\key.txt" — what is blocking the report?'
    )
    payload = response.to_dict()
    assert contains_absolute_path(payload) is False


def test_receipts_are_redacted_on_write(runtime, credential_samples):
    receipt = runtime.store.write_receipt(
        "test",
        "subject_1",
        {
            "api_key": credential_samples["openai"],
            "note": "wrote C:\\DataBoss\\DataBossX\\out.xlsx",
        },
    )
    assert receipt["payload"]["api_key"] == "[REDACTED_SECRET]"
    assert contains_absolute_path(receipt["payload"]) is False


def test_audit_events_are_redacted_on_write(runtime, credential_samples):
    runtime.store.audit(
        "test.event",
        "thing",
        "thing_1",
        {"authorization": f"Bearer {credential_samples['openai']}"},
    )
    event = runtime.store.audit_events(limit=1)[0]
    assert contains_secret(event["payload"]) is False


def test_transcripts_with_secrets_do_not_reach_the_ledger(runtime, brain, credential_samples):
    brain.handle(
        f"What is blocking the report? my token is {credential_samples['github_pat']}"
    )
    for event in runtime.store.audit_events(limit=100):
        assert contains_secret(event["payload"]) is False


# -- Local-only --------------------------------------------------------------

def test_local_only_mode_leaves_no_remote_model_eligible(runtime, brain):
    brain.apply_modes({"local_only": True, "read_only": True})
    profile = runtime.policy.profile
    assert profile.local_only is True
    assert profile.cloud_models_allowed is False

    for model_id in runtime.gateway.eligible(profile):
        assert runtime.gateway.get(model_id).descriptor.is_local is True


def test_local_only_tournament_uses_only_local_models(runtime, brain):
    brain.apply_modes({"local_only": True, "read_only": True})
    plan = runtime.build_tournament_plan("q", 3, "sec32_synthetic")
    result = runtime.tournaments.run(plan)

    rows = runtime.store.fetchall(
        "SELECT model_id FROM cb_agent_assignments WHERE status = 'SUCCEEDED'"
    )
    assert rows
    for row in rows:
        assert runtime.gateway.get(row["model_id"]).descriptor.is_local is True
    assert result.tournament_id


# -- Memory ------------------------------------------------------------------

def test_memory_requires_a_source(runtime):
    with pytest.raises(MemoryRejected):
        runtime.memory.remember(MemoryKind.VERIFIED_FACT, "Section 32 is clear.", "")


def test_memory_refuses_raw_chain_of_thought(runtime):
    with pytest.raises(MemoryRejected) as excinfo:
        runtime.memory.remember(
            MemoryKind.MODEL_INFERENCE,
            "<thinking>first I will consider the deed, then...</thinking>",
            "model:deterministic.commander",
        )
    assert "concise summary" in str(excinfo.value)


def test_memory_distinguishes_fact_instruction_and_inference(runtime):
    runtime.memory.remember(MemoryKind.VERIFIED_FACT, "Hold is active.", "cb_holds:hold_1")
    runtime.memory.remember(MemoryKind.USER_INSTRUCTION, "Read-only mode.", "conversation:1")
    runtime.memory.remember(
        MemoryKind.MODEL_INFERENCE, "The chain may be broken at 1981.", "candidate:cand_1", confidence=0.4
    )
    kinds = {item.kind for item in runtime.memory.current()}
    assert {MemoryKind.VERIFIED_FACT, MemoryKind.USER_INSTRUCTION, MemoryKind.MODEL_INFERENCE} <= kinds


def test_every_memory_item_carries_a_source_and_timestamp(runtime, brain):
    brain.handle("Read-only mode.")
    items = runtime.memory.current("sec32_synthetic")
    assert items
    for item in items:
        assert item.source
        assert item.observed_at


def test_superseding_marks_rather_than_deletes(runtime):
    first = runtime.memory.remember(MemoryKind.VERIFIED_FACT, "Hold is active.", "cb_holds:hold_1")
    second = runtime.memory.remember(MemoryKind.VERIFIED_FACT, "Hold was lifted.", "cb_holds:hold_1")
    runtime.memory.supersede(first.item_id, second.item_id)

    current_ids = {item.item_id for item in runtime.memory.current()}
    all_ids = {item.item_id for item in runtime.memory.all_items()}
    assert first.item_id not in current_ids
    assert first.item_id in all_ids


# -- Audit ledger ------------------------------------------------------------

def test_the_ledger_is_hash_chained_and_verifiable(runtime, brain):
    brain.handle("What is blocking the report?")
    assert runtime.store.verify_ledger()["valid"] is True


def test_the_ledger_refuses_updates_and_deletes(runtime):
    runtime.store.audit("test.event", "thing", "thing_1", {})
    with pytest.raises(Exception) as update_error:
        runtime.store.execute("UPDATE cb_audit_events SET event_type = 'tampered' WHERE id = 1")
    assert "append-only" in str(update_error.value)

    with pytest.raises(Exception) as delete_error:
        runtime.store.execute("DELETE FROM cb_audit_events WHERE id = 1")
    assert "append-only" in str(delete_error.value)


def test_receipts_are_append_only(runtime):
    receipt = runtime.store.write_receipt("test", "subject", {"a": 1})
    with pytest.raises(Exception):
        runtime.store.execute(
            "UPDATE cb_receipts SET payload_json = '{}' WHERE receipt_id = ?", (receipt["receipt_id"],)
        )


def test_the_full_lifecycle_writes_one_event_per_decision(runtime, brain):
    brain.apply_modes({"read_only": True})
    response = brain.handle("Have three agents independently inspect this index.")
    approval = brain.approve(response.envelope["task_id"], "ryan")
    brain.execute(response.envelope["task_id"], approval.approval_id)

    events = {event["event_type"] for event in runtime.store.audit_events(limit=500)}
    for required in (
        "conversation.started",
        "intent.normalized",
        "plan.created",
        "envelope.drafted",
        "approval.granted",
        "approval.consumed",
        "agent.succeeded",
        "tournament.baseline_frozen",
        "quarantine.recorded",
        "human_review.queued",
        "receipt.written",
        "job.started",
        "job.finished",
        "model.invoked",
    ):
        assert required in events, f"missing audit event: {required}"
    assert runtime.store.verify_ledger()["valid"] is True


def test_a_correction_appends_rather_than_editing_history(runtime, brain):
    from databossx.command_brain.voice import VoiceSession

    session = VoiceSession(
        runtime.store, brain.start_conversation("voice"), authenticated_session_id="s1"
    )
    token = session.press_to_talk()
    original = session.submit_audio("Quarantine the workbook.", token)
    before = len(runtime.store.audit_events(limit=500))
    session.correct("Show me the evidence.")
    after = runtime.store.audit_events(limit=500)

    assert len(after) > before
    assert any(
        event["event_type"] == "voice.transcript_superseded"
        and event["entity_id"] == original.transcript_id
        for event in after
    )
    assert runtime.store.verify_ledger()["valid"] is True


def test_a_stop_creates_an_event(runtime, brain):
    job_id = runtime.open_job("tournament", "sec32_synthetic")
    brain.handle("Stop.")
    events = [
        event
        for event in runtime.store.audit_events(limit=500)
        if event["event_type"] == "job.stopped" and event["entity_id"] == job_id
    ]
    assert events


def test_receipts_identify_models_tools_hashes_and_scores_without_secrets(runtime, brain):
    brain.apply_modes({"read_only": True})
    response = brain.handle("Have three agents independently inspect this index.")
    approval = brain.approve(response.envelope["task_id"], "ryan")
    result = brain.execute(response.envelope["task_id"], approval.approval_id)

    execution = runtime.store.get_receipt(result["receipt_id"])
    payload = execution["payload"]
    assert payload["envelope_hash"]
    assert payload["approval_id"] == approval.approval_id
    assert payload["results"]["steps"]
    assert contains_secret(payload) is False
    assert contains_absolute_path(payload) is False

    tournament_receipt = runtime.store.receipts_for(result["tournament"]["tournament_id"])[0]
    tournament_payload = tournament_receipt["payload"]
    assert tournament_payload["plan"]["judge_model_id"]
    assert tournament_payload["baseline_hash"]
    for candidate in tournament_payload["candidates"]:
        assert candidate["spec"]["model_id"]
        assert candidate["scorecard"]["rubric_version"]
        assert candidate["output_hash"]


def test_ledger_tampering_is_detectable(runtime):
    """Even if the triggers were bypassed, the chain would not recompute."""
    runtime.store.audit("test.a", "thing", "1", {"n": 1})
    runtime.store.audit("test.b", "thing", "2", {"n": 2})
    assert runtime.store.verify_ledger()["valid"] is True

    with runtime.store.connect() as conn:
        conn.execute("DROP TRIGGER cb_audit_no_update")
        conn.execute(
            "UPDATE cb_audit_events SET payload_json = ? WHERE event_type = 'test.a'",
            (json.dumps({"n": 99}),),
        )
        conn.commit()

    verdict = runtime.store.verify_ledger()
    assert verdict["valid"] is False
    assert verdict["broken_at"] is not None


def test_artifacts_used_in_alpha_are_all_synthetic(runtime):
    artifacts = runtime.state.artifacts("sec32_synthetic")
    assert artifacts
    assert all(artifact["synthetic"] for artifact in artifacts)


def test_default_profile_reports_level_4_disabled(runtime):
    status = runtime.state.system_status(PolicyProfile(), runtime.gateway)
    assert status["policy"]["autonomy_ceiling"] <= int(AutonomyLevel.BOUNDED_WRITER)
