"""Tests for legal-description normalization (Section/Township/Range)."""

import pytest

from databossx.legal import canonical_key, parse_legal, tract_key


def test_abbreviated_form():
    ld = parse_legal("Sec 31 T12N R24W")
    assert (ld.section, ld.township, ld.range) == ("31", "12N", "24W")
    assert ld.key == "31-12N-24W"


def test_spelled_out_form():
    assert canonical_key("Section 31, Township 12 North, Range 24 West") == "31-12N-24W"


def test_compact_hyphenated_form():
    assert canonical_key("31-12N-24W") == "31-12N-24W"
    assert canonical_key("S31-T12N-R24W") == "31-12N-24W"
    assert canonical_key("Sec. 31, T-12-N, R-24-W") == "31-12N-24W"


def test_all_spellings_collapse_to_one_key():
    forms = ["Sec 31 T12N R24W",
             "Section 31, Township 12 North, Range 24 West",
             "31-12N-24W", "S31-T12N-R24W"]
    assert len({canonical_key(f) for f in forms}) == 1


def test_leading_lot_call_still_finds_str():
    assert canonical_key("Lot 5 of Sec 9 T9N R22W") == "9-9N-22W"


def test_incomplete_returns_none_not_a_guess():
    assert canonical_key("no survey here") is None
    assert canonical_key("Section 31 only") is None
    assert parse_legal("Township 12 North").section is None


def test_tract_key_falls_back_to_alphanumeric_squash():
    # Non-parseable descriptors still get a stable, non-empty key.
    assert tract_key("Some Named Tract #2") == "SOMENAMEDTRACT2"
    # Parseable ones use the canonical key.
    assert tract_key("Sec 31 T12N R24W") == "31-12N-24W"


def test_south_and_east_directions():
    assert canonical_key("Sec 4 T3S R1E") == "4-3S-1E"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
