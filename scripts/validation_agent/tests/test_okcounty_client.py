"""OKCounty client safety: no paid call in dry-run, spend-gated retrieval,
over-cap blocked, and network failures never fabricate document content.

A fake HTTP session is injected so no real network call is ever made."""

import pytest

from config.settings import Settings
from db.db_client import DatabaseManager
from sources.spend_guard import SpendGuard
from sources.source_cache import SourceCache
from sources.okcounty_client import OKCountyClient
from core.run_manager import RunManager


class _FakeResp:
    def __init__(self, json_data=None, content=b"", status=200):
        self._json = json_data or {}
        self.content = content
        self._status = status

    def raise_for_status(self):
        if self._status >= 400:
            raise RuntimeError(f"HTTP {self._status}")

    def json(self):
        return self._json


class _FakeSession:
    """Routes by URL substring; records calls; can be told to raise."""
    def __init__(self, search_json=None, doc_content=b"%PDF fake",
                 raise_on=None):
        self.search_json = search_json
        self.doc_content = doc_content
        self.raise_on = raise_on or set()
        self.calls = []
        self.headers = {}
        self.auth = None

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        if "search" in url:
            if "search" in self.raise_on:
                raise ConnectionError("boom")
            return _FakeResp(json_data=self.search_json)
        if "download" in self.raise_on:
            raise ConnectionError("boom")
        return _FakeResp(content=self.doc_content)


def _live_settings(monkeypatch):
    monkeypatch.setenv("DATABOSSX_DRY_RUN", "false")
    monkeypatch.setenv("DATABOSSX_LIVE_SOURCE", "true")
    monkeypatch.setenv("OKCOUNTY_USERNAME", "alice")
    monkeypatch.setenv("OKCOUNTY_PASSWORD", "secret")
    monkeypatch.setenv("OKCOUNTY_API_BASE_URL", "https://api.example.test/v1")
    return Settings()


@pytest.fixture()
def env(tmp_path):
    db = DatabaseManager(tmp_path / "audit.db")
    rm = RunManager(tmp_path / "outputs", timestamp="20260101_000000")
    cache = SourceCache(rm.run_dir / "sources")
    yield db, rm, cache
    db.close()


def _search_json():
    return {"results": [{"type": "deed", "county": "Roger Mills",
                         "download_url": "https://api.example.test/v1/download/1",
                         "cost": "1.00"}]}


def test_dry_run_makes_no_paid_call(env, monkeypatch):
    db, rm, cache = env
    # Default settings = dry-run; client must be inert.
    settings = Settings()
    guard = SpendGuard(db=db, run_id=rm.run_id, cap_usd="100.00")
    client = OKCountyClient(settings, db=db, run_id=rm.run_id, spend_guard=guard)
    client._session = _FakeSession(search_json=_search_json())
    assert client.is_available() is False
    assert client.search("bk 1/pg 1") is None
    assert client._session.calls == []          # no network call
    assert guard.cumulative == guard.cap * 0     # no spend
    # A blocked api_call was still recorded (never hidden).
    rows = db.query("SELECT * FROM api_calls WHERE outcome='blocked'")
    assert len(rows) >= 1


def test_live_search_and_retrieve_under_cap(env, monkeypatch):
    db, rm, cache = env
    settings = _live_settings(monkeypatch)
    guard = SpendGuard(db=db, run_id=rm.run_id, cap_usd="100.00",
                       auto_approve=True, per_doc_limit="5.00")
    client = OKCountyClient(settings, db=db, run_id=rm.run_id, spend_guard=guard)
    client._session = _FakeSession(search_json=_search_json())
    assert client.is_available() is True
    result = client.search("bk 1/pg 1", county="Roger Mills")
    assert result is not None
    retrieved = client.retrieve(result, cache)
    assert retrieved is not None
    path, digest, cost = retrieved
    assert path.exists() and digest and float(cost) == 1.00
    # Spend recorded and under cap.
    assert float(guard.cumulative) <= 100.0
    assert float(guard.cumulative) > 0.0


def test_over_cap_retrieval_blocked_no_file(env, monkeypatch):
    db, rm, cache = env
    settings = _live_settings(monkeypatch)
    guard = SpendGuard(db=db, run_id=rm.run_id, cap_usd="100.00",
                       auto_approve=True, per_doc_limit="1000.00")
    # Pre-spend to $99.50 so a $1.00 doc would exceed the cap.
    guard.authorize("99.50", "prior", examiner_approved=True)
    client = OKCountyClient(settings, db=db, run_id=rm.run_id, spend_guard=guard)
    client._session = _FakeSession(search_json=_search_json())
    result = client.search("bk 1/pg 1")
    retrieved = client.retrieve(result, cache)
    assert retrieved is None                     # blocked by cap
    assert float(guard.cumulative) <= 100.0
    # No document file was written.
    assert not any(p.name.startswith("doc_") for p in
                   (rm.run_dir / "sources").iterdir())


def test_network_error_never_fabricates(env, monkeypatch):
    db, rm, cache = env
    settings = _live_settings(monkeypatch)
    guard = SpendGuard(db=db, run_id=rm.run_id, cap_usd="100.00",
                       auto_approve=True, per_doc_limit="5.00")
    client = OKCountyClient(settings, db=db, run_id=rm.run_id, spend_guard=guard)
    client._session = _FakeSession(search_json=_search_json(),
                                   raise_on={"download"})
    result = client.search("bk 1/pg 1")
    retrieved = client.retrieve(result, cache)
    assert retrieved is None                     # error -> no fabricated content
    assert not any(p.name.startswith("doc_") for p in
                   (rm.run_dir / "sources").iterdir())
    # The error outcome is logged.
    rows = db.query("SELECT * FROM api_calls WHERE outcome='error'")
    assert len(rows) >= 1
