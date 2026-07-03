"""Config safety: spend cap and iteration cap can never exceed hard ceilings,
dry-run forces live-source off, and secrets are redacted in dumps."""

from decimal import Decimal

import pytest

from config.settings import Settings, ABSOLUTE_API_CAP_USD, ABSOLUTE_MAX_ITERATIONS


def _fresh_settings(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return Settings()


def test_cap_clamped_to_100(monkeypatch):
    s = _fresh_settings(monkeypatch, DATABOSSX_API_CAP_USD="500.00")
    assert s.api_cap_usd == Decimal("100.00")
    assert s.api_cap_usd <= ABSOLUTE_API_CAP_USD


def test_cap_below_100_preserved(monkeypatch):
    s = _fresh_settings(monkeypatch, DATABOSSX_API_CAP_USD="25.00")
    assert s.api_cap_usd == Decimal("25.00")


def test_iterations_clamped(monkeypatch):
    s = _fresh_settings(monkeypatch, DATABOSSX_MAX_ITERATIONS="99")
    assert s.max_iterations == ABSOLUTE_MAX_ITERATIONS == 5


def test_dry_run_forces_live_off(monkeypatch):
    s = _fresh_settings(monkeypatch, DATABOSSX_DRY_RUN="true",
                        DATABOSSX_LIVE_SOURCE="true")
    assert s.dry_run is True
    assert s.live_source is False
    s.validate()  # must not raise


def test_live_mode_when_not_dry(monkeypatch):
    s = _fresh_settings(monkeypatch, DATABOSSX_DRY_RUN="false",
                        DATABOSSX_LIVE_SOURCE="true")
    assert s.live_source is True


def test_secret_redaction(monkeypatch):
    s = _fresh_settings(monkeypatch, OKCOUNTY_USERNAME="alice",
                        OKCOUNTY_PASSWORD="hunter2")
    dump = s.safe_dump()
    assert dump["okcounty_password"] == "***REDACTED***"
    assert "hunter2" not in str(dump)


def test_zero_cap_rejected(monkeypatch):
    with pytest.raises(ValueError):
        _fresh_settings(monkeypatch, DATABOSSX_API_CAP_USD="0")
