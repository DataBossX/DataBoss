"""Tests for the exact interest reconciliation engine (no floats)."""

from decimal import Decimal
from fractions import Fraction

import pytest

from horizon.interest import (
    InterestError,
    format_acres,
    format_fraction,
    net_acres,
    parse_interest,
    reconcile,
    sum_interests,
    try_parse_interest,
)


@pytest.mark.parametrize("text,expected", [
    ("1/2", Fraction(1, 2)),
    ("5/128", Fraction(5, 128)),
    ("0.5", Fraction(1, 2)),
    ("0.1", Fraction(1, 10)),           # float 0.1 is inexact; Fraction is exact
    ("12.5%", Fraction(1, 8)),
    ("100%", Fraction(1, 1)),
    ("1 1/2", Fraction(3, 2)),
    ("1/2 of 8/8", Fraction(1, 2)),
    ("1/16 of 1/2", Fraction(1, 32)),
    ("an undivided 1/4 interest", Fraction(1, 4)),
    ("1/16th", Fraction(1, 16)),
    (3, Fraction(3)),
    (Fraction(2, 3), Fraction(2, 3)),
    (Decimal("0.25"), Fraction(1, 4)),
])
def test_parse_interest(text, expected):
    assert parse_interest(text) == expected


def test_parse_interest_is_exact_not_float():
    # The whole point: 0.1 + 0.2 in floats != 0.3, but here it's exact.
    total = parse_interest("0.1") + parse_interest("0.2")
    assert total == Fraction(3, 10)
    assert isinstance(total, Fraction)


@pytest.mark.parametrize("bad", ["", "abc", "1/0", None, "//"])
def test_parse_interest_rejects_garbage(bad):
    with pytest.raises(InterestError):
        parse_interest(bad)


def test_try_parse_returns_none():
    assert try_parse_interest("nonsense") is None
    assert try_parse_interest("3/4") == Fraction(3, 4)


def test_net_acres_exact():
    # 1/16 of 160 gross acres = exactly 10 net mineral acres.
    assert net_acres("1/16", 160) == Fraction(10)
    assert net_acres("1/3", "160") == Fraction(160, 3)
    assert format_acres(net_acres("1/3", 160)) == "53.3333"


def test_reconcile_balanced():
    r = reconcile("8/8", "1/2")
    assert r.status == "balanced"
    assert r.retained == Fraction(1, 2)
    assert not r.needs_review


def test_reconcile_grantor_minus_conveyed():
    r = reconcile("3/4", "1/4")
    assert r.retained == Fraction(1, 2)
    assert r.status == "balanced"


def test_reconcile_over_conveyance_flagged_not_fabricated():
    r = reconcile("1/4", "1/2")
    assert r.status == "over_conveyance"
    assert r.retained == Fraction(-1, 4)
    assert r.needs_review
    assert "over-conveyance" in r.note.lower()


def test_reconcile_unknown_is_examiner_review():
    r = reconcile(None, "1/2")
    assert r.status == "examiner_review"
    assert r.retained is None
    assert "missing" in r.note.lower()


def test_reconcile_empty_string_unknown():
    r = reconcile("", "")
    assert r.status == "examiner_review"


def test_sum_interests_exact():
    assert sum_interests(["1/8", "1/8", "1/4"]) == Fraction(1, 2)


def test_format_fraction():
    assert format_fraction(Fraction(1, 2)) == "1/2"
    assert format_fraction(Fraction(4, 2)) == "2"
