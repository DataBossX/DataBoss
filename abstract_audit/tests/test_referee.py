"""Tests for the referee (cross-row, cross-workbook) defect checks."""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from referee import (  # noqa: E402
    check_date_order,
    check_entity_consistency,
    read_rows,
    split_entity,
)
from schema import COLUMNS  # noqa: E402


def _build(path: Path, rows: list[list[str]]) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(["Index County:", "Campbell"])
    ws.append(list(COLUMNS))
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


def _row(doc_no: str, grantor: str, grantee: str, doc_date: str, rec_date: str):
    return ["Assignment", grantor, grantee, doc_no, "", doc_date, rec_date, "", ""]


def test_rec_date_before_doc_date_is_flagged(tmp_path: Path) -> None:
    # The Section 15 WYW-021220 defect: recorded before the document existed.
    path = _build(tmp_path / "d.xlsx", [_row("1", "A", "B", "8/1/2025", "7/31/2025")])
    defects = check_date_order(path, read_rows(path))
    assert len(defects) == 1
    assert defects[0].rec_date == "7/31/2025"
    assert "precedes" in defects[0].describe()


def test_same_day_recording_is_not_a_defect(tmp_path: Path) -> None:
    path = _build(tmp_path / "s.xlsx", [_row("1", "A", "B", "8/1/2025", "8/1/2025")])
    assert check_date_order(path, read_rows(path)) == []


def test_normal_ordering_is_not_a_defect(tmp_path: Path) -> None:
    path = _build(tmp_path / "n.xlsx", [_row("1", "A", "B", "8/1/2025", "9/17/2025")])
    assert check_date_order(path, read_rows(path)) == []


def test_missing_dates_are_skipped_not_flagged(tmp_path: Path) -> None:
    path = _build(tmp_path / "m.xlsx", [_row("1", "A", "B", "", "9/17/2025")])
    assert check_date_order(path, read_rows(path)) == []


def test_split_entity_separates_stem_from_suffix() -> None:
    assert split_entity("Jibber Resources, LLC") == ("jibber resources", "LLC")
    assert split_entity("Jibber Resources Inc.") == ("jibber resources", "INC")
    assert split_entity("KAB Acquisition L.L.L.P.-VI") is None  # suffix not terminal
    assert split_entity("The Public") is None


def test_entity_suffix_conflict_across_workbooks_is_flagged() -> None:
    # The Section 15 WYW-089855 defect: LLC in one book, Inc. in another.
    per_wb = {
        "county.xlsx": [
            dict(zip(COLUMNS, ["Assignment", "Jibber Resources, LLC", "Brian Law",
                               "2025-06006", "", "", "", "", ""]))
        ],
        "WYW-089855.xlsx": [
            dict(zip(COLUMNS, ["Assignment", "Jibber Resources Inc.", "Brian Law",
                               "", "", "", "", "", ""]))
        ],
    }
    defects = check_entity_consistency(per_wb)
    assert len(defects) == 1
    assert defects[0].stem == "jibber resources"
    assert set(defects[0].variants) == {"LLC", "INC"}


def test_consistent_spelling_is_not_flagged() -> None:
    per_wb = {
        "a.xlsx": [dict(zip(COLUMNS, ["Assignment", "Barn Owls, LLC", "X",
                                      "", "", "", "", "", ""]))],
        "b.xlsx": [dict(zip(COLUMNS, ["Assignment", "Barn Owls, LLC", "Y",
                                      "", "", "", "", "", ""]))],
    }
    assert check_entity_consistency(per_wb) == []


def test_co_and_company_are_treated_as_the_same_suffix() -> None:
    per_wb = {
        "a.xlsx": [dict(zip(COLUMNS, ["Deed", "Davis Oil Company", "X",
                                      "", "", "", "", "", ""]))],
        "b.xlsx": [dict(zip(COLUMNS, ["Deed", "Davis Oil Co.", "Y",
                                      "", "", "", "", "", ""]))],
    }
    assert check_entity_consistency(per_wb) == []
