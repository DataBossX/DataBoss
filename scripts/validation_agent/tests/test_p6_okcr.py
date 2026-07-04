"""P6 exit tests: OKCR client honors free_to_view, spend cap, graceful degrade."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from validation_agent.memory import db
from validation_agent.memory.spend_ledger import SpendLedger
from validation_agent.source_verification.okcr_client import (
    InstrumentMeta,
    OKCRClient,
    SourceUnavailable,
)


@pytest.fixture()
def ledger(tmp_path: Path):
    conn = db.get_connection(tmp_path / "r.db")
    db.init_schema(conn)
    conn.execute("INSERT INTO runs(run_id, source_path, created_ts, state) "
                 "VALUES('r','x','t','INGESTED')")
    conn.commit()
    return SpendLedger(conn, "r", cap=Decimal("100.00"))


def test_unreachable_host_degrades_gracefully(ledger) -> None:
    # Real network is blocked in CI/cloud; the client must return SourceUnavailable,
    # never raise, so the loop can escalate instead of crashing.
    client = OKCRClient("dummy-key", ledger, timeout=5)
    result = client.counties()
    assert isinstance(result, (list, SourceUnavailable))


def test_paid_fetch_blocked_when_over_cap(ledger, tmp_path, monkeypatch) -> None:
    client = OKCRClient("k", ledger)
    # Force lookup to return a costly, non-free instrument.
    monkeypatch.setattr(
        client, "lookup",
        lambda number, county="Roger Mills": InstrumentMeta(
            county, number, free_to_view=False, cost_usd=Decimal("150.00")),
    )
    out = client.fetch_image("2018-000119", tmp_path / "img.pdf")
    assert isinstance(out, SourceUnavailable)
    assert ledger.spent() == Decimal("0.00")  # nothing charged


def test_free_to_view_never_charges(ledger, tmp_path, monkeypatch) -> None:
    client = OKCRClient("k", ledger)
    monkeypatch.setattr(
        client, "lookup",
        lambda number, county="Roger Mills": InstrumentMeta(
            county, number, free_to_view=True, cost_usd=Decimal("0.00")),
    )
    # Simulate a successful curl by writing the target file.
    def fake_run(cmd, capture_output, text, timeout):
        out_idx = cmd.index("-o") + 1
        Path(cmd[out_idx]).write_bytes(b"%PDF-1.4 fake")
        class R: returncode = 0; stdout = ""; stderr = ""
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    out = client.fetch_image("2018-000119", tmp_path / "img.pdf")
    assert isinstance(out, Path) and out.exists()
    assert ledger.spent() == Decimal("0.00")
