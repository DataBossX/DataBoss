"""Spend guard blocks over $100 and logs every decision."""

from __future__ import annotations

from decimal import Decimal

import pytest

from sources.spend_guard import SpendCapExceeded, SpendGuard


def test_allows_under_cap(settings, audit):
    guard = SpendGuard(settings, audit, run_id="r1")
    # allow a $0 (read-only / dry-run priced) check
    decision = guard.check(Decimal("0.00"), "free lookup")
    assert decision.allowed is True


def test_blocks_over_cap(settings, audit):
    guard = SpendGuard(settings, audit, run_id="r1")
    decision = guard.check(Decimal("150.00"), "expensive doc")
    assert decision.blocked is True
    assert decision.reason == "SPEND_CAP_REACHED"
    # blocked decision was logged
    rows = audit.db.query("SELECT * FROM spend_ledger WHERE decision='BLOCKED'")
    assert rows


def test_cumulative_plus_proposed_over_cap_blocks(settings, audit):
    guard = SpendGuard(settings, audit, run_id="r1")
    # commit 99 first (requires live+auto-approve; simulate by direct ledger entry)
    audit.log_spend("ALLOWED", Decimal("99.00"), Decimal("99.00"),
                    "COMMITTED", "prior", run_id="r1")
    decision = guard.check(Decimal("2.00"), "would exceed")
    assert decision.blocked is True
    assert decision.reason == "SPEND_CAP_REACHED"


def test_dry_run_blocks_paid_call(settings, audit):
    guard = SpendGuard(settings, audit, run_id="r1")
    decision = guard.check(Decimal("2.50"), "paid doc")
    assert decision.blocked is True
    assert decision.reason in ("POLICY_DRY_RUN", "SPEND_CAP_REACHED")


def test_commit_refuses_overspend(settings, audit):
    guard = SpendGuard(settings, audit, run_id="r1")
    audit.log_spend("ALLOWED", Decimal("99.50"), Decimal("99.50"),
                    "COMMITTED", "prior", run_id="r1")
    with pytest.raises(SpendCapExceeded):
        guard.commit(Decimal("5.00"), "over cap commit")
