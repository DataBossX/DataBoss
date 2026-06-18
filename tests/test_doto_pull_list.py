"""Tests for doto pull-list normalization & dedup (cost-affecting logic).

The dedup key decides which images get (paid) downloads, so its correctness is
financially material — hence the focused coverage here.
"""
import importlib

import pytest

pytest.importorskip("pandas")
pl = importlib.import_module("processors.pull_list")


def test_column_alias_mapping():
    assert pl._normalize_col_name("Doc No") == "instrument_number"
    assert pl._normalize_col_name("BK") == "book"
    assert pl._normalize_col_name("Recording Date") == "recording_date"
    assert pl._normalize_col_name("totally unknown") is None


def test_county_normalization_titlecases_known():
    assert pl._normalize_county("oklahoma") == "Oklahoma"
    assert pl._normalize_county("LE FLORE") == "Le Flore"
    assert pl._normalize_county("") == ""
    # Unknown county is preserved (title-cased) rather than dropped.
    assert pl._normalize_county("nowhere") == "Nowhere"


def test_instrument_type_normalization():
    assert pl._normalize_instrument_type("wd") == "Warranty Deed"
    assert pl._normalize_instrument_type("OIL AND GAS LEASE") == "Oil and Gas Lease"
    assert pl._normalize_instrument_type("") == ""
    assert pl._normalize_instrument_type("weird type") == "Weird Type"


def test_book_page_strips_trailing_float_zero():
    assert pl._normalize_book_page("123.0") == "123"
    assert pl._normalize_book_page("ab12") == "AB12"
    assert pl._normalize_book_page(None) == ""


def test_dedup_key_is_order_stable_and_upper():
    row = {"county": "Tulsa", "book": "1", "page": "2",
           "instrument_number": "abc", "image_number": "x"}
    key = pl._build_dedup_key(row)
    assert key == "TULSA|1|2|ABC|X"


def test_dedup_key_distinguishes_distinct_rows():
    a = pl._build_dedup_key({"county": "Tulsa", "instrument_number": "1"})
    b = pl._build_dedup_key({"county": "Tulsa", "instrument_number": "2"})
    assert a != b


def test_dedup_key_matches_for_equivalent_rows():
    a = pl._build_dedup_key({"county": "tulsa", "book": "1"})
    b = pl._build_dedup_key({"county": "TULSA", "book": "1"})
    assert a == b
