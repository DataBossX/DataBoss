"""Shared workbook reading for PEACHES.

ODS is read with the standard library only (zipfile + ElementTree) with
repeat expansion done by descendant iteration: ODS rows may be wrapped in
table:table-rows groups and carry table:number-rows-repeated /
table:number-columns-repeated attributes, so direct-children counting
undercounts. XLSX is read with openpyxl.

A "grid" is a list of rows; each row is a list of display strings.
"""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
}


def q(ns: str, tag: str) -> str:
    return "{%s}%s" % (NS[ns], tag)


COUNTY_HEADERS = [
    "Document Type", "Grantor", "Grantee", "Doc No", "Book-Page",
    "Date of Doc", "Rec Date", "Legal Description", "Comments",
]
FEDERAL_HEADERS = [
    "Document Type", "Grantor", "Grantee", "File No", "Page",
    "Date of Doc", "Rec Date", "Comments", "Legal Description", "Part",
]

MAX_ROWS = 20000
MAX_COLS = 64
EMPTY_ROW_REPEAT_CAP = 200


def _node_text(el) -> str:
    """Recursively extract text, honouring text:s / text:tab / line-break."""
    parts = []
    if el.text:
        parts.append(el.text)
    for child in el:
        tag = child.tag
        if tag == q("text", "s"):
            try:
                n = int(child.get(q("text", "c"), "1"))
            except ValueError:
                n = 1
            parts.append(" " * n)
        elif tag == q("text", "tab"):
            parts.append("\t")
        elif tag == q("text", "line-break"):
            parts.append("\n")
        else:
            parts.append(_node_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _cell_text(cell) -> str:
    paras = []
    for p in cell.iter(q("text", "p")):
        paras.append(_node_text(p))
    text = "\n".join(paras).strip()
    if text:
        return text
    date_value = cell.get(q("office", "date-value"))
    if date_value:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", date_value)
        if m:
            return "%d/%d/%d" % (int(m.group(2)), int(m.group(3)), int(m.group(1)))
        return date_value
    value = cell.get(q("office", "value"))
    if value:
        try:
            f = float(value)
            return str(int(f)) if f == int(f) else value
        except ValueError:
            return value
    return ""


def _expand_table(table_el):
    grid = []
    for row_el in table_el.iter(q("table", "table-row")):
        cells = []
        for child in list(row_el):
            if child.tag not in (q("table", "table-cell"), q("table", "covered-table-cell")):
                continue
            try:
                crep = int(child.get(q("table", "number-columns-repeated"), "1"))
            except ValueError:
                crep = 1
            crep = max(1, min(crep, MAX_COLS))
            cells.extend([_cell_text(child)] * crep)
            if len(cells) >= MAX_COLS:
                cells = cells[:MAX_COLS]
                break
        try:
            rrep = int(row_el.get(q("table", "number-rows-repeated"), "1"))
        except ValueError:
            rrep = 1
        rrep = max(1, rrep)
        if not any(c.strip() for c in cells) and rrep > EMPTY_ROW_REPEAT_CAP:
            rrep = EMPTY_ROW_REPEAT_CAP
        for _ in range(rrep):
            grid.append(list(cells))
            if len(grid) >= MAX_ROWS:
                return grid
    return grid


def read_ods_sheets(path):
    """Return [(sheet_name, grid), ...] for an ODS file."""
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if "content.xml" not in names:
            raise ValueError("ODS missing content.xml: %s" % path)
        root = ET.fromstring(zf.read("content.xml"))
    sheets = []
    spreadsheet = root.find(".//" + q("office", "spreadsheet"))
    if spreadsheet is None:
        return sheets
    for table_el in spreadsheet.iter(q("table", "table")):
        # Only top-level tables: iter() also descends, but CH workbooks do not
        # nest tables; guard by skipping tables whose ancestor is a table.
        name = table_el.get(q("table", "name"), "")
        sheets.append((name, _expand_table(table_el)))
    return sheets


def _fmt_xlsx_value(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return "%d/%d/%d" % (v.month, v.day, v.year)
    if isinstance(v, date):
        return "%d/%d/%d" % (v.month, v.day, v.year)
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip()


def read_xlsx_sheets(path):
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheets = []
    try:
        for ws in wb.worksheets:
            grid = []
            for row in ws.iter_rows(values_only=True):
                grid.append([_fmt_xlsx_value(v) for v in row][:MAX_COLS])
                if len(grid) >= MAX_ROWS:
                    break
            sheets.append((ws.title, grid))
    finally:
        wb.close()
    return sheets


def read_sheets(path):
    lower = str(path).lower()
    if lower.endswith(".ods"):
        return read_ods_sheets(path)
    if lower.endswith(".xlsx"):
        return read_xlsx_sheets(path)
    raise ValueError("unsupported workbook type: %s" % path)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def header_score(grid):
    """Best schema match count for the grid's row 9 (index 8)."""
    if len(grid) < 9:
        return 0
    row9 = [_norm(c) for c in grid[8]]
    best = 0
    for schema in (COUNTY_HEADERS, FEDERAL_HEADERS):
        score = sum(1 for i, h in enumerate(schema)
                    if i < len(row9) and row9[i] == _norm(h))
        best = max(best, score)
    return best


def choose_sheet(sheets):
    """Pick the index sheet: best row-9 schema score, then most rows."""
    best = None
    best_key = None
    for name, grid in sheets:
        key = (header_score(grid), len(grid))
        if best_key is None or key > best_key:
            best_key = key
            best = (name, grid)
    return best if best else ("", [])


def read_index_sheet(path):
    """Return (sheet_name, grid) for the workbook's index sheet."""
    return choose_sheet(read_sheets(path))
