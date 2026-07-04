"""Interest validator: catches over-conveyance with exact Fraction math."""

from __future__ import annotations

from fractions import Fraction

from core.enums import GateStatus
from tests._ctx import make_context
from validators.util import parse_fraction
from validators.val_interest import InterestConservationGate


def test_valid_interest_conserved(settings, valid_workbook):
    ctx = make_context(valid_workbook, settings)
    results = InterestConservationGate().validate(ctx)
    assert any(r.status == GateStatus.PASS for r in results)
    assert not any(r.status == GateStatus.ESCALATE for r in results)


def test_overconveyance_escalates(settings, overconveyance_workbook):
    ctx = make_context(overconveyance_workbook, settings)
    results = InterestConservationGate().validate(ctx)
    escalations = [r for r in results if r.status == GateStatus.ESCALATE]
    assert escalations
    assert any("over-conveyance" in (r.reason or "").lower() for r in escalations)


def test_fraction_parsing_no_float_false_positive():
    # 1/3 has no exact float representation; Fraction keeps it exact.
    third = parse_fraction("1/3")
    assert third == Fraction(1, 3)
    assert third + third + third == Fraction(1)
    assert parse_fraction("50%") == Fraction(1, 2)
    assert parse_fraction("0.25") == Fraction(1, 4)


def test_thirds_conservation_is_exact():
    # grantor 1 - conveyed 2/3 - retained 1/3 == 0 exactly (no float drift)
    grantor = parse_fraction("1")
    conveyed = parse_fraction("2/3")
    retained = parse_fraction("1/3")
    assert grantor - conveyed - retained == 0
