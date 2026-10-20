"""Apply the Section 11 overtime index style to any section workbook.

The style was measured from the Section 11 overtime package: county index,
BLM index, and abstract checklist. This module paints fonts, borders,
alignment, column widths, and print setup. It does not write, clear, or
invent cell values.

Expected index layout, already present in the workbook:

- rows 1-7 metadata labels in column A and values in column B
- row 8 blank
- row 9 column headers
- instrument rows from row 10

County headers are Document Type, Grantor, Grantee, Doc No, Book-Page,
Date of Doc, Rec Date, Legal Description, Comments. BLM headers add File No,
Page, Comments, Legal Description, and Part. File No and Comments stay
whatever the sheet already contains, including blanks.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Sequence

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

FONT_NAME = "Calibri"
FONT_SIZE = 11
FONT_COLOR = "FF000000"
BORDER_COLOR = "FF000000"
DATE_FORMAT = "m/d/yyyy"
INTEGER_FORMAT = "0"

# Centimetres, measured from the Section 11 overtime ODS column styles.
COUNTY_WIDTHS_CM = (
    8.22854166666667,
    9.07520833333333,
    9.18104166666667,
    1.984375,
    1.95791666666667,
    2.06375,
    1.984375,
    9.445625,
    2.56645833333333,
)
BLM_WIDTHS_CM = (
    8.016875,
    8.334375,
    8.54604166666667,
    1.349375,
    0.978958333333333,
    2.06375,
    1.984375,
    1.95791666666667,
    8.78416666666667,
    0.846666666666667,
)
CHECKLIST_WIDTHS = (
    14.0,
    18.0,
    29.28515625,
    30.140625,
    38.0,
    32.7109375,
    28.0,
    18.0,
    17.7109375,
    18.85546875,
    15.85546875,
)

COUNTY_HEADERS = (
    "Document Type",
    "Grantor",
    "Grantee",
    "Doc No",
    "Book-Page",
    "Date of Doc",
    "Rec Date",
    "Legal Description",
    "Comments",
)
BLM_HEADERS = (
    "Document Type",
    "Grantor",
    "Grantee",
    "File No",
    "Page",
    "Date of Doc",
    "Rec Date",
    "Comments",
    "Legal Description",
    "Part",
)

# 1-based columns whose Section 11 data cells are centered and shrink-to-fit.
COUNTY_CENTER_COLUMNS = {4, 5, 6, 7}
BLM_CENTER_COLUMNS = {4, 5, 6, 7, 10}
COUNTY_DATE_COLUMNS = {6, 7}
BLM_DATE_COLUMNS = {6, 7}
COUNTY_INTEGER_COLUMNS = {4}
BLM_INTEGER_COLUMNS = {4, 5, 10}

HEADER_ROW = 9
FIRST_DATA_ROW = 10
METADATA_ROWS = range(1, 8)

THIN = Side(style="thin", color=BORDER_COLOR)
THIN_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
NO_BORDER = Border()
NO_FILL = PatternFill(fill_type=None)
WHITE_FILL = PatternFill(start_color="FFFFFFFF", end_color="FFFFFFFF", fill_type="solid")

INDEX_MARGINS = {"left": 0.7, "right": 0.7, "top": 0.3, "bottom": 0.3, "header": 0.3, "footer": 0.3}
CHECKLIST_MARGINS = {"left": 0.7, "right": 0.7, "top": 0.75, "bottom": 0.75, "header": 0.3, "footer": 0.3}

# Checklist bands from the Section 11 workbook: header row, value row, last column.
CHECKLIST_BANDS = ((2, 3, 11), (5, 6, 8), (8, 9, 7))
CHECKLIST_ROW_HEIGHTS = {2: 45.0, 3: 48.0, 5: 30.0, 6: 30.0, 8: 30.0, 9: 78.0}


@dataclass(frozen=True)
class StyleFinding:
    sheet: str
    cell: str
    message: str

    def __str__(self) -> str:
        where = f"{self.sheet}!{self.cell}" if self.cell else self.sheet
        return f"{where}: {self.message}"


def cm_to_excel_width(cm: float) -> float:
    """Convert a centimetre column width to an Excel character width.

    Uses the OOXML Calibri 11 assumption: 96 DPI and a 7-pixel max digit
    width plus 5 pixels of padding.
    """
    pixels = cm / 2.54 * 96.0
    return (pixels - 5.0) / 7.0


def _font(bold: bool) -> Font:
    return Font(name=FONT_NAME, size=FONT_SIZE, bold=bold, color=FONT_COLOR, italic=False)


def _align(horizontal: str, *, wrap: bool, shrink: bool = False, vertical: str = "top") -> Alignment:
    return Alignment(
        horizontal=horizontal,
        vertical=vertical,
        wrap_text=wrap,
        shrink_to_fit=shrink,
    )


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def detect_kind(ws: Worksheet) -> Optional[str]:
    """Return ``county``, ``blm``, ``checklist``, or None."""
    title = (ws.title or "").lower()
    a2 = _text(ws["A2"].value).lower()
    if "checklist" in title or a2 == "county index":
        return "checklist"
    headers = tuple(_text(ws.cell(HEADER_ROW, col).value) for col in range(1, 11))
    if headers[:9] == COUNTY_HEADERS:
        return "county"
    if headers[:10] == BLM_HEADERS:
        return "blm"
    return None


def last_populated_row(ws: Worksheet, columns: int) -> int:
    last = HEADER_ROW
    for row in range(FIRST_DATA_ROW, (ws.max_row or HEADER_ROW) + 1):
        if any(_text(ws.cell(row, col).value) for col in range(1, columns + 1)):
            last = row
    return last


def _apply_index_print(ws: Worksheet) -> None:
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.scale = 100
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    for name, value in INDEX_MARGINS.items():
        setattr(ws.page_margins, name, value)
    ws.print_title_rows = "1:9"
    ws.page_setup.horizontalCentered = False


def _paint(cell, *, bold: bool, horizontal: str, wrap: bool, border: bool, shrink: bool = False, vertical: str = "top", fill: Optional[PatternFill] = None) -> None:
    cell.font = _font(bold)
    cell.alignment = _align(horizontal, wrap=wrap, shrink=shrink, vertical=vertical)
    cell.border = THIN_BORDER if border else NO_BORDER
    cell.fill = NO_FILL if fill is None else fill


def _apply_number_format(cell, column: int, date_columns: set, integer_columns: set) -> None:
    value = cell.value
    if isinstance(value, (datetime, date)) and column in date_columns:
        cell.number_format = DATE_FORMAT
    elif isinstance(value, (int, float)) and not isinstance(value, bool) and column in integer_columns:
        cell.number_format = INTEGER_FORMAT


def apply_index_style(ws: Worksheet, kind: str) -> int:
    """Style one county or BLM index sheet. Returns the last data row."""
    if kind == "county":
        columns = 9
        widths = COUNTY_WIDTHS_CM
        center = COUNTY_CENTER_COLUMNS
        dates = COUNTY_DATE_COLUMNS
        integers = COUNTY_INTEGER_COLUMNS
    elif kind == "blm":
        columns = 10
        widths = BLM_WIDTHS_CM
        center = BLM_CENTER_COLUMNS
        dates = BLM_DATE_COLUMNS
        integers = BLM_INTEGER_COLUMNS
    else:
        raise ValueError(f"index kind must be county or blm, got {kind!r}")

    for col, cm in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col)].width = cm_to_excel_width(cm)

    for row in range(1, 9):
        ws.row_dimensions[row].height = 15
        for col in range(1, columns + 1):
            bold = row in METADATA_ROWS and col == 1
            _paint(ws.cell(row, col), bold=bold, horizontal="left", wrap=True, border=False)

    ws.row_dimensions[HEADER_ROW].height = 30
    for col in range(1, columns + 1):
        _paint(ws.cell(HEADER_ROW, col), bold=True, horizontal="center", wrap=True, border=True)

    last = last_populated_row(ws, columns)
    for row in range(FIRST_DATA_ROW, last + 1):
        ws.row_dimensions[row].height = None
        for col in range(1, columns + 1):
            centered = col in center
            _paint(
                ws.cell(row, col),
                bold=False,
                horizontal="center" if centered else "left",
                wrap=not centered,
                shrink=centered,
                border=True,
            )
            _apply_number_format(ws.cell(row, col), col, dates, integers)
    _apply_index_print(ws)
    return last


def _checklist_horizontal(row: int, value: object) -> str:
    if row != 9:
        return "center"
    if isinstance(value, (datetime, date)):
        return "center"
    text = _text(value)
    if not text or "\n" in text or len(text) <= 28:
        return "center"
    return "left"


def apply_checklist_style(ws: Worksheet) -> None:
    """Style the three Section 11 checklist bands. Values stay put."""
    for col, width in enumerate(CHECKLIST_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(col)].width = width
    for header_row, value_row, last_col in CHECKLIST_BANDS:
        ws.row_dimensions[header_row].height = CHECKLIST_ROW_HEIGHTS[header_row]
        ws.row_dimensions[value_row].height = CHECKLIST_ROW_HEIGHTS[value_row]
        for col in range(1, last_col + 1):
            header = ws.cell(header_row, col)
            _paint(header, bold=True, horizontal="center", wrap=True, border=True, vertical="center", fill=WHITE_FILL)
            value = ws.cell(value_row, col)
            _paint(
                value,
                bold=False,
                horizontal=_checklist_horizontal(value_row, value.value),
                wrap=True,
                border=True,
                vertical="center",
                fill=WHITE_FILL,
            )
            if isinstance(value.value, (datetime, date)):
                value.number_format = "mm-dd-yy"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.page_setup.scale = 45
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    for name, value in CHECKLIST_MARGINS.items():
        setattr(ws.page_margins, name, value)


def apply_section11_style(ws: Worksheet, kind: Optional[str] = None) -> str:
    """Style one worksheet. Returns the kind that was applied."""
    resolved = kind or detect_kind(ws)
    if resolved is None:
        raise ValueError(f"cannot tell how to style sheet {ws.title!r}; pass kind='county', 'blm', or 'checklist'")
    if resolved == "checklist":
        apply_checklist_style(ws)
    elif resolved in ("county", "blm"):
        apply_index_style(ws, resolved)
    else:
        raise ValueError(f"unknown kind {resolved!r}")
    return resolved


def style_workbook(workbook: Workbook, kinds: Optional[dict] = None) -> List[str]:
    """Style every recognized sheet. ``kinds`` maps a sheet title to a kind."""
    applied: List[str] = []
    overrides = kinds or {}
    for ws in workbook.worksheets:
        kind = overrides.get(ws.title)
        if kind is None and ws.title not in overrides:
            kind = detect_kind(ws)
        if kind is None:
            continue
        apply_section11_style(ws, kind)
        applied.append(ws.title)
    return applied


def _color_is_black(color) -> bool:
    if color is None:
        return False
    rgb = getattr(color, "rgb", None)
    if rgb is None:
        return False
    text = str(rgb).upper()
    return text.endswith("000000") and text not in {"00000000", "0"}


def _border_is_thin_black(cell) -> bool:
    for edge in (cell.border.left, cell.border.right, cell.border.top, cell.border.bottom):
        if edge is None or edge.style != "thin":
            return False
        if not _color_is_black(edge.color):
            return False
    return True


def _border_is_empty(cell) -> bool:
    for edge in (cell.border.left, cell.border.right, cell.border.top, cell.border.bottom):
        if edge is not None and edge.style not in (None,):
            return False
    return True


def _font_ok(cell, *, bold: bool) -> Optional[str]:
    font = cell.font
    if font.name != FONT_NAME or font.size != FONT_SIZE:
        return f"font is {font.name} {font.size}, expected {FONT_NAME} {FONT_SIZE}"
    if bool(font.bold) != bold:
        return f"bold is {bool(font.bold)}, expected {bold}"
    if not _color_is_black(font.color):
        return f"font color is {getattr(font.color, 'rgb', None)}, expected black"
    return None


def _check_cell(findings: List[StyleFinding], ws: Worksheet, row: int, col: int, *, bold: bool, horizontal: str, wrap: bool, border: bool, vertical: str) -> None:
    cell = ws.cell(row, col)
    font_problem = _font_ok(cell, bold=bold)
    if font_problem:
        findings.append(StyleFinding(ws.title, cell.coordinate, font_problem))
    align = cell.alignment
    if (align.horizontal or "general") != horizontal:
        findings.append(StyleFinding(ws.title, cell.coordinate, f"horizontal align is {align.horizontal}, expected {horizontal}"))
    if (align.vertical or "bottom") != vertical:
        findings.append(StyleFinding(ws.title, cell.coordinate, f"vertical align is {align.vertical}, expected {vertical}"))
    if bool(align.wrap_text) != wrap:
        findings.append(StyleFinding(ws.title, cell.coordinate, f"wrap is {bool(align.wrap_text)}, expected {wrap}"))
    if border and not _border_is_thin_black(cell):
        findings.append(StyleFinding(ws.title, cell.coordinate, "missing thin black border"))
    if not border and not _border_is_empty(cell):
        findings.append(StyleFinding(ws.title, cell.coordinate, "unexpected border"))
    fill = cell.fill
    if border and vertical == "center":
        rgb = getattr(fill.fgColor, "rgb", None) if fill is not None else None
        if fill is None or fill.patternType != "solid" or not str(rgb).upper().endswith("FFFFFF"):
            findings.append(StyleFinding(ws.title, cell.coordinate, "checklist fill is not white"))
    elif fill is not None and fill.patternType not in (None, "none"):
        findings.append(StyleFinding(ws.title, cell.coordinate, "index cell has a fill"))


def audit_index_style(ws: Worksheet, kind: str) -> List[StyleFinding]:
    findings: List[StyleFinding] = []
    columns = 9 if kind == "county" else 10
    widths = COUNTY_WIDTHS_CM if kind == "county" else BLM_WIDTHS_CM
    center = COUNTY_CENTER_COLUMNS if kind == "county" else BLM_CENTER_COLUMNS
    for col, cm in enumerate(widths, start=1):
        actual = ws.column_dimensions[get_column_letter(col)].width
        expected = cm_to_excel_width(cm)
        if actual is None or abs(actual - expected) > 0.05:
            findings.append(StyleFinding(ws.title, get_column_letter(col), f"width {actual} != {expected:.4f}"))
    for row in range(1, 9):
        for col in range(1, columns + 1):
            _check_cell(
                findings, ws, row, col,
                bold=row in METADATA_ROWS and col == 1,
                horizontal="left", wrap=True, border=False, vertical="top",
            )
    for col in range(1, columns + 1):
        _check_cell(findings, ws, HEADER_ROW, col, bold=True, horizontal="center", wrap=True, border=True, vertical="top")
    last = last_populated_row(ws, columns)
    for row in range(FIRST_DATA_ROW, last + 1):
        for col in range(1, columns + 1):
            centered = col in center
            _check_cell(
                findings, ws, row, col,
                bold=False,
                horizontal="center" if centered else "left",
                wrap=not centered,
                border=True,
                vertical="top",
            )
    if ws.page_setup.orientation != "landscape":
        findings.append(StyleFinding(ws.title, "", "page is not landscape"))
    if ws.page_setup.fitToWidth != 1:
        findings.append(StyleFinding(ws.title, "", "fit-to-width is not 1"))
    if abs(ws.page_margins.left - 0.7) > 0.01 or abs(ws.page_margins.top - 0.3) > 0.01:
        findings.append(StyleFinding(ws.title, "", "index margins do not match Section 11"))
    titles = (ws.print_title_rows or "").replace("$", "")
    if titles != "1:9":
        findings.append(StyleFinding(ws.title, "", "repeating print titles are not rows 1:9"))
    return findings


def audit_checklist_style(ws: Worksheet) -> List[StyleFinding]:
    findings: List[StyleFinding] = []
    for col, expected in enumerate(CHECKLIST_WIDTHS, start=1):
        actual = ws.column_dimensions[get_column_letter(col)].width
        if actual is None or abs(actual - expected) > 0.05:
            findings.append(StyleFinding(ws.title, get_column_letter(col), f"width {actual} != {expected}"))
    for header_row, value_row, last_col in CHECKLIST_BANDS:
        for col in range(1, last_col + 1):
            _check_cell(findings, ws, header_row, col, bold=True, horizontal="center", wrap=True, border=True, vertical="center")
            value = ws.cell(value_row, col)
            _check_cell(
                findings, ws, value_row, col,
                bold=False,
                horizontal=_checklist_horizontal(value_row, value.value),
                wrap=True, border=True, vertical="center",
            )
    if ws.page_setup.orientation != "landscape":
        findings.append(StyleFinding(ws.title, "", "checklist page is not landscape"))
    if abs(ws.page_margins.left - 0.7) > 0.01 or abs(ws.page_margins.top - 0.75) > 0.01:
        findings.append(StyleFinding(ws.title, "", "checklist margins do not match Section 11"))
    return findings


def audit_section11_style(ws: Worksheet, kind: Optional[str] = None) -> List[StyleFinding]:
    resolved = kind or detect_kind(ws)
    if resolved == "checklist":
        return audit_checklist_style(ws)
    if resolved in ("county", "blm"):
        return audit_index_style(ws, resolved)
    return [StyleFinding(ws.title, "", "sheet is not a county index, BLM index, or checklist")]


def audit_workbook(workbook: Workbook) -> List[StyleFinding]:
    findings: List[StyleFinding] = []
    for ws in workbook.worksheets:
        if detect_kind(ws) is None:
            continue
        findings.extend(audit_section11_style(ws))
    return findings


def _load(path: Path) -> Workbook:
    from openpyxl import load_workbook

    return load_workbook(path)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Apply or audit Section 11 cell style on an index workbook.")
    parser.add_argument("command", choices=("apply", "audit"))
    parser.add_argument("workbook", type=Path)
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--kind", choices=("county", "blm", "checklist", "auto"), default="auto")
    args = parser.parse_args(argv)

    workbook = _load(args.workbook)
    if args.command == "apply":
        if args.output is None:
            parser.error("apply requires an output path")
        if args.kind == "auto":
            styled = style_workbook(workbook)
        else:
            styled = []
            for ws in workbook.worksheets:
                apply_section11_style(ws, args.kind)
                styled.append(ws.title)
        if not styled:
            print("No sheet matched a Section 11 layout.", file=sys.stderr)
            return 2
        args.output.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(args.output)
        findings = audit_workbook(workbook)
        print(f"Styled {', '.join(styled)} -> {args.output}")
        if findings:
            for finding in findings:
                print(finding, file=sys.stderr)
            return 1
        return 0

    findings = []
    for ws in workbook.worksheets:
        kind = None if args.kind == "auto" else args.kind
        if kind is None and detect_kind(ws) is None:
            continue
        findings.extend(audit_section11_style(ws, kind))
    if findings:
        for finding in findings:
            print(finding)
        return 1
    print("Section 11 style matches.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
