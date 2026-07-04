"""Acreage validator: catches wrong totals, uses Decimal, detects overrides."""

from __future__ import annotations

from core.enums import FailureCategory, GateStatus
from tests._ctx import make_context
from tests.fixtures.make_workbook import build_valid_workbook
from validators.val_acreage import AcreageFootingGate


def test_valid_acreage_passes(settings, valid_workbook):
    ctx = make_context(valid_workbook, settings)
    results = AcreageFootingGate().validate(ctx)
    assert any(r.status == GateStatus.PASS for r in results)
    assert not any(
        r.failure_category == FailureCategory.COMPUTATIONAL_MISMATCH for r in results
    )


def test_wrong_total_detected(settings, tmp_path):
    wb = build_valid_workbook(tmp_path / "broken.xlsx", break_tract=999.99)
    ctx = make_context(wb, settings)
    results = AcreageFootingGate().validate(ctx)
    fails = [r for r in results if r.status == GateStatus.FAIL]
    assert fails
    assert any(
        r.failure_category == FailureCategory.COMPUTATIONAL_MISMATCH for r in fails
    )


def test_overridden_total_is_repairable_formula_defect(settings, tmp_path):
    # Declared total disagrees with the summed tracts -> repairable formula defect.
    wb = build_valid_workbook(tmp_path / "override.xlsx", total_override="1000.00")
    ctx = make_context(wb, settings)
    results = AcreageFootingGate().validate(ctx)
    override = [
        r for r in results
        if r.failure_category == FailureCategory.FORMULA_DEFECT and r.repairable
    ]
    assert override, "expected a repairable formula-defect for overridden total"


def test_uses_decimal_no_float_error(settings, valid_workbook):
    # 637.42 exact — a float sum of the tract values would risk 637.4199999.
    ctx = make_context(valid_workbook, settings)
    results = AcreageFootingGate().validate(ctx)
    passed = [r for r in results if r.status == GateStatus.PASS]
    assert passed
    assert "637.42" in (passed[0].reason or "")
