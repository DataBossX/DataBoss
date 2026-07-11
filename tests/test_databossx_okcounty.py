"""Tests for the OKCountyRecords client and evidence pull queue."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from databossx.okcounty import (ChargeNotApprovedError, OKCountyClient,
                                SpendGuard, SpendLimitError, load_queue,
                                run_queue)

REPO_ROOT = Path(__file__).resolve().parent.parent
QUEUE_FILE = REPO_ROOT / "databossx" / "data" / "evidence_pull_queue.json"


def fake_transport(payload: bytes = b"%PDF-1.4 fake"):
    calls = []

    def transport(url, headers):
        calls.append({"url": url, "headers": headers})
        return payload

    transport.calls = calls
    return transport


def make_client(transport=None):
    return OKCountyClient(api_key="test-key-not-real", transport=transport)


def test_api_key_required(monkeypatch):
    monkeypatch.delenv("OKCOUNTY_API_KEY", raising=False)
    with pytest.raises(ValueError):
        OKCountyClient()


def test_api_key_from_env(monkeypatch):
    monkeypatch.setenv("OKCOUNTY_API_KEY", "env-key")
    monkeypatch.setenv("OKCOUNTY_BASE_URL", "https://example.test/api")
    c = OKCountyClient()
    assert c.api_key == "env-key"
    assert c.base_url == "https://example.test/api"


def test_bearer_header_sent():
    t = fake_transport(json.dumps({"ok": True}).encode())
    c = make_client(t)
    c.search("beckham", q="section 32")
    assert t.calls[0]["headers"]["Authorization"] == "Bearer test-key-not-real"
    assert "beckham" in t.calls[0]["url"]


def test_download_requires_charge_approval(tmp_path):
    c = make_client(fake_transport())
    guard = SpendGuard(max_spend_usd=10)
    with pytest.raises(ChargeNotApprovedError):
        c.download_document("beckham", "2022-000156", tmp_path, guard)


def test_spend_guard_blocks_over_budget(tmp_path):
    c = make_client(fake_transport())
    guard = SpendGuard(max_spend_usd=0.80, est_cost_per_doc_usd=0.40)
    for inst in ("2022-000156", "2022-000157"):
        c.download_document("beckham", inst, tmp_path, guard, approve_charges=True)
    with pytest.raises(SpendLimitError):
        c.download_document("beckham", "2022-003489", tmp_path, guard,
                            approve_charges=True)
    assert guard.spent_usd == pytest.approx(0.80)


def test_download_writes_file_and_manifest_row(tmp_path):
    payload = b"%PDF-1.4 evidence bytes"
    c = make_client(fake_transport(payload))
    guard = SpendGuard(max_spend_usd=1.0)
    row = c.download_document("beckham", "2022-000156", tmp_path, guard,
                              approve_charges=True,
                              timestamp="2026-07-11T00:00:00+00:00")
    assert row["status"] == "ok"
    assert Path(row["path"]).read_bytes() == payload
    import hashlib
    assert row["sha256"] == hashlib.sha256(payload).hexdigest()


def test_failed_download_recorded_not_raised(tmp_path):
    def broken(url, headers):
        raise OSError("network blocked")

    c = make_client(broken)
    guard = SpendGuard(max_spend_usd=1.0)
    row = c.download_document("beckham", "2022-000156", tmp_path, guard,
                              approve_charges=True)
    assert row["status"] == "failed"
    assert "network blocked" in row["error"]
    assert guard.spent_usd == 0  # failed pulls are not charged against budget


def test_queue_tier1_is_the_22_absent_instruments():
    tier1 = load_queue(QUEUE_FILE, tier=1)
    assert len(tier1) == 22
    ids = [q["instrument_id"] for q in tier1]
    assert len(set(ids)) == 22
    for q in tier1:
        assert q["county"] == "beckham"
        assert q["book_page"] and q["reason"] and q["type"]


def test_queue_run_appends_manifest(tmp_path):
    c = make_client(fake_transport())
    guard = SpendGuard(max_spend_usd=100)
    queue = load_queue(QUEUE_FILE, tier=2)  # 4 countywide screens
    rows = run_queue(c, queue, tmp_path, guard, approve_charges=True,
                     timestamp="2026-07-11T00:00:00+00:00")
    assert len(rows) == 4 and all(r["status"] == "ok" for r in rows)
    manifest = (tmp_path / "PULL_MANIFEST.jsonl").read_text().splitlines()
    assert len(manifest) == 4
    assert json.loads(manifest[0])["book_page"] == "2434/751-760"


def test_queue_run_stops_at_budget(tmp_path):
    c = make_client(fake_transport())
    guard = SpendGuard(max_spend_usd=0.40)
    queue = load_queue(QUEUE_FILE, tier=2)
    rows = run_queue(c, queue, tmp_path, guard, approve_charges=True)
    assert rows[0]["status"] == "ok"
    assert rows[1]["status"] == "skipped_budget"
    assert len(rows) == 2  # run halts once the budget is exhausted


def test_no_secrets_in_repo_files():
    """No API key material may ever be committed."""
    import subprocess
    needle = "b62e" + "fd1d"  # split so this test file never matches itself
    out = subprocess.run(
        ["git", "grep", "-l", needle], cwd=REPO_ROOT,
        capture_output=True, text=True)
    assert out.stdout.strip() == "", f"secret found in: {out.stdout}"
