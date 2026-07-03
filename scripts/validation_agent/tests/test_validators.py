"""Validator math: acreage footing, interest conservation (exact, no float
bugs), chain vesting escalation, and formula-defect repairability."""

from decimal import Decimal

from validators.val_acreage import check_acreage, AcreageFootingValidator
from validators.val_interest import check_conservation, InterestConservationValidator
from validators.val_chain import ChainContinuityValidator, analyze_chain
from validators.val_formula import detect_formula_defects


def test_acreage_reconciles_exactly():
    res = check_acreage(["63.742"] * 10, Decimal("637.42"))
    assert res["reconciles"]
    assert res["total"] == "637.420"


def test_acreage_catches_wrong_total():
    res = check_acreage(["60"] * 10, Decimal("637.42"))
    assert not res["reconciles"]
    assert res["difference"] == "-37.42"


def test_acreage_validator_fails_on_mismatch():
    v = AcreageFootingValidator()
    out = v.run({"tract_acreages": [60] * 10, "expected_acreage": "637.42"})
    assert out[0].status == "FAIL"
    assert out[0].repairable is False  # factual, never auto-repaired


def test_interest_conservation_balanced():
    # grantor had 1/2, conveyed 3/8, retained 1/8 -> 3/8 + 1/8 = 1/2. Balanced.
    res = check_conservation("1/2", "3/8", "1/8")
    assert res["balanced"]
    assert res["status"] == "balanced"


def test_interest_overconveyance_no_float_bug():
    # 0.1 + 0.2 style values that break float equality; must use exact math.
    # grantor 0.3, conveyed 0.1, retained 0.2 -> balanced exactly.
    res = check_conservation("0.3", "0.1", "0.2")
    assert res["balanced"], res
    # Overconveyance: grantor 0.3, conveyed 0.25, retained 0.1 -> 0.35 > 0.3.
    over = check_conservation("0.3", "0.25", "0.1")
    assert over["status"] == "overconveyance"
    assert not over["balanced"]


def test_interest_validator_flags_overconveyance():
    v = InterestConservationValidator()
    out = v.run({"interest_rows": [
        {"subject": "Tract 1", "grantor_interest": "0.3",
         "conveyed": "0.25", "retained": "0.1"}]})
    assert out[0].status == "FAIL"
    assert "overconveyance" in out[0].reason


def test_chain_escalates_missing_vesting():
    links = [
        {"grantor": "US", "grantee": "Alice", "vested_root": True},
        # Bob was never vested (never a grantee) -> gap.
        {"grantor": "Bob", "grantee": "Carol"},
    ]
    report = analyze_chain(links)
    assert not report["continuous"]
    v = ChainContinuityValidator()
    out = v.run({"chain_links": links})
    assert out[0].status == "ESCALATE"


def test_chain_continuous_passes():
    links = [
        {"grantor": "US", "grantee": "Alice", "vested_root": True},
        {"grantor": "Alice", "grantee": "Bob"},
    ]
    v = ChainContinuityValidator()
    out = v.run({"chain_links": links})
    assert out[0].status == "PASS"


def test_formula_defect_repairable_with_neighbor():
    # C13 should be a formula; neighbor C12 has the template formula.
    report = detect_formula_defects(
        expected_formula_cells=["C13"],
        formula_map={"C12": "=SUM(C2:C11)"},
        value_map={"C13": 600.0},
    )
    assert not report["clean"]
    d = report["defects"][0]
    assert d["repairable"] is True
    assert d["intended_formula"] == "=SUM(C2:C11)"


def test_formula_defect_not_repairable_without_evidence():
    report = detect_formula_defects(
        expected_formula_cells=["Z99"],
        formula_map={},
        value_map={"Z99": 1.23},
    )
    assert report["defects"][0]["repairable"] is False
