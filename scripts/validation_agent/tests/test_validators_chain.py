"""Chain validator: escalates missing vesting, never auto-repairs gaps."""

from __future__ import annotations

from core.enums import FailureCategory, GateStatus
from tests._ctx import make_context
from validators.val_chain import ChainContinuityGate


def test_valid_chain_passes(settings, valid_workbook):
    ctx = make_context(valid_workbook, settings)
    results = ChainContinuityGate().validate(ctx)
    assert any(r.status == GateStatus.PASS for r in results)


def test_missing_vesting_escalates(settings, missing_vesting_workbook):
    ctx = make_context(missing_vesting_workbook, settings)
    results = ChainContinuityGate().validate(ctx)
    escalations = [r for r in results if r.status == GateStatus.ESCALATE]
    assert escalations
    assert any(
        r.failure_category == FailureCategory.TITLE_CHAIN_GAP for r in escalations
    )
    # chain gaps are never marked repairable
    assert all(r.repairable is False for r in escalations)
