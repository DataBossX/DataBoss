"""Phase 10 done-definition: the $100 cap blocks over-budget fetches."""

from __future__ import annotations

import pytest

from validation_agent.config.settings import config
from validation_agent.db.audit_logger import AuditLogger
from validation_agent.db.db_client import DatabaseManager
from validation_agent.sources.spend_guard import APISpendGuard


@pytest.fixture()
def guard(tmp_path):
    dbm = DatabaseManager(db_path=tmp_path / "spend.db",
                          schema_path=config.schema_path)
    dbm.init()
    return APISpendGuard(AuditLogger(dbm), cap=100.0)


def test_free_to_view_always_allowed(guard):
    d = guard.authorize(9999.0, free_to_view=True)
    assert d.allowed and d.estimated_cost == 0.0


def test_within_cap_allowed(guard):
    d = guard.authorize(10.0)
    assert d.allowed
    assert d.projected_total == 10.0


def test_block_when_exceeding_cap(guard):
    guard.commit_spend(96.0, "prior fetches")
    d = guard.authorize(5.0)
    assert not d.allowed
    assert "cap" in d.reason.lower()
    assert guard.remaining() == pytest.approx(4.0)


def test_commit_refuses_to_breach_cap(guard):
    guard.commit_spend(99.0, "almost there")
    with pytest.raises(RuntimeError):
        guard.commit_spend(5.0, "over the top")
