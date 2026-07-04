"""Regression tests for the Roger Mills title report builder (codexv1).

Covers the interest chain-out and the review-hardening fixes. Kept in the same
directory as the tool so `import roger_mills_title_report_builder` resolves under
pytest's default import mode.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

pytest.importorskip("openpyxl")

import roger_mills_title_report_builder as rm  # noqa: E402


# -- interest parsing -------------------------------------------------------
def test_parse_interest_fraction():
    assert rm.parse_interest_fraction("1/2") == Fraction(1, 2)
    assert rm.parse_interest_fraction("0.25") == Fraction(1, 4)
    assert rm.parse_interest_fraction("12.5%") == Fraction(1, 8)
    assert rm.parse_interest_fraction("1/8 RI") == Fraction(1, 8)
    assert rm.parse_interest_fraction("640") is None      # >1, not a fraction
    assert rm.parse_interest_fraction("") is None
    assert rm.parse_interest_fraction("n/a") is None


# -- chain-out --------------------------------------------------------------
def _row(grantor, grantee, interest, acreage="640"):
    return rm.TitleRow({"grantor": grantor, "grantee": grantee,
                        "interest": interest, "acreage": acreage}, "s", 1)


def test_chain_out_reconciles():
    chain = rm.chain_out_interest([
        _row("US PATENT", "ALICE", "1"),
        _row("ALICE", "BOB", "1/2"),
        _row("BOB", "CAROL", "1/2"),
    ])
    assert chain["ownership"]["ALICE"] == Fraction(1, 2)
    assert chain["ownership"]["CAROL"] == Fraction(1, 2)
    assert chain["reconciles"] and chain["gap_count"] == 0
    assert chain["gross_acres"] == 640.0


def test_chain_out_flags_vesting_gap():
    chain = rm.chain_out_interest([
        _row("US PATENT", "ALICE", "1"),
        _row("ZED", "EVE", "1/2"),   # ZED never vested
    ])
    assert chain["gap_count"] == 1
    assert not chain["reconciles"]
    assert any("not previously vested" in w for w in chain["warnings"])


def test_chain_out_self_conveyance_and_blank_grantee():
    chain = rm.chain_out_interest([
        _row("US PATENT", "ALICE", "1"),
        _row("ALICE", "ALICE", "1/2"),   # correction
        _row("ALICE", "", "1/4"),        # blank grantee
    ])
    assert chain["ownership"].get("ALICE") == Fraction(1)
    assert "" not in chain["ownership"]
    assert len(chain["warnings"]) == 2


# -- review-hardening fixes -------------------------------------------------
def test_header_matching_rejects_short_token_substrings():
    assert rm.match_header("Notes") == "remarks"     # not entry_no via "no"
    assert rm.match_header("Total") is None           # not grantee via "to"
    assert rm.match_header("Grantor") == "grantor"
    assert rm.match_header("Book No") == "book"
    assert rm.match_header("Recording Date") == "recorded_date"


def test_norm_text_integral_float_has_no_decimal():
    # A doc number read as 456.0 must dedup-key identically to "456".
    assert rm.norm_text(456.0) == "456"
    assert rm.norm_doc_ref(456.0) == "456"


def test_norm_date_does_not_fabricate():
    # A page/reference number is not a date; a messy non-date cell is not a date.
    assert rm.norm_date("12345") is None            # out of serial range
    assert rm.norm_date("Section 31 twp 12N") is None
    # A real date still parses.
    assert rm.norm_date("1975-06-01") is not None
