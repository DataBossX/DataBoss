"""Apply the Section 11 grid to an existing workbook without changing values."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.worksheet.worksheet import Worksheet

from .profile import (
    CENTER_NO_WRAP,
    CHECKLIST_MARKER,
    CHECKLIST_SCALE,
    CHECKLIST_WIDTHS,
    COUNTY_HEADERS,
    COUNTY_WIDTHS,
    DATE_HEADERS,
    FEDERAL_HEADERS,
    FEDERAL_WIDTHS,
    FONT_COLOR,
    FONT_NAME,
    FONT_SIZE,
    HEADER_ROW_HEIGHT,
    INTEGER_FORMAT,
    MARGIN_BOTTOM,
    MARGIN_FOOTER,
    MARGIN_HEADER,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    MAX_DATA_ROW_HEIGHT,
    META_ROW_HEIGHT,
    PAPER_LETTER,
    ROW_HEIGHT_STEP,
    DATE_FORMAT,
    BORDER_COLOR,
)


class UnrecognizedWorkbook(ValueError):
    """Raised when no sheet matches an index or checklist grid."""


@dataclass(frozen=True)
class SheetResult:
    sheet: str
    kind: str
    header_row: int
    last_row: int
    columns: int


_THIN = Side(style="thin", color=BORDER_COLOR)
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_NO_BORDER = Border()
_NO_FILL = PatternFill(fill_type=None)
_FONT = Font(name=FONT_NAME, size=FONT_SIZE, color=FONT_COLOR, bold=False)
_FONT_BOLD = Font(name=FONT_NAME, size=FONT_SIZE, color=FONT_COLOR, bold=True)
_LEFT_WRAP = Alignment(horizontal="left", vertical="top", wrap_text=True)
_CENTER_WRAP = Alignment(horizontal="center", vertical="top", wrap_text=True)
_CENTER_MIDDLE = Alignment(horizontal="center", vertical="center", wrap_text=True)
_CENTER_SHRINK = Alignment(
    horizontal="center",
    vertical="top",
    wrap_text=False,
    shrink_to_fit=True,
)


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return f"{value.month}/{value.day}/{value.year}"
    if isinstance(value, date):
        return f"{value.month}/{value.day}/{value.year}"
    return str(value)


def wrapped_lines(value: object, width: float) -> int:
    """Estimate wrapped lines the way the Section 11 index sizes a row."""
    text = _text(value)
    if text == "":
        return 1
    usable = max(width - 0.5, 1.0)
    lines = 0
    for segment in text.split("\n"):
        lines += max(1, math.ceil(len(segment) / usable))
    return lines


def data_row_height(lines: int) -> float:
    return float(min(MAX_DATA_ROW_HEIGHT, max(ROW_HEIGHT_STEP, ROW_HEIGHT_STEP * lines)))


def _headers(ws: Worksheet, row: int, count: int) -> tuple[str, ...]:
    found = []
    for col in range(1, count + 1):
        value = ws.cell(row, col).value
        found.append(value.strip() if isinstance(value, str) else "")
    return tuple(found)


def find_index(ws: Worksheet) -> tuple[str, int, tuple[str, ...], tuple[float, ...]] | None:
    limit = min(ws.max_row or 1, 20)
    for row in range(1, limit + 1):
        county = _headers(ws, row, len(COUNTY_HEADERS))
        if county == COUNTY_HEADERS:
            return "county", row, COUNTY_HEADERS, COUNTY_WIDTHS
        federal = _headers(ws, row, len(FEDERAL_HEADERS))
        if federal == FEDERAL_HEADERS:
            return "federal", row, FEDERAL_HEADERS, FEDERAL_WIDTHS
    return None


def is_checklist(ws: Worksheet) -> bool:
    title = (ws.title or "").lower()
    if "checklist" in title:
        return True
    for col in range(1, min(ws.max_column or 1, 12) + 1):
        value = ws.cell(2, col).value
        if isinstance(value, str) and value.strip() == CHECKLIST_MARKER:
            return True
    return False


def _paint(cell, font: Font, alignment: Alignment, border: Border) -> None:
    cell.font = font
    cell.alignment = alignment
    cell.border = border
    cell.fill = _NO_FILL


def _number_format(cell, header: str | None, center: bool) -> None:
    if isinstance(cell.value, (datetime, date)):
        cell.number_format = DATE_FORMAT
    elif center and isinstance(cell.value, int) and not isinstance(cell.value, bool):
        cell.number_format = INTEGER_FORMAT


def _page_index(ws: Worksheet) -> None:
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = PAPER_LETTER
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.scale = None
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_margins.left = MARGIN_LEFT
    ws.page_margins.right = MARGIN_RIGHT
    ws.page_margins.top = MARGIN_TOP
    ws.page_margins.bottom = MARGIN_BOTTOM
    ws.page_margins.header = MARGIN_HEADER
    ws.page_margins.footer = MARGIN_FOOTER
    ws.freeze_panes = None
    # openpyxl ignores a None assignment on print_title_rows, so clear the ranges directly.
    ws._print_rows = None
    ws._print_cols = None
    ws.sheet_format.defaultRowHeight = META_ROW_HEIGHT
    ws.page_setup.horizontalCentered = False
    ws.sheet_view.showGridLines = False


def _clear_outside(ws: Worksheet, last_row: int, columns: int) -> None:
    max_col = max(ws.max_column or 1, columns)
    max_row = max(ws.max_row or 1, last_row)
    for row in range(1, max_row + 1):
        for col in range(1, max_col + 1):
            inside = row <= last_row and col <= columns
            if inside:
                continue
            cell = ws.cell(row, col)
            _paint(cell, _FONT, _LEFT_WRAP, _NO_BORDER)


def apply_index(ws: Worksheet) -> SheetResult:
    found = find_index(ws)
    if found is None:
        raise UnrecognizedWorkbook(f"{ws.title} has no Section 11 index header")
    kind, header_row, headers, widths = found
    last_row = header_row
    for row in range(header_row, (ws.max_row or header_row) + 1):
        if any(ws.cell(row, col).value not in (None, "") for col in range(1, len(headers) + 1)):
            last_row = row
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width

    for row in range(1, header_row):
        ws.row_dimensions[row].height = META_ROW_HEIGHT
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row, col)
            label = col == 1 and isinstance(cell.value, str) and cell.value.endswith(":")
            _paint(cell, _FONT_BOLD if label else _FONT, _LEFT_WRAP, _NO_BORDER)
            if isinstance(cell.value, (datetime, date)):
                cell.number_format = DATE_FORMAT

    ws.row_dimensions[header_row].height = HEADER_ROW_HEIGHT
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(header_row, col)
        _paint(cell, _FONT_BOLD, _CENTER_WRAP, _BORDER)

    for row in range(header_row + 1, last_row + 1):
        lines = 1
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row, col)
            center = header in CENTER_NO_WRAP
            if header in DATE_HEADERS:
                alignment = _CENTER_WRAP
                wrap = True
            elif center:
                alignment = _CENTER_SHRINK
                wrap = False
            else:
                alignment = _LEFT_WRAP
                wrap = True
            _paint(cell, _FONT, alignment, _BORDER)
            _number_format(cell, header, center)
            if wrap:
                lines = max(lines, wrapped_lines(cell.value, widths[col - 1]))
        ws.row_dimensions[row].height = data_row_height(lines)

    _clear_outside(ws, last_row, len(headers))
    _page_index(ws)
    if ws.title == "Sheet1" and len(ws.parent.worksheets) == 1:
        ws.title = "Index"
    return SheetResult(ws.title, kind, header_row, last_row, len(headers))


def _page_checklist(ws: Worksheet) -> None:
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = PAPER_LETTER
    ws.page_setup.fitToWidth = None
    ws.page_setup.fitToHeight = None
    ws.page_setup.scale = CHECKLIST_SCALE
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=False)
    ws.page_margins.left = MARGIN_LEFT
    ws.page_margins.right = MARGIN_RIGHT
    ws.page_margins.top = MARGIN_TOP
    ws.page_margins.bottom = MARGIN_BOTTOM
    ws.page_margins.header = MARGIN_HEADER
    ws.page_margins.footer = MARGIN_FOOTER
    ws.freeze_panes = None
    ws._print_rows = None
    ws._print_cols = None
    ws.page_setup.horizontalCentered = False


def apply_checklist(ws: Worksheet) -> SheetResult:
    last_row = max(ws.max_row or 1, 1)
    last_col = max(min(ws.max_column or 1, len(CHECKLIST_WIDTHS)), 1)
    for index, width in enumerate(CHECKLIST_WIDTHS[:last_col], start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    for row in range(1, last_row + 1):
        lines = 1
        bold_row = any(ws.cell(row, col).font and ws.cell(row, col).font.bold for col in range(1, last_col + 1))
        has_value = any(ws.cell(row, col).value not in (None, "") for col in range(1, last_col + 1))
        for col in range(1, last_col + 1):
            cell = ws.cell(row, col)
            occupied = cell.value not in (None, "")
            bordered = bool(cell.border and cell.border.left and cell.border.left.style)
            bold = bool(cell.font and cell.font.bold) or (bold_row and occupied)
            if occupied or bordered:
                alignment = _CENTER_MIDDLE if bold else _LEFT_WRAP
                _paint(cell, _FONT_BOLD if bold else _FONT, alignment, _BORDER)
                if isinstance(cell.value, (datetime, date)):
                    cell.number_format = DATE_FORMAT
                width = CHECKLIST_WIDTHS[col - 1]
                lines = max(lines, wrapped_lines(cell.value, width))
            else:
                _paint(cell, _FONT, _LEFT_WRAP, _NO_BORDER)
        floor = HEADER_ROW_HEIGHT if bold_row and has_value else ROW_HEIGHT_STEP
        ws.row_dimensions[row].height = float(
            min(MAX_DATA_ROW_HEIGHT, max(floor, ROW_HEIGHT_STEP * lines))
        )
    _page_checklist(ws)
    return SheetResult(ws.title, "checklist", 0, last_row, last_col)


def apply_workbook(wb: Workbook) -> list[SheetResult]:
    results: list[SheetResult] = []
    for ws in wb.worksheets:
        if find_index(ws):
            results.append(apply_index(ws))
        elif is_checklist(ws):
            results.append(apply_checklist(ws))
    if not results:
        raise UnrecognizedWorkbook("workbook has no index or checklist sheet")
    return results


def apply_file(source: Path, dest: Path) -> list[SheetResult]:
    from openpyxl import load_workbook

    wb = load_workbook(source)
    results = apply_workbook(wb)
    dest.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dest)
    return results


def apply_directory(source: Path, dest: Path) -> list[tuple[Path, list[SheetResult]]]:
    written: list[tuple[Path, list[SheetResult]]] = []
    for path in sorted(source.rglob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        target = dest / path.relative_to(source)
        try:
            results = apply_file(path, target)
        except UnrecognizedWorkbook:
            continue
        written.append((target, results))
    if not written:
        raise UnrecognizedWorkbook(f"no index or checklist workbook under {source}")
    return written
