"""Integration tests for the Landman Helper control-truth projection."""

from __future__ import annotations

import datetime as dt

from horizon.control_truth import build_control_truth
from horizon.package_gate import GateReport
from horizon.source_identity_guard import source_identity_guard
from horizon.writer_gate import WriterGateState

NOW = dt.datetime(2026, 9, 25, 12, 0, 0, tzinfo=dt.timezone.utc)


def _clean_writer_gate(**overrides):
    base = dict(
        writer_seat="P12",
        writer_instance="claude-session-1",
        exact_preimage_sha256="a" * 64,
        observed_preimage_sha256="a" * 64,
        exact_target_id="drive-id-1",
        observed_target_id="drive-id-1",
        lease_holder="claude-session-1",
        lease_expires_at=NOW + dt.timedelta(minutes=5),
        heartbeat_at=NOW - dt.timedelta(seconds=5),
        collision_count=0,
        now=NOW,
    )
    base.update(overrides)
    return WriterGateState(**base)


def _clean_gate_report(**overrides):
    base = dict(outer_sha256="s" * 64, members={"a.xlsx": "m" * 64}, failures=[])
    base.update(overrides)
    return GateReport(**base)


def test_ready_requires_every_gate_to_pass_at_once():
    previous = [{"source_identity": "a", "disposition": "INCLUDE"}]
    current = [{"source_identity": "a", "disposition": "INCLUDE"}]
    si_report = source_identity_guard(previous, current, expected_count=1)
    records = [{"source_identity": "a", "disposition": "INCLUDE", "pixel_reviewed": True}]

    projection = build_control_truth(
        "12-45N-76W",
        source_identity=si_report,
        writer_gate=_clean_writer_gate(),
        source_records=records,
        gate_report=_clean_gate_report(),
        clean_cycle_streak=5,
        required_clean_cycles=5,
    )

    assert projection.ready
    assert projection.status == "READY"


def test_stale_writer_lease_holds_the_whole_section():
    previous = [{"source_identity": "a", "disposition": "INCLUDE"}]
    current = [{"source_identity": "a", "disposition": "INCLUDE"}]
    si_report = source_identity_guard(previous, current, expected_count=1)
    records = [{"source_identity": "a", "disposition": "INCLUDE", "pixel_reviewed": True}]
    stale_writer_gate = _clean_writer_gate(heartbeat_at=NOW - dt.timedelta(seconds=500))

    projection = build_control_truth(
        "12-45N-76W",
        source_identity=si_report,
        writer_gate=stale_writer_gate,
        source_records=records,
        gate_report=_clean_gate_report(),
        clean_cycle_streak=5,
    )

    assert not projection.ready
    assert projection.status == "HOLD"
    assert not projection.writer_gate.passed


def test_source_identity_shrinkage_holds_the_section():
    previous = [
        {"source_identity": "a", "disposition": "INCLUDE"},
        {"source_identity": "b", "disposition": "INCLUDE"},
    ]
    current = [{"source_identity": "a", "disposition": "INCLUDE"}]
    si_report = source_identity_guard(previous, current, expected_count=2)
    records = [{"source_identity": "a", "disposition": "INCLUDE", "pixel_reviewed": True}]

    projection = build_control_truth(
        "12-45N-76W",
        source_identity=si_report,
        writer_gate=_clean_writer_gate(),
        source_records=records,
        gate_report=_clean_gate_report(),
        clean_cycle_streak=5,
    )

    assert not projection.ready
    assert "b" in projection.source_identity.missing_identities


def test_ocr_only_coverage_holds_the_section():
    previous = [{"source_identity": "a", "disposition": "INCLUDE"}]
    current = [{"source_identity": "a", "disposition": "INCLUDE"}]
    si_report = source_identity_guard(previous, current, expected_count=1)
    records = [
        {"source_identity": "a", "disposition": "INCLUDE", "ocr_reviewed": True, "pixel_reviewed": False}
    ]

    projection = build_control_truth(
        "12-45N-76W",
        source_identity=si_report,
        writer_gate=_clean_writer_gate(),
        source_records=records,
        gate_report=_clean_gate_report(),
        clean_cycle_streak=5,
    )

    assert not projection.ready
    assert projection.coverage.ocr_only_hold == 1


def test_insufficient_clean_cycles_holds_the_section():
    previous = [{"source_identity": "a", "disposition": "INCLUDE"}]
    current = [{"source_identity": "a", "disposition": "INCLUDE"}]
    si_report = source_identity_guard(previous, current, expected_count=1)
    records = [{"source_identity": "a", "disposition": "INCLUDE", "pixel_reviewed": True}]

    projection = build_control_truth(
        "12-45N-76W",
        source_identity=si_report,
        writer_gate=_clean_writer_gate(),
        source_records=records,
        gate_report=_clean_gate_report(),
        clean_cycle_streak=2,
        required_clean_cycles=5,
    )

    assert not projection.ready
    assert not projection.integrity.passed


def test_byte_change_resets_readiness_via_failing_gate_report():
    previous = [{"source_identity": "a", "disposition": "INCLUDE"}]
    current = [{"source_identity": "a", "disposition": "INCLUDE"}]
    si_report = source_identity_guard(previous, current, expected_count=1)
    records = [{"source_identity": "a", "disposition": "INCLUDE", "pixel_reviewed": True}]
    changed_bytes_gate = _clean_gate_report(failures=["CRC:a.xlsx"])

    projection = build_control_truth(
        "12-45N-76W",
        source_identity=si_report,
        writer_gate=_clean_writer_gate(),
        source_records=records,
        gate_report=changed_bytes_gate,
        clean_cycle_streak=5,
    )

    assert not projection.ready
    assert not projection.integrity.passed


def test_public_dict_never_leaks_source_identities_or_filenames():
    previous = [
        {"source_identity": "SYNTH-1001.pdf", "disposition": "INCLUDE"},
        {"source_identity": "SYNTH-1002.pdf", "disposition": "INCLUDE"},
    ]
    current = [{"source_identity": "SYNTH-1001.pdf", "disposition": "INCLUDE"}]
    si_report = source_identity_guard(previous, current, expected_count=2)
    records = [
        {"source_identity": "SYNTH-1001.pdf", "disposition": "INCLUDE", "pixel_reviewed": True}
    ]

    projection = build_control_truth(
        "14-45N-76W",
        source_identity=si_report,
        writer_gate=_clean_writer_gate(),
        source_records=records,
        gate_report=_clean_gate_report(),
        clean_cycle_streak=5,
    )

    public = projection.public_dict()
    dumped = repr(public)
    assert "SYNTH-1001" not in dumped
    assert "SYNTH-1002" not in dumped
    assert public["status"] == "HOLD"

    # The internal projection is allowed to carry identities -- it is for
    # local/CLI/test use only and must never be returned from a public API.
    assert "SYNTH-1002.pdf" in projection.internal_dict()["source_identity"]["missing_identities"]
