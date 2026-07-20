"""Tests for the added economics-audit rules (S4): duplicate owner, excessive burden."""

import pytest

from databossx.ownership import MineralOwner, division_of_interest, mineral_summary


def test_duplicate_owner_flagged():
    owners = [
        MineralOwner("Avery Minerals LLC", "1/2"),
        MineralOwner("avery minerals, llc", "1/4"),  # same owner, different spelling
        MineralOwner("Brand LP", "1/4"),
    ]
    out = mineral_summary(owners, "160", tract="T1")
    assert any("listed 2 times" in d for d in out.defects)


def test_no_duplicate_flag_for_distinct_owners():
    owners = [MineralOwner("A", "1/2"), MineralOwner("B", "1/2")]
    out = mineral_summary(owners, "160", tract="T1")
    assert not any("listed" in d for d in out.defects)


def test_excessive_burden_flagged():
    # royalty 3/4 + ORRI 1/4 = 8/8 -> WI has no net revenue.
    owners = [MineralOwner("A", "1", royalty="3/4", orri="1/4", lessee="Op")]
    out = division_of_interest(owners, "160", tract="T1")
    assert any("exceed 8/8" in d and "burdens" in d.lower() for d in out.defects)


def test_normal_burden_not_flagged():
    owners = [MineralOwner("A", "1", royalty="3/16", orri="1/32", lessee="Op")]
    out = division_of_interest(owners, "160", tract="T1")
    assert not any("burdens" in d.lower() for d in out.defects)
    assert not out.defects  # a clean 8/8, fully-leased, normal-burden tract


def test_golden_demo_shape_unchanged_by_new_rules():
    # The golden demo's tract 1 (7/8, over-conveyance) must still flag ONLY its
    # real defects -- no new false positives from the added rules.
    from databossx.command_center import ownership_to_tracts

    rows = [
        {"name": "Avery Minerals LLC", "mineral_interest": "1/2", "royalty": "3/16",
         "orri": "", "lessee": "Cedar", "tract": "Sec 31 T12N R24W", "gross_acres": "160"},
        {"name": "Brand Royalty LP", "mineral_interest": "1/4", "royalty": "3/16",
         "orri": "1/32", "lessee": "Cedar", "tract": "Sec 31 T12N R24W", "gross_acres": "160"},
        {"name": "Foster Heirs", "mineral_interest": "1/8", "royalty": "", "orri": "",
         "lessee": "", "tract": "Sec 31 T12N R24W", "gross_acres": "160"},
    ]
    tracts = ownership_to_tracts(rows)
    t = tracts[0]
    # Exactly one defect: the 7/8 shortfall. No duplicate/burden false positives.
    assert len(t.defects) == 1
    assert "not 8/8" in t.defects[0]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
