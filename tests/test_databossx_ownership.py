"""Exact-math tests for the DataBossX ownership / WI / NRI calculator.

Every assertion is an *exact* Fraction identity -- if any of these ever needs a
tolerance, floats have crept in and the calculator is fabricating.
"""

from fractions import Fraction

import pytest

from databossx.ownership import (
    MineralOwner,
    division_of_interest,
    mineral_net_acres,
    mineral_summary,
    royalty_nri,
    working_interest_nri,
)


# -- direct calculators -----------------------------------------------------
def test_net_mineral_acres_exact():
    # 1/2 of 160 gross = 80 net mineral acres, exactly.
    assert mineral_net_acres("1/2", "160") == Fraction(80)
    # 5/128 of 640 = 25 NMA exactly (a fraction a float cannot represent).
    assert mineral_net_acres("5/128", "640") == Fraction(25)


def test_net_mineral_acres_unparseable_returns_none():
    assert mineral_net_acres("garbage", "160") is None
    assert mineral_net_acres("1/2", "not-acres") is None


def test_royalty_nri_exact():
    # A 1/2 mineral owner under a 3/16 lease keeps 3/32 royalty NRI.
    assert royalty_nri("1/2", "3/16") == Fraction(3, 32)


def test_working_interest_nri_classic_identity():
    # Full WI under a 1/8 lease -> 7/8 NRI. The textbook case.
    assert working_interest_nri("1", "1/8") == Fraction(7, 8)
    # 1/2 WI, 3/16 royalty, 1/32 ORRI -> 1/2 * (1 - 3/16 - 1/32) = 25/64.
    assert working_interest_nri("1/2", "3/16", "1/32") == Fraction(25, 64)


def test_working_interest_nri_negative_when_overburdened():
    # Burdens exceeding 8/8 produce a negative NRI (a defect the caller flags),
    # never a clamped-to-zero fabrication.
    assert working_interest_nri("1", "3/4", "1/2") == Fraction(-1, 4)


# -- mineral roll-up + 8/8 check --------------------------------------------
def test_mineral_summary_balances_to_eight_eighths():
    owners = [
        MineralOwner("A", "1/2"),
        MineralOwner("B", "1/4"),
        MineralOwner("C", "1/4"),
    ]
    out = mineral_summary(owners, "320", tract="T1")
    assert out.total_mineral == Fraction(1)
    assert not out.defects  # sums exactly to 8/8
    nma = {r.name: r.net_mineral_acres for r in out.mineral_rows}
    assert nma["A"] == Fraction(160)
    assert nma["B"] == Fraction(80)
    assert nma["C"] == Fraction(80)


def test_mineral_summary_flags_shortfall_not_normalized():
    owners = [MineralOwner("A", "1/2"), MineralOwner("B", "1/4")]  # only 3/4
    out = mineral_summary(owners, "160", tract="T1")
    assert out.total_mineral == Fraction(3, 4)
    assert out.defects and "not 8/8" in out.defects[0]
    # The reported interests are NOT scaled up to force a balance.
    assert out.mineral_rows[0].mineral_interest == Fraction(1, 2)


def test_mineral_summary_unparseable_owner_is_review_no_guess():
    owners = [MineralOwner("A", "1/2"), MineralOwner("B", "???")]
    out = mineral_summary(owners, "160")
    b = [r for r in out.mineral_rows if r.name == "B"][0]
    assert b.status == "review"
    assert b.mineral_interest is None  # not invented
    assert any("unparseable" in d or "review" in d for d in out.defects)


# -- full division of interest ----------------------------------------------
def test_division_of_interest_fully_leased_sums_to_eight_eighths():
    # Two owners, each leased at 1/8 royalty; unit fully leased.
    owners = [
        MineralOwner("A", "1/2", royalty="1/8", lessee="OperatorCo"),
        MineralOwner("B", "1/2", royalty="1/8", lessee="OperatorCo"),
    ]
    out = division_of_interest(owners, "640", tract="T1")
    # Leased fraction is the whole estate.
    assert out.leased_mineral == Fraction(1)
    # WI totals to 8/8.
    assert out.total_working_interest == Fraction(1)
    # All NRI (WI + royalty) totals to 8/8 exactly.
    assert out.total_nri == Fraction(1)
    assert not out.defects


def test_division_of_interest_wi_and_royalty_values():
    owners = [MineralOwner("A", "1", royalty="3/16", lessee="Op")]
    out = division_of_interest(owners, "160", tract="T1")
    wi = [r for r in out.doi_rows if r.role == "working_interest"][0]
    ro = [r for r in out.doi_rows if r.role == "royalty"][0]
    assert wi.working_interest == Fraction(1)
    assert wi.nri == Fraction(13, 16)   # 1 * (1 - 3/16)
    assert ro.nri == Fraction(3, 16)    # lessor royalty
    assert wi.nri + ro.nri == Fraction(1)


def test_division_of_interest_with_orri():
    owners = [MineralOwner("A", "1", royalty="1/8", orri="1/16", lessee="Op")]
    out = division_of_interest(owners, "160")
    roles = {r.role: r for r in out.doi_rows}
    assert roles["working_interest"].nri == Fraction(1) * (1 - Fraction(1, 8) - Fraction(1, 16))
    assert roles["royalty"].nri == Fraction(1, 8)
    assert roles["orri"].nri == Fraction(1, 16)
    # Everything still distributes to exactly 8/8.
    assert out.total_nri == Fraction(1)
    assert not out.defects


def test_division_of_interest_partly_unleased():
    # A leased (1/2), B open (1/2). WI + NRI account only for the leased half.
    owners = [
        MineralOwner("A", "1/2", royalty="1/4", lessee="Op"),
        MineralOwner("B", "1/2"),  # unleased
    ]
    out = division_of_interest(owners, "160")
    assert out.leased_mineral == Fraction(1, 2)
    assert out.total_working_interest == Fraction(1, 2)
    # Leased NRI = WI NRI + royalty NRI = 1/2*(3/4) + 1/2*(1/4) = 1/2 = leased frac.
    leased_nri = sum(r.nri for r in out.doi_rows
                     if r.role != "mineral" and r.nri is not None)
    assert leased_nri == Fraction(1, 2)
    # The open half is carried as a mineral row, not fabricated into a WI.
    assert any(r.role == "mineral" and r.lessee == "" for r in out.doi_rows)
    assert not out.defects


def test_division_of_interest_overburden_flags_review():
    owners = [MineralOwner("A", "1", royalty="7/8", orri="1/4", lessee="Op")]
    out = division_of_interest(owners, "160")
    wi = [r for r in out.doi_rows if r.role == "working_interest"][0]
    assert wi.status == "review"
    assert "negative NRI" in wi.remarks


def test_no_fabrication_on_unparseable_royalty():
    owners = [MineralOwner("A", "1", royalty="bad", lessee="Op")]
    out = division_of_interest(owners, "160")
    wi = [r for r in out.doi_rows if r.role == "working_interest"][0]
    assert wi.status == "review"
    assert wi.nri is None  # never guessed


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
