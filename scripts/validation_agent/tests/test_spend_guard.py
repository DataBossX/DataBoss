"""Spend guard: blocks any call that would push cumulative spend over $100,
enforces per-doc limits, and records blocked attempts (never hidden)."""

from decimal import Decimal

import pytest

from db.db_client import DatabaseManager
from sources.spend_guard import SpendGuard, SpendCapExceeded


@pytest.fixture()
def db(tmp_path):
    d = DatabaseManager(tmp_path / "audit.db")
    yield d
    d.close()


def test_single_call_over_cap_blocked(db):
    g = SpendGuard(db=db, run_id="r1", cap_usd="100.00")
    d = g.authorize("150.00", "big doc", examiner_approved=True)
    assert d.approved is False
    assert g.cumulative == Decimal("0.00")


def test_cumulative_cannot_exceed_100(db):
    g = SpendGuard(db=db, run_id="r1", cap_usd="100.00")
    # 99 approved, then a 2.00 call must be blocked.
    d1 = g.authorize("99.00", "doc a", examiner_approved=True)
    assert d1.approved
    d2 = g.authorize("2.00", "doc b", examiner_approved=True)
    assert d2.approved is False
    assert g.cumulative == Decimal("99.00")
    assert g.remaining() == Decimal("1.00")


def test_exactly_at_cap_allowed(db):
    g = SpendGuard(db=db, run_id="r1", cap_usd="100.00")
    d = g.authorize("100.00", "doc", examiner_approved=True)
    assert d.approved
    assert g.cumulative == Decimal("100.00")
    # One more cent is blocked.
    assert g.authorize("0.01", "doc2", examiner_approved=True).approved is False


def test_no_approval_blocks_paid_call(db):
    g = SpendGuard(db=db, run_id="r1", cap_usd="100.00", auto_approve=False)
    d = g.authorize("1.00", "doc")  # not examiner-approved, auto off
    assert d.approved is False


def test_auto_approve_respects_per_doc_limit(db):
    g = SpendGuard(db=db, run_id="r1", cap_usd="100.00",
                   per_doc_limit="5.00", auto_approve=True)
    assert g.authorize("4.00", "small").approved is True
    assert g.authorize("6.00", "big").approved is False


def test_blocked_attempts_are_recorded(db):
    g = SpendGuard(db=db, run_id="r1", cap_usd="100.00")
    g.authorize("500.00", "blocked doc", examiner_approved=True)
    rows = db.query("SELECT * FROM spend_ledger WHERE run_id='r1'")
    assert len(rows) == 1
    assert rows[0]["approved"] == 0


def test_cap_cannot_be_raised_above_absolute(db):
    g = SpendGuard(db=db, run_id="r1", cap_usd="1000.00")
    assert g.cap == Decimal("100.00")


def test_cumulative_seeded_from_ledger(db):
    g1 = SpendGuard(db=db, run_id="r1", cap_usd="100.00")
    g1.authorize("50.00", "doc", examiner_approved=True)
    # A new guard for the same run sees prior spend.
    g2 = SpendGuard(db=db, run_id="r1", cap_usd="100.00")
    assert g2.cumulative == Decimal("50.00")
    assert g2.authorize("60.00", "doc2", examiner_approved=True).approved is False
