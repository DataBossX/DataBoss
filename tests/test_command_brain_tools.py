"""Tool registry guarantees.

Tools take stable IDs. They do not take paths, commands, locators, or
credentials, and they cannot widen their own permissions.
"""

from __future__ import annotations

import pytest

from databossx.command_brain.autonomy import AutonomyLevel
from databossx.command_brain.errors import (
    RegistryFrozen,
    SchemaViolation,
    ToolInputRejected,
    ToolNotRegistered,
)
from databossx.command_brain.state import ArtifactNotRegistered
from databossx.command_brain.tools import ToolDefinition, scan_tool_input

EXPECTED_TOOLS = {
    "get_system_status",
    "get_project_status",
    "get_active_jobs",
    "get_open_defects",
    "get_pending_approvals",
    "get_release_holds",
    "get_artifact_metadata",
    "get_artifact_hash",
    "verify_artifact_hash",
    "compare_artifact_metadata",
    "read_validation_receipt",
    "inspect_registered_workbook_read_only",
    "inspect_registered_images_read_only",
    "run_registered_test_suite",
    "draft_task_envelope",
    "draft_review_request",
    "assign_read_only_agent",
    "create_tournament_plan",
    "run_synthetic_tournament",
    "compare_candidate_scores",
    "quarantine_candidate",
    "request_human_review",
    "explain_finding",
    "stop_queued_job",
}


def test_the_allowlist_is_exactly_the_declared_tool_set(runtime):
    assert set(runtime.tools.tool_ids()) == EXPECTED_TOOLS


def test_unknown_tool_is_rejected(runtime):
    with pytest.raises(ToolNotRegistered):
        runtime.tools.invoke("delete_everything", {}, runtime.tool_context())


def test_arbitrary_shell_command_is_rejected(runtime):
    with pytest.raises(ToolInputRejected) as excinfo:
        runtime.tools.invoke(
            "get_project_status", {"project_id": "sec32; rm -rf /"}, runtime.tool_context()
        )
    assert "shell" in str(excinfo.value).lower() or "pattern" in str(excinfo.value).lower()


@pytest.mark.parametrize(
    "value",
    [
        "C:\\DataBoss\\DataBossX\\workbook.xlsx",
        "/home/ryan/secrets.env",
        "\\\\fileserver\\share\\report.xlsx",
        "../../etc/passwd",
    ],
)
def test_filesystem_paths_are_rejected_everywhere(value):
    with pytest.raises(ToolInputRejected):
        scan_tool_input({"artifact_id": value})


def test_credential_shaped_input_is_rejected():
    with pytest.raises(ToolInputRejected):
        scan_tool_input({"api_key": "anything"})
    with pytest.raises(ToolInputRejected):
        scan_tool_input({"note": "sk-abcdefghijklmnopqrstuvwxyz012345"}, {"properties": {"note": {}}})


def test_unregistered_artifact_is_rejected(runtime):
    with pytest.raises(ArtifactNotRegistered):
        runtime.tools.invoke(
            "get_artifact_metadata", {"artifact_id": "not_a_real_artifact"}, runtime.tool_context()
        )


def test_tool_schema_violation_is_rejected(runtime):
    with pytest.raises(SchemaViolation):
        runtime.tools.invoke("get_project_status", {}, runtime.tool_context())
    with pytest.raises(SchemaViolation):
        runtime.tools.invoke(
            "create_tournament_plan",
            {"question": "compare readings", "candidate_count": 99},
            runtime.tool_context(),
        )


def test_a_tool_cannot_be_added_after_the_registry_is_frozen(runtime):
    assert runtime.tools.frozen is True
    with pytest.raises(RegistryFrozen):
        runtime.tools.register(
            ToolDefinition(
                tool_id="escalate_privileges",
                description="should never be registrable",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                handler=lambda ctx, params: {},
            )
        )


def test_a_tool_handler_has_no_route_to_widen_permissions(runtime):
    context = runtime.tool_context()
    # The context deliberately exposes no registry and no policy engine.
    assert not hasattr(context, "policy")
    assert not hasattr(context, "registry")
    assert not hasattr(context, "grant")


def test_no_tool_declares_an_external_effect(runtime):
    assert all(tool["external_effect"] is False for tool in runtime.tools.list_tools())


def test_no_tool_can_clear_a_hold(runtime):
    """Holds can be read and never lifted: there is no clear-the-hold verb."""
    hold_tools = [tool for tool in runtime.tools.list_tools() if "hold" in tool["tool_id"]]
    assert hold_tools, "expected at least one hold-reading tool"
    assert all(tool["read_only"] and not tool["mutates_state"] for tool in hold_tools)

    runtime.store.execute(
        "INSERT INTO cb_holds (hold_id, project_id, scope, reason, active, created_at) "
        "VALUES ('hold_1', 'sec32_synthetic', 'release', 'Examiner review outstanding', 1, ?)",
        (runtime.store.now(),),
    )
    before = runtime.state.release_holds("sec32_synthetic")
    for tool_id in runtime.tools.tool_ids():
        assert "clear" not in tool_id and "lift" not in tool_id
    assert runtime.state.release_holds("sec32_synthetic") == before
    assert before[0]["active"] == 1


def test_read_only_tools_report_state_with_a_timestamp(runtime):
    result = runtime.tools.invoke("get_system_status", {}, runtime.tool_context())
    assert result.output["observed_at"]
    assert result.output["ledger"]["valid"] is True


def test_artifact_metadata_never_returns_a_locator(runtime):
    page = runtime.corpus.pages[0].page_id
    result = runtime.tools.invoke(
        "get_artifact_metadata", {"artifact_id": page}, runtime.tool_context()
    )
    assert "locator" not in result.output
    assert result.output["sha256"] == runtime.corpus.page_hash(page)


def test_index_page_inspection_returns_structure_not_transcription(runtime):
    with runtime.policy.elevated(AutonomyLevel.READ_ONLY_EXECUTE):
        result = runtime.tools.invoke(
            "inspect_registered_images_read_only",
            {"artifact_id": runtime.corpus.pages[0].page_id},
            runtime.tool_context(),
        )
    cells = result.output["rows"][0]["cells"]
    assert all(set(cell) == {"legibility"} for cell in cells.values())


def test_test_suite_runner_rejects_anything_unregistered(runtime):
    with runtime.policy.elevated(AutonomyLevel.READ_ONLY_EXECUTE):
        with pytest.raises(ToolInputRejected):
            runtime.tools.invoke(
                "run_registered_test_suite", {"suite_id": "make_install"}, runtime.tool_context()
            )
        result = runtime.tools.invoke(
            "run_registered_test_suite",
            {"suite_id": "command_brain_selftest"},
            runtime.tool_context(),
        )
    assert result.output["state"] == "PASS"


def test_policy_gate_selftest_confirms_the_two_hard_refusals(runtime):
    with runtime.policy.elevated(AutonomyLevel.READ_ONLY_EXECUTE):
        result = runtime.tools.invoke(
            "run_registered_test_suite",
            {"suite_id": "command_brain_policy_gates"},
            runtime.tool_context(),
        )
    assert result.output["state"] == "PASS"
    names = {check["name"] for check in result.output["checks"]}
    assert names == {"external_effect_denied", "speech_is_not_authority"}


def test_every_invocation_is_recorded_even_when_refused(runtime):
    with pytest.raises(ToolNotRegistered):
        runtime.tools.invoke("nope", {}, runtime.tool_context())
    runtime.tools.invoke("get_system_status", {}, runtime.tool_context())

    rows = runtime.store.fetchall("SELECT tool_id, status FROM cb_tool_invocations ORDER BY created_at")
    statuses = {(row["tool_id"], row["status"]) for row in rows}
    assert ("get_system_status", "OK") in statuses


def test_rejected_invocations_are_recorded_with_an_error_code(runtime):
    with pytest.raises(ToolInputRejected):
        runtime.tools.invoke(
            "get_project_status", {"project_id": "a | b"}, runtime.tool_context()
        )
    row = runtime.store.fetchone(
        "SELECT status, error_code FROM cb_tool_invocations WHERE tool_id = 'get_project_status'"
    )
    assert row["status"] == "REJECTED"
    assert row["error_code"] == "TOOL_INPUT_REJECTED"


def test_stop_and_quarantine_stay_available_at_low_autonomy(runtime):
    """The emergency brake must not itself need a signature."""
    tools = {tool["tool_id"]: tool for tool in runtime.tools.list_tools()}
    assert tools["stop_queued_job"]["required_level"] <= int(AutonomyLevel.OBSERVE)
    assert tools["quarantine_candidate"]["required_level"] <= int(AutonomyLevel.DRAFT)
