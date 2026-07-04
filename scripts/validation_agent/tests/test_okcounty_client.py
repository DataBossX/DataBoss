"""OKCounty client: dry-run default, spend/auth gating, and never fabricates."""

from __future__ import annotations

from decimal import Decimal

from sources.okcounty_client import OKCountyClient
from sources.spend_guard import SpendGuard


def _client(settings, audit):
    guard = SpendGuard(settings, audit, run_id="r1")
    return OKCountyClient(settings, audit, guard, run_id="r1")


def test_dry_run_does_not_retrieve_or_fabricate(settings, audit):
    # default settings are dry-run
    result = _client(settings, audit).fetch_document("book_101_page_201")
    assert result.outcome == "dry_run"
    assert result.file_path is None  # nothing fabricated
    calls = audit.db.query("SELECT * FROM api_calls WHERE outcome='blocked'")
    assert calls


def test_live_without_credentials_reports_auth_failure(settings, audit):
    object.__setattr__(settings, "dry_run", False)
    object.__setattr__(settings, "live_source_mode", True)
    # no credentials configured
    result = _client(settings, audit).fetch_document("book_101_page_201")
    assert result.outcome == "not_configured"
    assert result.file_path is None
    calls = audit.db.query("SELECT * FROM api_calls WHERE outcome='auth_failure'")
    assert calls


def test_live_with_credentials_blocks_on_manual_approval(settings, audit):
    object.__setattr__(settings, "dry_run", False)
    object.__setattr__(settings, "live_source_mode", True)
    object.__setattr__(settings, "_okcounty_username", "u")
    object.__setattr__(settings, "_okcounty_password", "p")
    object.__setattr__(settings, "_okcounty_api_base_url", "https://example.test")
    object.__setattr__(settings, "auto_approve_paid_docs", False)
    result = _client(settings, audit).fetch_document("book_101_page_201", Decimal("2.50"))
    assert result.outcome == "blocked"
    assert result.file_path is None


def test_live_auto_approved_still_never_fabricates(settings, audit):
    object.__setattr__(settings, "dry_run", False)
    object.__setattr__(settings, "live_source_mode", True)
    object.__setattr__(settings, "_okcounty_username", "u")
    object.__setattr__(settings, "_okcounty_password", "p")
    object.__setattr__(settings, "_okcounty_api_base_url", "https://example.test")
    object.__setattr__(settings, "auto_approve_paid_docs", True)
    object.__setattr__(settings, "per_document_auto_approval_limit_usd", Decimal("5.00"))
    result = _client(settings, audit).fetch_document("book_101_page_201", Decimal("2.50"))
    # integration not provisioned -> honest auth_failure, NOT a fake document
    assert result.outcome == "auth_failure"
    assert result.file_path is None
