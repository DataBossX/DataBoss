"""Spend guard: never exceeds $100 cumulative; blocks and logs over-cap calls."""
from decimal import Decimal

import pytest

from sources.spend_guard import SpendGuard, SpendCapExceeded


def _guard(db, tmp_agent, cap="100.00"):
    from config.settings import load_settings
    s = load_settings({"DATABOSSX_API_CAP_USD": cap})
    s.agent_root = tmp_agent.agent_root
    return SpendGuard(db, s, run_id="r-spend")


def test_within_cap_allows_and_accumulates(db, tmp_agent):
    g = _guard(db, tmp_agent)
    g.record_charge("40.00", "doc1")
    assert g.cumulative() == Decimal("40.00")
    g.record_charge("55.00", "doc2")
    assert g.cumulative() == Decimal("95.00")
    assert g.remaining() == Decimal("5.00")


def test_blocks_over_cap(db, tmp_agent):
    g = _guard(db, tmp_agent)
    g.record_charge("95.00", "doc1")
    assert g.can_spend("6.00") is False
    with pytest.raises(SpendCapExceeded):
        g.record_charge("6.00", "doc-over")
    # cumulative never exceeded 100
    assert g.cumulative() <= Decimal("100.00")
    assert g.cumulative() == Decimal("95.00")
    # a blocked ledger row was written
    blocked = db.query("SELECT * FROM spend_ledger WHERE kind='blocked'")
    assert len(blocked) == 1


def test_exact_100_is_allowed_but_101_is_not(db, tmp_agent):
    g = _guard(db, tmp_agent)
    g.record_charge("100.00", "exact")
    assert g.cumulative() == Decimal("100.00")
    with pytest.raises(SpendCapExceeded):
        g.record_charge("0.01", "penny-over")


def test_configured_cap_never_exceeds_absolute(db, tmp_agent):
    g = _guard(db, tmp_agent, cap="500.00")  # requested 500 -> clamped to 100
    assert g.cap == Decimal("100.00")


# ---- OKCounty client: no silent paid calls; dry-run + auth + cap gating ----
from config.settings import load_settings
from sources.okcounty_client import OKCountyClient


def _client(db, tmp_agent, env):
    s = load_settings(env)
    s.agent_root = tmp_agent.agent_root
    g = SpendGuard(db, s, run_id="r-ok")
    return OKCountyClient(db, s, g, run_id="r-ok"), g


def test_okcounty_dry_run_makes_no_paid_call(db, tmp_agent):
    c, _ = _client(db, tmp_agent, {"DATABOSSX_DRY_RUN": "true"})
    r = c.retrieve_document("2019-001855")
    assert r.ok is False and r.status == "dry-run"
    # nothing charged
    assert db.count("spend_ledger", "kind='charge'") == 0


def test_okcounty_live_without_credentials_is_auth_failure(db, tmp_agent):
    c, _ = _client(db, tmp_agent, {"DATABOSSX_DRY_RUN": "false", "DATABOSSX_LIVE_SOURCE": "true"})
    r = c.retrieve_document("2019-001855")
    assert r.ok is False and r.status == "auth_failure"
    assert db.count("spend_ledger", "kind='charge'") == 0


def test_okcounty_paid_retrieval_requires_approval(db, tmp_agent):
    c, _ = _client(db, tmp_agent, {
        "DATABOSSX_DRY_RUN": "false", "DATABOSSX_LIVE_SOURCE": "true",
        "OKCOUNTY_USERNAME": "u", "OKCOUNTY_PASSWORD": "p",
        "OKCOUNTY_API_BASE_URL": "https://example.invalid",
        "DATABOSSX_AUTO_APPROVE_PAID": "false"})
    r = c.retrieve_document("2019-001855", approved=False)
    assert r.status == "needs_approval"
    assert db.count("spend_ledger", "kind='charge'") == 0


def test_okcounty_retrieval_blocked_when_over_cap(db, tmp_agent):
    c, g = _client(db, tmp_agent, {
        "DATABOSSX_DRY_RUN": "false", "DATABOSSX_LIVE_SOURCE": "true",
        "OKCOUNTY_USERNAME": "u", "OKCOUNTY_PASSWORD": "p",
        "OKCOUNTY_API_BASE_URL": "https://example.invalid",
        "DATABOSSX_AUTO_APPROVE_PAID": "true", "OKCOUNTY_COST_PER_IMAGE": "0.50"})
    g.record_charge("100.00", "prefill to cap")
    r = c.retrieve_document("2019-001855", approved=True)
    assert r.status == "blocked"
    assert g.cumulative() == Decimal("100.00")  # never exceeded
