"""The controlled demo, the Command Center surface, and end-to-end determinism."""

from __future__ import annotations

import json

import pytest

from databossx.command_brain.demo import DEMO_PROJECT, run_demo
from databossx.command_brain.redaction import contains_absolute_path, contains_secret
from databossx.command_brain.server import make_server


def test_controlled_demo_passes_every_safety_check(tmp_path):
    summary = run_demo(tmp_path / "demo.db", verbose=False)
    assert summary["all_checks_passed"] is True, summary["checks"]


def test_controlled_demo_preserves_the_baseline_bytes(tmp_path):
    summary = run_demo(tmp_path / "demo.db", verbose=False)
    assert summary["checks"]["baseline_bytes_unchanged"] is True


def test_controlled_demo_quarantines_the_fabricating_candidate(tmp_path):
    summary = run_demo(tmp_path / "demo.db", verbose=False)
    statuses = {c["profile"]: c["status"] for c in summary["candidates"]}
    assert statuses["fabricating"] == "QUARANTINED"
    assert statuses["transposing"] == "REJECTED"


def test_controlled_demo_uses_only_simulated_readers(tmp_path):
    summary = run_demo(tmp_path / "demo.db", verbose=False)
    assert all(candidate["simulated"] for candidate in summary["candidates"])
    assert summary["voice"]["simulated"] is True
    assert "SIMULATED" in summary["voice"]["note"]


def test_controlled_demo_routes_uncertainty_to_a_human(tmp_path):
    summary = run_demo(tmp_path / "demo.db", verbose=False)
    assert summary["human_review_items"] > 0
    assert summary["consensus"]["vote_overruled_by_source"]


def test_controlled_demo_is_deterministic(tmp_path):
    first = run_demo(tmp_path / "one.db", verbose=False)
    second = run_demo(tmp_path / "two.db", verbose=False)
    assert first["baseline_output_hash"] == second["baseline_output_hash"]
    assert [c["aggregate"] for c in first["candidates"]] == [
        c["aggregate"] for c in second["candidates"]
    ]
    assert first["envelope_hash"] == second["envelope_hash"]


def test_controlled_demo_payload_is_phone_safe(tmp_path):
    summary = run_demo(tmp_path / "demo.db", verbose=False)
    shareable = {key: value for key, value in summary.items() if key != "db_path"}
    assert contains_secret(shareable) is False
    assert contains_absolute_path(shareable) is False


def test_command_center_state_is_renderable_and_complete(brain, runtime):
    brain.handle("What is happening with Section 32?")
    state = brain.command_center_state(DEMO_PROJECT)

    for key in (
        "policy", "autonomy_level_name", "global_hold", "system", "pending_approvals",
        "human_review_queue", "models", "tools", "recent_events", "memory",
        "simulated_components", "priority_actions",
    ):
        assert key in state
    assert "START READ-ONLY TOURNAMENT" in state["priority_actions"]
    assert "Fix everything" not in " ".join(state["priority_actions"])
    assert state["simulated_components"], "simulated components must be visible"
    json.dumps(state, default=str)  # renderable without custom encoders


def test_server_refuses_a_non_loopback_bind(brain):
    with pytest.raises(RuntimeError) as excinfo:
        make_server(brain, host="0.0.0.0", port=8788)
    assert "non-loopback" in str(excinfo.value)


def test_server_binds_loopback_and_mints_a_csrf_token(brain):
    server = make_server(brain, host="127.0.0.1", port=0)
    try:
        state = server.command_center_state
        assert state.csrf_token and state.session_id
        assert state.csrf_token != state.session_id
    finally:
        server.server_close()


def test_ui_page_is_self_contained(tmp_path):
    from databossx.command_brain.server import UI_PATH

    html = UI_PATH.read_text(encoding="utf-8")
    for forbidden in ("http://", "https://", "cdn.", "<script src="):
        assert forbidden not in html, f"Command Center must not reference {forbidden}"
    assert "GLOBAL HOLD ACTIVE" in html
    assert "STOP ALL QUEUED WORK" in html
