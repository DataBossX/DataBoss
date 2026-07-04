import os
from decimal import Decimal
from config.settings import Settings

def test_api_cap_clamped_to_100(monkeypatch):
    monkeypatch.setenv("DATABOSSX_API_CAP_USD", "500.00")
    s = Settings()
    assert s.api_cap_usd == Decimal("100.00")

def test_api_cap_can_be_stricter(monkeypatch):
    monkeypatch.setenv("DATABOSSX_API_CAP_USD", "25.00")
    assert Settings().api_cap_usd == Decimal("25.00")

def test_max_iterations_clamped(monkeypatch):
    monkeypatch.setenv("DATABOSSX_MAX_ITERATIONS", "999")
    assert Settings().max_iterations == 5

def test_dry_run_default(monkeypatch):
    monkeypatch.delenv("DATABOSSX_DRY_RUN", raising=False)
    assert Settings().dry_run is True

def test_safe_dump_redacts_secrets(monkeypatch):
    monkeypatch.setenv("OKCOUNTY_PASSWORD", "supersecret")
    d = Settings().safe_dump()
    assert d["okcounty_password"] == "***REDACTED***"
    assert "supersecret" not in str(d)

def test_live_retrieval_requires_all(monkeypatch):
    for k in ("OKCOUNTY_USERNAME","OKCOUNTY_PASSWORD","OKCOUNTY_API_BASE_URL"):
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("DATABOSSX_DRY_RUN", "false")
    monkeypatch.setenv("DATABOSSX_LIVE_SOURCE_MODE", "true")
    assert Settings().live_retrieval_allowed() is True
    monkeypatch.setenv("DATABOSSX_DRY_RUN", "true")
    assert Settings().live_retrieval_allowed() is False
