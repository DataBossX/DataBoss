"""Tests for the optional foundation audit-store bridge."""

import json
from pathlib import Path

import pytest

from databossx.audit_bridge import read_audit_events, record_run
from databossx.command_center import run_project
from databossx.demo import build_golden_demo


@pytest.fixture()
def golden(tmp_path):
    root = tmp_path / "G"
    build_golden_demo(root)
    return root


def test_run_without_audit_writes_no_db(golden, tmp_path):
    out = tmp_path / "out"
    result = run_project("golden_demo", root=str(golden), output_dir=str(out))
    assert "audit_db" not in result.deliverables
    assert not (out / "runtime").exists()


def test_run_with_audit_records_events_and_hashes(golden, tmp_path):
    out = tmp_path / "out"
    result = run_project("golden_demo", root=str(golden), output_dir=str(out),
                         record_audit=True)
    db = result.deliverables.get("audit_db")
    assert db and Path(db).exists()

    events = read_audit_events(Path(db), "golden_demo", limit=50)
    types = {e["event_type"] for e in events}
    assert "run.completed" in types
    assert "deliverable.produced" in types

    # Every deliverable event carries a real content hash.
    deliv = [json.loads(e["payload_json"]) for e in events
             if e["event_type"] == "deliverable.produced"]
    assert deliv
    for payload in deliv:
        assert len(payload["sha256"]) == 64
        assert payload["bytes"] > 0


def test_record_run_is_best_effort(tmp_path):
    # Pointing at an unwritable/odd location must not raise -- it returns None.
    # (Here we give a valid dir but assert the contract: never raises.)
    got = record_run(tmp_path / "o", project_name="P", project_key="p",
                     jurisdiction="OK", rag="GREEN", counts={}, defect_count=0,
                     deliverables={})
    # Either it wrote a db (str) or degraded to None -- never an exception.
    assert got is None or Path(got).exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
