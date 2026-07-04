"""P0 exit tests: append-only guarantees, audit idempotency, spend cap."""
from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from validation_agent.memory import db
from validation_agent.memory.audit_log import AuditLog
from validation_agent.memory.spend_ledger import SpendCapExceeded, SpendLedger
from validation_agent.models import AuditEntry, GateId


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.get_connection(tmp_path / "run.db")
    db.init_schema(c)
    c.execute(
        "INSERT INTO runs(run_id, source_path, created_ts, state) VALUES(?,?,?,?)",
        ("r1", "x.xlsx", "now", "INGESTED"),
    )
    c.commit()
    return c


def test_append_only_rejects_update(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO spend_ledger(ts, run_id, cost_usd) VALUES('t','r1','1.00')"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE spend_ledger SET cost_usd='9' WHERE run_id='r1'")
        conn.commit()


def test_append_only_rejects_delete(conn: sqlite3.Connection) -> None:
    log = AuditLog(conn, "r1")
    log.record(AuditEntry(run_id="r1", actor="t", action="a", result="ok"))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM audit_log WHERE run_id='r1'")
        conn.commit()


def test_audit_is_idempotent_on_identical_action(conn: sqlite3.Connection) -> None:
    log = AuditLog(conn, "r1")
    e = AuditEntry(run_id="r1", actor="v", action="check", result="pass",
                   gate=GateId.G1_CONSERVATION)
    log.record(e)
    log.record(e)  # identical -> ignored
    assert log.count() == 1


def test_audit_distinct_actions_both_recorded(conn: sqlite3.Connection) -> None:
    log = AuditLog(conn, "r1")
    log.record(AuditEntry(run_id="r1", actor="v", action="a1", result="pass"))
    log.record(AuditEntry(run_id="r1", actor="v", action="a2", result="pass"))
    assert log.count() == 2


def test_spend_cap_enforced(conn: sqlite3.Connection) -> None:
    ledger = SpendLedger(conn, "r1", cap=Decimal("100.00"))
    ledger.charge(Decimal("60.00"))
    assert ledger.remaining() == Decimal("40.00")
    with pytest.raises(SpendCapExceeded):
        ledger.charge(Decimal("50.00"))
    # partial charge that fits still works
    ledger.charge(Decimal("40.00"))
    assert ledger.remaining() == Decimal("0.00")
