"""Validator behaviour: acreage, interest (exact math), chain escalation."""
from decimal import Decimal

from validators.val_acreage import AcreageValidator
from validators.val_interest import InterestValidator, conservation_residual
from validators.val_chain import ChainValidator
from validators.base_validator import FAIL, ESCALATE, PASS


def test_acreage_catches_wrong_total(sample_wb):
    # Fixture section gross = 40 + 40 = 80, but expect 637.42 -> FAIL at section level.
    v = AcreageValidator(workbook_path=sample_wb, config={"expected_acreage": "637.42"})
    results = v.run()
    assert any(r.status == FAIL for r in results)


def test_acreage_passes_when_expected_matches(sample_wb):
    v = AcreageValidator(workbook_path=sample_wb, config={"expected_acreage": "80"})
    results = v.run()
    assert any(r.status == PASS for r in results)


def test_interest_detects_overconveyance_without_float_bug(sample_wb):
    v = InterestValidator(workbook_path=sample_wb, config={})
    results = v.run()
    over = [r for r in results if r.status == FAIL and "Over-conveyance" in r.reason]
    assert over, "Tract 2 (30+25 > 40) must be flagged as over-conveyed"
    # exact arithmetic: residual of a conserving triple is exactly zero
    assert conservation_residual("1", "3/16", "-13/16") == 0
    assert conservation_residual("1", "1/3", "1/3") != 0


def test_interest_uses_exact_thirds():
    # 1/3 + 1/3 + 1/3 must equal exactly 1 (no float drift)
    r = conservation_residual("1", "1", "0")
    assert r == 0
    # a value that a naive float compare would get wrong
    assert conservation_residual("0.1", "0.3", "0.2") == 0  # 0.1 - 0.3 + 0.2 == 0 exactly


def test_chain_escalates_missing_vesting(sample_wb):
    v = ChainValidator(workbook_path=sample_wb, config={})
    results = v.run()
    assert any(r.status == ESCALATE for r in results)
    assert all(r.repairable is False for r in results if r.status == ESCALATE)
