"""Synthetic checks for the Section 11 styler. Fixtures are fictional."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from section_style import UnrecognizedWorkbook, apply_directory, apply_workbook, audit_workbook
from section_style.profile import COUNTY_HEADERS, COUNTY_WIDTHS, FEDERAL_HEADERS, FEDERAL_WIDTHS


def _index(headers, rows, *, sheet_name="Sheet1", font="Aptos Narrow"):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws["A1"] = "County:"
    ws["B1"] = "Example"
    ws["A2"] = "Lands:"
    ws["B2"] = "Lot 1 of 1-1N-1W"
    ws["A3"] = "Date:"
    ws["B3"] = datetime(2026, 1, 2)
    for col, header in enumerate(headers, start=1):
        ws.cell(9, col, header)
    for offset, row in enumerate(rows):
        for col, value in enumerate(row, start=1):
            ws.cell(10 + offset, col, value)
    ws.freeze_panes = "A10"
    ws.print_title_rows = "9:9"
    ws.page_setup.orientation = "portrait"
    ws.page_setup.paperSize = 8
    for row in ws.iter_rows():
        for cell in row:
            cell.font = Font(name=font, size=12)
    ws.row_dimensions[10].height = 257
    return wb


def test_county_style_preserves_values_and_matches_grid():
    original = "Example Grantor, LLC\nExample Grantee"
    legal = "Lot 1 of 1-1N-1W"
    wb = _index(
        COUNTY_HEADERS,
        [
            ["Deed", original, "Example Grantee", 1001, "0001-0001", datetime(2024, 3, 4), None, legal, None],
            ["Deed", "A" * 400, "B", None, None, None, None, legal, "missing image"],
        ],
    )
    apply_workbook(wb)
    ws = wb.active
    assert ws.title == "Index"
    assert ws["B10"].value == original
    assert ws["D10"].value == 1001
    assert ws["G10"].value is None
    assert ws["I10"].value is None
    assert ws["H11"].value == legal
    assert ws.freeze_panes is None
    assert ws.print_title_rows is None
    assert ws.page_setup.orientation == "landscape"
    assert str(ws.page_setup.paperSize) == "1"
    assert ws.page_setup.fitToWidth == 1
    assert ws.page_margins.left == 0.7
    assert ws.page_margins.top == 0.3
    assert [ws.column_dimensions[chr(ord("A") + i)].width for i in range(9)] == list(COUNTY_WIDTHS)
    assert ws["A1"].font.bold is True
    assert ws["A1"].font.name == "Calibri"
    assert not (ws["A1"].border.left and ws["A1"].border.left.style)
    assert ws["A9"].font.bold is True
    assert ws["A9"].alignment.horizontal == "center"
    assert ws["D10"].alignment.shrink_to_fit is True
    assert ws["D10"].alignment.wrap_text is False
    assert ws["D10"].number_format == "0"
    assert ws["F10"].number_format == "m/d/yyyy"
    assert ws["F10"].alignment.horizontal == "center"
    assert ws["A10"].alignment.wrap_text is True
    assert ws.row_dimensions[9].height == 30
    assert ws.row_dimensions[8].height == 15
    assert ws.row_dimensions[11].height <= 150
    assert audit_workbook(wb) == []


def test_federal_widths_and_blank_file_number():
    wb = _index(
        FEDERAL_HEADERS,
        [["Patent", "Example Grantor", "Example Grantee", None, 4, datetime(2020, 5, 6), None, None, "Lot 1 of 1-1N-1W", None]],
    )
    apply_workbook(wb)
    ws = wb["Index"]
    assert ws["D10"].value is None
    assert ws["J10"].value is None
    assert [ws.column_dimensions[chr(ord("A") + i)].width for i in range(10)] == list(FEDERAL_WIDTHS)
    assert ws["E10"].alignment.shrink_to_fit is True
    assert audit_workbook(wb) == []


def test_checklist_keeps_text_and_prints_at_45_percent():
    wb = Workbook()
    ws = wb.active
    ws.title = "Abstract checklist"
    ws["A2"] = "County Index"
    ws["B2"] = "Certification Letter"
    ws["A2"].font = Font(name="Aptos Narrow", bold=True, size=11)
    ws["B2"].font = Font(name="Aptos Narrow", bold=True, size=11)
    ws["A3"] = "Ready"
    ws["A3"].font = Font(name="Aptos Narrow", size=11)
    ws["A6"] = datetime(2026, 1, 2)
    ws.row_dimensions[3].height = 180
    ws.page_setup.orientation = "portrait"
    apply_workbook(wb)
    assert ws["A3"].value == "Ready"
    assert isinstance(ws["A6"].value, datetime)
    assert ws["A6"].number_format == "m/d/yyyy"
    assert ws["A2"].font.name == "Calibri"
    assert ws["A2"].font.bold is True
    assert ws["A2"].alignment.horizontal == "center"
    assert ws["A3"].border.left.style == "thin"
    assert ws["A3"].fill.patternType is None
    assert ws.page_setup.scale == 45
    assert ws.page_setup.orientation == "landscape"
    assert ws.page_margins.top == 0.3
    assert ws.row_dimensions[3].height <= 150
    assert audit_workbook(wb) == []


def test_apply_is_idempotent():
    wb = _index(COUNTY_HEADERS, [["Deed", "Example Grantor", "Example Grantee", 7, "1-1", None, None, "Lot 1 of 1-1N-1W", ""]])
    apply_workbook(wb)
    first = [ws.row_dimensions[row].height for ws in wb.worksheets for row in range(1, 11)]
    apply_workbook(wb)
    second = [ws.row_dimensions[row].height for ws in wb.worksheets for row in range(1, 11)]
    assert first == second
    assert audit_workbook(wb) == []


def test_unrecognized_workbook_is_rejected():
    wb = Workbook()
    wb.active["A1"] = "notes"
    with pytest.raises(UnrecognizedWorkbook):
        apply_workbook(wb)


def test_apply_directory_skips_unknown_workbooks(tmp_path: Path):
    good = tmp_path / "in" / "good.xlsx"
    bad = tmp_path / "in" / "notes.xlsx"
    good.parent.mkdir()
    book = _index(COUNTY_HEADERS, [["Deed", "Example Grantor", "Example Grantee", 1, None, None, None, "Lot 1 of 1-1N-1W", None]])
    book.save(good)
    other = Workbook()
    other.active["A1"] = "notes"
    other.save(bad)
    written = apply_directory(tmp_path / "in", tmp_path / "out")
    assert len(written) == 1
    saved = load_workbook(tmp_path / "out" / "good.xlsx")
    assert saved.active["B10"].value == "Example Grantor"
    assert audit_workbook(saved) == []
