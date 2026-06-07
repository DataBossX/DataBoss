"""Tests for parsing / extraction helpers."""
import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from title_report_factory.modules.party_and_date_extractor import (
    to_short_date, split_parties, grantor_grantee)
from title_report_factory.modules.interest_extractor import (
    parse_royalty, royalty_decimal, parse_acres, interest_type)
from title_report_factory.modules.legal_description_extractor import (
    matches_subject, extract_quarter_calls, tract_for_quarter)
from title_report_factory.modules.document_classifier import classify

SUBJECT = {"section": "27", "township": "11N", "range": "25W"}


def test_short_date_from_datetime():
    assert to_short_date(datetime.datetime(2002, 9, 30)) == "9/30/2002"


def test_short_date_from_iso_string():
    assert to_short_date("2017-10-24 00:00:00") == "10/24/2017"


def test_short_date_blank():
    assert to_short_date("Not provided") == ""
    assert to_short_date(None) == ""


def test_grantor_grantee_arrow():
    g, e = grantor_grantee("KL CHK SPV, LLC -> Diversified Production, LLC")
    assert g == "KL CHK SPV, LLC"
    assert e == "Diversified Production, LLC"


def test_split_parties():
    parts = split_parties("A, LLC; B, LP -> C, LLC")
    assert "A, LLC" in parts and "C, LLC" in parts


def test_royalty_fraction():
    assert parse_royalty("3/16") == "3/16"
    assert abs(royalty_decimal("3/16") - 0.1875) < 1e-9
    assert parse_royalty(0.1875) == "0.1875"


def test_parse_acres():
    assert parse_acres("160.00 acres, more or less") == "160.00"


def test_matches_subject():
    assert matches_subject("NE/4 Section 27-11N-25W", SUBJECT)
    assert matches_subject("S27 T11N R25W", SUBJECT)
    assert not matches_subject("Section 33 T12N R22W", SUBJECT)


def test_quarter_calls_and_tract():
    assert tract_for_quarter("NE/4 Section 27-11N-25W") == "NE/4"
    assert tract_for_quarter("SW/4 less church") == "SW/4"
    assert "NE/4" in extract_quarter_calls("NE/4 SE/4 of 27")


def test_section_wide_not_misfiled_as_se():
    # Regression: 'Section ...' must NOT match 'SE' (SECTION starts with SE).
    assert tract_for_quarter("Section 27-11N-25W") == ""
    assert tract_for_quarter("SE/4 Section 27-11N-25W") == "SE/4"


def test_classifier():
    assert classify("Oil and Gas Lease")[0] == "Oil & Gas Lease"
    assert classify("Wellbore Assignment")[0] == "Wellbore Assignment"
    assert classify("Mineral Deed")[0] == "Mineral Deed"
    assert classify("Merger")[0] == "Merger"


def test_interest_type():
    assert "Working" in interest_type("Wellbore Assignment")
    assert interest_type("Merger") == "Corporate succession (entity-level)"
