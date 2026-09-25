"""Regression tests for the /control-truth health projection endpoint."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from databossx.api import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(str(tmp_path / "databossx.sqlite3"))
    return TestClient(app)


def _writer_gate_payload(**overrides):
    base = {
        "writer_seat": "P12",
        "writer_instance": "claude-session-1",
        "exact_preimage_sha256": "a" * 64,
        "observed_preimage_sha256": "a" * 64,
        "exact_target_id": "drive-id-1",
        "observed_target_id": "drive-id-1",
        "lease_holder": "claude-session-1",
        "lease_expires_at": "2026-09-25T12:05:00Z",
        "heartbeat_at": "2026-09-25T11:59:55Z",
        "collision_count": 0,
        "now": "2026-09-25T12:00:00Z",
    }
    base.update(overrides)
    return base


def _integrity_payload(**overrides):
    base = {
        "outer_sha256": "s" * 64,
        "member_sha256": {"a.xlsx": "m" * 64},
        "failures": [],
        "clean_cycle_streak": 5,
        "required_clean_cycles": 5,
    }
    base.update(overrides)
    return base


def test_healthz_still_works(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_control_truth_reports_ready(client):
    payload = {
        "section": "12-45N-76W",
        "source_identity_previous": [{"source_identity": "a", "disposition": "INCLUDE"}],
        "source_identity_current": [{"source_identity": "a", "disposition": "INCLUDE"}],
        "source_identity_expected_count": 1,
        "coverage_records": [
            {"source_identity": "a", "disposition": "INCLUDE", "pixel_reviewed": True}
        ],
        "writer_gate": _writer_gate_payload(),
        "integrity": _integrity_payload(),
    }
    resp = client.post("/control-truth", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "READY"
    assert body["section"] == "12-45N-76W"


def test_control_truth_denies_stale_writer_and_never_leaks_identities(client):
    payload = {
        "section": "14-45N-76W",
        "source_identity_previous": [
            {"source_identity": "SYNTH-1001.pdf", "disposition": "INCLUDE"},
            {"source_identity": "SYNTH-1002.pdf", "disposition": "INCLUDE"},
        ],
        "source_identity_current": [
            {"source_identity": "SYNTH-1001.pdf", "disposition": "INCLUDE"},
        ],
        "source_identity_expected_count": 2,
        "coverage_records": [
            {
                "source_identity": "SYNTH-1001.pdf",
                "disposition": "INCLUDE",
                "ocr_reviewed": True,
                "pixel_reviewed": False,
            }
        ],
        "writer_gate": _writer_gate_payload(heartbeat_at="2026-09-25T11:50:00Z"),
        "integrity": _integrity_payload(),
    }
    resp = client.post("/control-truth", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "HOLD"
    assert body["writer_gate_passed"] is False
    assert "HEARTBEAT_STALE_OR_ABSENT" in body["writer_gate_reasons"]

    dumped = repr(body)
    assert "SYNTH-1001" not in dumped
    assert "SYNTH-1002" not in dumped
