"""Unified synthetic manifest accepted by both Horizon and DataBossX loaders."""

from __future__ import annotations

import json
from pathlib import Path

from databossx.control_plane import ControlPlane
from horizon.project_manifest import load_project_manifest

FIXTURE = Path("examples/projects/SYNTHETIC-DEMO/project_manifest.json")
PROJECT_ID = "SYNTHETIC-DEMO-001"


def test_unified_fixture_loads_through_horizon():
    manifest = load_project_manifest(FIXTURE)
    assert manifest.project_id == PROJECT_ID
    assert manifest.source_policy == "IMMUTABLE_READ_ONLY"
    assert len(manifest.required_checks) == 5
    assert manifest.release_policy["human_gate"] == "G7"
    assert manifest.release_policy["technical_verification_is_not_release"] is True
    assert manifest.metadata["county"] == "Fictional County"
    assert len(manifest.candidates) == 1
    assert manifest.candidates[0].reported_sha256 == (
        "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    )


def test_unified_fixture_loads_through_control_plane(tmp_path):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    control = ControlPlane(tmp_path / "control.sqlite3", intake_roots=[tmp_path])
    control.initialize()
    project_id = control.create_project(raw)
    assert project_id == PROJECT_ID

    with control.connect() as connection:
        row = connection.execute(
            """SELECT payload_json FROM manifest_revisions
               WHERE project_id = ? ORDER BY created_at DESC LIMIT 1""",
            (project_id,),
        ).fetchone()
    payload = json.loads(row["payload_json"])
    assert payload["required_checks"] == raw["required_checks"]
    assert payload["release_policy"] == raw["release_policy"]
    assert payload["candidate_deliverables"] == raw["candidate_deliverables"]
