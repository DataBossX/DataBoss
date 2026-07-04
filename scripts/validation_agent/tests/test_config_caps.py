"""Configuration caps and safety defaults."""
from decimal import Decimal

from config.settings import load_settings, ABSOLUTE_SPEND_CAP_USD, ABSOLUTE_MAX_ITERATIONS


def test_spend_cap_cannot_exceed_100():
    s = load_settings({"DATABOSSX_API_CAP_USD": "99999.99"})
    assert s.api_cap_usd == Decimal("100.00")
    assert s.api_cap_usd <= ABSOLUTE_SPEND_CAP_USD


def test_spend_cap_can_be_lower():
    s = load_settings({"DATABOSSX_API_CAP_USD": "25.00"})
    assert s.api_cap_usd == Decimal("25.00")


def test_iterations_clamped():
    s = load_settings({"DATABOSSX_MAX_ITERATIONS": "999"})
    assert s.max_iterations == ABSOLUTE_MAX_ITERATIONS == 5
    s2 = load_settings({"DATABOSSX_MAX_ITERATIONS": "0"})
    assert s2.max_iterations >= 1


def test_dry_run_is_default():
    s = load_settings({})
    assert s.dry_run is True
    assert s.live_enabled() is False


def test_live_requires_both_flags():
    s = load_settings({"DATABOSSX_LIVE_SOURCE": "true", "DATABOSSX_DRY_RUN": "true"})
    # live_source on but still dry-run -> not enabled
    assert s.live_enabled() is False
    s2 = load_settings({"DATABOSSX_LIVE_SOURCE": "true", "DATABOSSX_DRY_RUN": "false"})
    assert s2.live_enabled() is True


def test_safe_dump_redacts_secrets():
    s = load_settings({"OKCOUNTY_USERNAME": "secretuser", "OKCOUNTY_PASSWORD": "secretpass"})
    dump = s.safe_dump()
    assert dump["okcounty_username"] == "***REDACTED***"
    assert dump["okcounty_password"] == "***REDACTED***"
    assert "secretuser" not in str(dump)
    assert "secretpass" not in str(dump)
