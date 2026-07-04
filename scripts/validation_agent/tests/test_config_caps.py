"""Config cap enforcement: API cap <= 100.00, iterations <= 5, secret redaction."""

from __future__ import annotations

import os
from decimal import Decimal

from config.settings import ABSOLUTE_API_CAP_USD, ABSOLUTE_MAX_ITERATIONS, load_settings


def test_api_cap_never_exceeds_100(monkeypatch):
    monkeypatch.setenv("DATABOSSX_API_CAP_USD", "500.00")
    s = load_settings()
    assert s.api_cap_usd <= ABSOLUTE_API_CAP_USD
    assert s.api_cap_usd == Decimal("100.00")


def test_api_cap_rejects_nonpositive(monkeypatch):
    monkeypatch.setenv("DATABOSSX_API_CAP_USD", "0")
    s = load_settings()
    assert s.api_cap_usd == ABSOLUTE_API_CAP_USD


def test_max_iterations_clamped(monkeypatch):
    monkeypatch.setenv("DATABOSSX_MAX_ITERATIONS", "99")
    s = load_settings()
    assert s.max_iterations <= ABSOLUTE_MAX_ITERATIONS
    assert s.max_iterations == 5


def test_lower_cap_is_respected(monkeypatch):
    monkeypatch.setenv("DATABOSSX_API_CAP_USD", "25.00")
    monkeypatch.setenv("DATABOSSX_MAX_ITERATIONS", "3")
    s = load_settings()
    assert s.api_cap_usd == Decimal("25.00")
    assert s.max_iterations == 3


def test_secrets_are_redacted(monkeypatch):
    monkeypatch.setenv("OKCOUNTY_USERNAME", "agent007")
    monkeypatch.setenv("OKCOUNTY_PASSWORD", "supersecret")
    s = load_settings()
    dump = s.as_safe_dict()
    assert dump["okcounty_password"] == "***REDACTED***"
    assert dump["okcounty_username"] == "***REDACTED***"
    assert "supersecret" not in str(dump)


def test_default_dry_run_and_no_paid_access(monkeypatch):
    for k in ("DATABOSSX_DRY_RUN", "DATABOSSX_LIVE_SOURCE_MODE"):
        monkeypatch.delenv(k, raising=False)
    s = load_settings()
    assert s.dry_run is True
    assert s.live_source_mode is False
    assert s.paid_source_access_allowed() is False
