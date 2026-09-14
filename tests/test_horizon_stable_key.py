"""House stable-key normalization and overlap collapse."""

import pytest

from horizon.stable_key import (
    StableKeyError,
    TractEntry,
    dedupe,
    normalize_bookpage,
    normalize_docno,
    stable_key,
)


def test_modern_and_legacy_document_numbers() -> None:
    assert normalize_docno("2026-09901") == "2026-09901"
    assert normalize_docno("#0900001") == "900001"
    assert normalize_docno("N/A") == ""
    assert normalize_docno(None) == ""


def test_bookpage_zero_pad_and_suffix() -> None:
    assert normalize_bookpage("654-561") == "0654-0561"
    assert normalize_bookpage("25mr-347") == "25MR-0347"
    assert normalize_bookpage("") == ""


def test_stable_key_allows_one_missing_half() -> None:
    assert stable_key("2026-09901", None) == "2026-09901|"
    assert stable_key(None, "0654-0561") == "|0654-0561"
    with pytest.raises(StableKeyError):
        stable_key(None, None)


def test_dedupe_reports_overlapping_raw_rows() -> None:
    entries = [
        TractEntry(page=1, row=1, docno="900001", bookpage="0654-0561"),
        TractEntry(page=12, row=3, docno="900001", bookpage="0654-0561", source="typed"),
        TractEntry(page=2, row=1, docno="2026-09901"),
    ]
    by_key, overlaps = dedupe(entries)
    assert overlaps == ["900001|0654-0561"]
    assert len(by_key["900001|0654-0561"]) == 2
    assert "2026-09901|" in by_key
