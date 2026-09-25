"""Regression tests for writer-gate exclusivity."""

from __future__ import annotations

import datetime as dt

import pytest

from horizon.writer_gate import WriterGateDenied, WriterGateState, authorize_mutation

NOW = dt.datetime(2026, 9, 25, 12, 0, 0, tzinfo=dt.timezone.utc)


def _state(**overrides):
    base = dict(
        writer_seat="P12",
        writer_instance="claude-session-1",
        exact_preimage_sha256="a" * 64,
        observed_preimage_sha256="a" * 64,
        exact_target_id="drive-id-1",
        observed_target_id="drive-id-1",
        lease_holder="claude-session-1",
        lease_expires_at=NOW + dt.timedelta(minutes=5),
        heartbeat_at=NOW - dt.timedelta(seconds=10),
        collision_count=0,
        now=NOW,
    )
    base.update(overrides)
    return WriterGateState(**base)


def test_clean_state_passes_and_authorizes():
    state = _state()
    assert state.passed
    assert authorize_mutation(state) is state


def test_stale_writer_lease_cannot_mutate():
    state = _state(heartbeat_at=NOW - dt.timedelta(seconds=500))
    assert not state.passed
    assert "HEARTBEAT_STALE_OR_ABSENT" in state.reasons_denied()
    with pytest.raises(WriterGateDenied) as excinfo:
        authorize_mutation(state)
    assert "HEARTBEAT_STALE_OR_ABSENT" in excinfo.value.reasons


def test_expired_lease_cannot_mutate():
    state = _state(lease_expires_at=NOW - dt.timedelta(seconds=1))
    assert not state.passed
    assert "LEASE_EXPIRED_OR_ABSENT" in state.reasons_denied()
    with pytest.raises(WriterGateDenied):
        authorize_mutation(state)


def test_second_claimant_cannot_mutate():
    state = _state(lease_holder="codex-session-9")
    assert not state.passed
    assert "LEASE_NOT_HELD_BY_INSTANCE" in state.reasons_denied()


def test_changed_preimage_denies_mutation():
    state = _state(observed_preimage_sha256="b" * 64)
    assert not state.passed
    assert "PREIMAGE_CHANGED_OR_UNKNOWN" in state.reasons_denied()


def test_target_mismatch_denies_mutation():
    state = _state(observed_target_id="drive-id-DIFFERENT")
    assert not state.passed
    assert "TARGET_MISMATCH_OR_UNKNOWN" in state.reasons_denied()


def test_collision_denies_mutation():
    state = _state(collision_count=1)
    assert not state.passed
    assert "COLLISION_DETECTED" in state.reasons_denied()


def test_unknown_preimage_or_target_never_passes():
    state = _state(exact_preimage_sha256="", observed_preimage_sha256="")
    assert not state.passed
    state2 = _state(exact_target_id="", observed_target_id="")
    assert not state2.passed


def test_no_heartbeat_at_all_is_denied_not_assumed_fresh():
    state = _state(heartbeat_at=None)
    assert not state.passed
    assert "HEARTBEAT_STALE_OR_ABSENT" in state.reasons_denied()


def test_naive_datetimes_are_treated_as_utc_not_a_crash():
    state = _state(
        now=dt.datetime(2026, 9, 25, 12, 0, 0),
        lease_expires_at=dt.datetime(2026, 9, 25, 12, 5, 0),
        heartbeat_at=dt.datetime(2026, 9, 25, 11, 59, 50),
    )
    assert state.passed
