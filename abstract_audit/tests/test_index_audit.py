"""Tests for the abstract index auditor."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from index_audit import audit_workbook  # noqa: E402
from schema import COLUMNS, HEADER_KEYS, SECTION_15  # noqa: E402

# One clean row and the defects the auditor must catch.
GOOD_ROW = [
    "Mortgage", "Fred Christensen", "First/Denver Joint Stock Land Bank",
    "37714", "009M-0270", "12/1/1924", "1/5/1925",
    "E/2 E/2 of 15-45N-76W, aol", "",
]
MODERN_ROW = [
    "Joint Use Agreement", "Barn Owls, LLC", "Parliament Securities SPV, LLC",
    "2026-03115", "", "12/11/2025", "5/8/2026",
    "T45N-R76W, Section 15: Lots 11-14 (SW/4)", "",
]
BLANK_GRANTEE_ROW = [
    "Proof of Labor", "Dawn L. Carpenter", "",
    "343814", "72MR-0447", "8/27/1970", "9/3/1970", "Bob Nos. 58-60", "",
]
DUPLICATE_ROW = list(GOOD_ROW)  # same Doc No 37714


def _build(path: Path, rows: list[list[str]], *, header: bool = True) -> Path:
    wb = Workbook()
    ws = wb.active
    if header:
        values = {
            "Index County": "Campbell",
            "Lands": "T45N-R76W Section 15: All",
            "Date": "9/14/2026",
            "Starting Date": "Inception",
            "Date Posted Thru": "7/21/2026",
            "Indexed By": "Ryan Gille",
            "Project": "Abstract 4576 Overtime",
        }
        for key in HEADER_KEYS:
            ws.append([f"{key}:", values[key]])
    ws.append(list(COLUMNS))
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


def test_clean_index_is_fully_complete(tmp_path: Path) -> None:
    rep = audit_workbook(_build(tmp_path / "clean.xlsx", [GOOD_ROW, MODERN_ROW]))
    assert rep.row_count == 2
    assert rep.completeness == 1.0
    assert rep.column_order_ok
    assert rep.missing_header_keys == []
    assert rep.blank_required == []
    assert rep.duplicate_doc_nos == {}


def test_modern_row_without_book_page_is_not_a_defect(tmp_path: Path) -> None:
    rep = audit_workbook(_build(tmp_path / "modern.xlsx", [MODERN_ROW]))
    # Book-Page is optional, so it must not dent required completeness.
    assert rep.completeness == 1.0
    assert rep.columns["Book-Page"].blank == 1


def test_blank_required_cell_is_reported(tmp_path: Path) -> None:
    rep = audit_workbook(_build(tmp_path / "blank.xlsx", [GOOD_ROW, BLANK_GRANTEE_ROW]))
    assert rep.completeness < 1.0
    assert [d["column"] for d in rep.blank_required] == ["Grantee"]
    assert rep.blank_required[0]["doc_no"] == "343814"


def test_duplicate_doc_numbers_are_grouped(tmp_path: Path) -> None:
    rep = audit_workbook(_build(tmp_path / "dupe.xlsx", [GOOD_ROW, DUPLICATE_ROW]))
    assert list(rep.duplicate_doc_nos) == ["37714"]
    assert len(rep.duplicate_doc_nos["37714"]) == 2


def test_malformed_doc_no_and_date_are_flagged(tmp_path: Path) -> None:
    bad = list(GOOD_ROW)
    bad[3] = "n/a"
    bad[6] = "Jan 5 1925"
    rep = audit_workbook(_build(tmp_path / "bad.xlsx", [bad]))
    assert rep.malformed_doc_nos[0]["value"] == "n/a"
    assert rep.malformed_dates[0]["value"] == "Jan 5 1925"


def test_missing_header_block_is_reported(tmp_path: Path) -> None:
    rep = audit_workbook(_build(tmp_path / "nohdr.xlsx", [GOOD_ROW], header=False))
    assert set(rep.missing_header_keys) == set(HEADER_KEYS)


def test_section_15_expects_exactly_six_files() -> None:
    assert SECTION_15.expected_file_count() == 6


def test_missing_header_row_raises(tmp_path: Path) -> None:
    wb = Workbook()
    wb.active.append(["nothing", "useful"])
    wb.save(tmp_path / "junk.xlsx")
    with pytest.raises(ValueError, match="no 'Document Type' header row"):
        audit_workbook(tmp_path / "junk.xlsx")
