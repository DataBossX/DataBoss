"""Format Combine-Harvest abstract indexes to the Overtime package layout.

This module does not fetch source images and does not invent instrument facts.
It applies display rules to an already selected row file.

County columns A:I and BLM columns A:J follow the finished Overtime donors.
Rows 1-7 are metadata, row 8 is blank, row 9 is the header, and entries start
on row 10. Preparation date is 10/19/2026. Instrument dates use m/d/yyyy.
All-digit document numbers are stored as integers. The original spelling,
including leading zeros, stays in the database. BLM File No and Comments stay
present and blank. Page and Part are single integers. An unnumbered part stays
blank.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

EXCEL_EPOCH = datetime(1899, 12, 30)
PREP_DATE = datetime(2026, 10, 19)
DATE_FORMAT = "m/d/yyyy"
FONT_NAME = "Calibri"
FONT_SIZE = 11

# Centimeter widths measured from Overtime section 15 county donor ODS.
COUNTY_WIDTH_CM = [8.36083333333333, 10.5833333333333, 9.68375, 2.19604166666667, 2.778125, 2.91041666666667, 2.460625, 6.50875, 7.381875]
FEDERAL_WIDTH_CM = [8.36083333333333, 10.5833333333333, 9.68375, 2.19604166666667, 1.8, 2.91041666666667, 2.460625, 2.2, 7.381875, 1.6]

THIN = Border(
    left=Side(style="thin", color="000000"),
    right=Side(style="thin", color="000000"),
    top=Side(style="thin", color="000000"),
    bottom=Side(style="thin", color="000000"),
)
HEADER_FILL = PatternFill("solid", fgColor="D9E2F3")
LABEL_FONT = Font(name=FONT_NAME, size=FONT_SIZE, bold=True)
BODY_FONT = Font(name=FONT_NAME, size=FONT_SIZE)
HEADER_FONT = Font(name=FONT_NAME, size=FONT_SIZE, bold=True)
WRAP = Alignment(wrap_text=True, vertical="top", horizontal="left")
CENTER = Alignment(wrap_text=True, vertical="center", horizontal="center")


def excel_width(cm: float) -> float:
    pixels = cm * 96 / 2.54
    return round((pixels - 5) / 7, 2)


def excel_serial_to_date(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not (1 < value < 80000):
        return None
    return EXCEL_EPOCH + timedelta(days=int(value))


def format_date_text(value):
    found = excel_serial_to_date(value)
    if found is None:
        return None
    return f"{found.month}/{found.day}/{found.year}"


def is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def is_literal_unknown(value) -> bool:
    return isinstance(value, str) and value.strip().lower() == "unknown"


def is_qualified_unknown(value) -> bool:
    return isinstance(value, str) and "unknown" in value.lower() and not is_literal_unknown(value)


def substantive_headers(kind: str, headers: list[str]) -> set[str]:
    if kind == "county":
        return {header for header in headers if header != "Comments"}
    return {header for header in headers if header not in {"File No", "Comments"}}


def numeric_document_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return None


def display_value(kind: str, header: str, value):
    if kind != "county" and header in {"File No", "Comments"}:
        return None
    if header in {"Date of Doc", "Rec Date"}:
        found = excel_serial_to_date(value)
        if found is not None:
            return found
        return None if is_blank(value) else value
    if header == "Doc No":
        number = numeric_document_number(value)
        if number is not None:
            return number
    if header in {"Page", "Part"}:
        if isinstance(value, bool) or is_blank(value):
            return None
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return value
    if is_blank(value):
        return None
    return value


def sort_key(kind: str, headers: list[str], row: dict, order: int):
    if kind == "county":
        return (0, row.get("new_row") or row.get("original_row") or order, order)
    values = row["values"]
    part = values[headers.index("Part")] if "Part" in headers else None
    page = values[headers.index("Page")] if "Page" in headers else None
    part_key = part if isinstance(part, (int, float)) and not isinstance(part, bool) else 10**9
    page_key = page if isinstance(page, (int, float)) and not isinstance(page, bool) else 10**9
    return (1, part_key, page_key, order)


def metadata_map(workbook: dict) -> dict[str, str]:
    found = {}
    for row in workbook.get("metadata") or []:
        if row and row[0]:
            found[str(row[0]).rstrip(":")] = "" if len(row) < 2 or row[1] is None else str(row[1])
    return found


def client_metadata(workbook: dict) -> list[tuple[str, object]]:
    raw = metadata_map(workbook)
    posted = raw.get("Date Posted Thru")
    if posted in {None, "", "Unknown"}:
        posted_value = "Unknown"
    else:
        posted_value = posted
    return [
        ("County:", raw.get("County") or "Johnson"),
        ("Lands:", raw.get("Lands") or ""),
        ("Date:", PREP_DATE),
        ("Starting Date:", None),
        ("Date Posted Thru:", posted_value),
        ("Indexed By:", raw.get("Indexed By") or "Ryan Gille"),
        ("Project:", raw.get("Project") or "Combine-Harvest CH185443 / AFE210275"),
    ]


def line_count(value, width_chars: float = 40) -> int:
    if value is None or isinstance(value, datetime):
        return 1
    width = max(8, int(width_chars))
    lines = 0
    for part in str(value).split("\n"):
        lines += max(1, (len(part) + width - 1) // width)
    return lines


def ordered_rows(workbook: dict):
    kind = workbook["kind"]
    headers = workbook["headers"]
    return sorted(
        enumerate(workbook["rows"]),
        key=lambda item: sort_key(kind, headers, item[1], item[0]),
    )


def write_xlsx(path: Path, workbook: dict) -> None:
    headers = workbook["headers"]
    kind = workbook["kind"]
    widths = COUNTY_WIDTH_CM if kind == "county" else FEDERAL_WIDTH_CM
    book = Workbook()
    sheet = book.active
    sheet.title = "Index"
    sheet.sheet_format.defaultRowHeight = 15
    sheet.sheet_view.showGridLines = False
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_TABLOID
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.page_setup.horizontalCentered = True
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_margins = PageMargins(left=0.4, right=0.4, top=0.45, bottom=0.45, header=0.2, footer=0.2)
    sheet.oddHeader.left.text = metadata_map(workbook).get("Lands", "")
    sheet.oddFooter.left.text = "Prepared 10/19/2026  |  QUALIFIED REVIEW  |  UNSIGNED"
    sheet.oddFooter.right.text = "Page &P of &N"
    sheet.print_title_rows = "9:9"
    sheet.sheet_properties.tabColor = "1F4E79"
    for index, (label, value) in enumerate(client_metadata(workbook), start=1):
        sheet.cell(index, 1, label).font = LABEL_FONT
        cell = sheet.cell(index, 2, value)
        cell.font = BODY_FONT
        cell.alignment = WRAP
        if isinstance(value, datetime):
            cell.number_format = DATE_FORMAT
    sheet.row_dimensions[8].height = 8
    for column, header in enumerate(headers, start=1):
        cell = sheet.cell(9, column, header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = THIN
        width_cm = widths[column - 1] if column - 1 < len(widths) else 4
        sheet.column_dimensions[get_column_letter(column)].width = excel_width(width_cm)
    sheet.row_dimensions[9].height = 22
    sheet.auto_filter.ref = f"A9:{get_column_letter(len(headers))}9"
    sheet.freeze_panes = "A10"
    for offset, (_, row) in enumerate(ordered_rows(workbook)):
        excel_row = 10 + offset
        height = 20
        for column, header in enumerate(headers, start=1):
            raw = row["values"][column - 1] if column - 1 < len(row["values"]) else None
            value = display_value(kind, header, raw)
            cell = sheet.cell(excel_row, column, value)
            cell.font = BODY_FONT
            cell.alignment = CENTER if header in {"Page", "Part", "Doc No", "Book-Page", "Date of Doc", "Rec Date"} else WRAP
            cell.border = THIN
            if isinstance(value, datetime):
                cell.number_format = DATE_FORMAT
            if header in {"Page", "Part", "Doc No"} and isinstance(value, int):
                cell.number_format = "0"
            width_chars = excel_width(widths[column - 1]) if column - 1 < len(widths) else 20
            height = max(height, 16 * line_count(value, width_chars) + 8)
        sheet.row_dimensions[excel_row].height = min(height, 409)
    last_row = 9 + len(workbook["rows"])
    sheet.print_area = f"A1:{get_column_letter(len(headers))}{max(last_row, 9)}"
    sheet.sheet_view.view = "pageBreakPreview"
    sheet.sheet_view.zoomScale = 100
    path.parent.mkdir(parents=True, exist_ok=True)
    book.save(path)


def _ods_cell(value, style: str) -> str:
    style_attr = f' table:style-name="{style}"'
    if value is None or value == "":
        return f"<table:table-cell{style_attr}/>"
    if isinstance(value, datetime):
        text = f"{value.month}/{value.day}/{value.year}"
        return (
            f'<table:table-cell{style_attr} office:value-type="date" office:date-value="{value.strftime("%Y-%m-%d")}">'
            f"<text:p>{escape(text)}</text:p></table:table-cell>"
        )
    if isinstance(value, int) and not isinstance(value, bool):
        return (
            f'<table:table-cell{style_attr} office:value-type="float" office:value="{value}">'
            f"<text:p>{value}</text:p></table:table-cell>"
        )
    paragraphs = "".join(f"<text:p>{escape(line)}</text:p>" for line in str(value).split("\n"))
    return f'<table:table-cell{style_attr} office:value-type="string">{paragraphs}</table:table-cell>'


def write_ods(path: Path, workbook: dict) -> None:
    headers = workbook["headers"]
    kind = workbook["kind"]
    widths = COUNTY_WIDTH_CM if kind == "county" else FEDERAL_WIDTH_CM
    columns = []
    for index, width in enumerate(widths, start=1):
        columns.append(
            f'<table:table-column table:style-name="co{index}"/>'
        )
    rows_xml = []
    for label, value in client_metadata(workbook):
        rows_xml.append(
            '<table:table-row table:style-name="roMeta">'
            + _ods_cell(label, "ceLabel")
            + _ods_cell(value, "ceMeta")
            + "</table:table-row>"
        )
    rows_xml.append('<table:table-row table:style-name="roBlank"/>')
    rows_xml.append(
        '<table:table-row table:style-name="roHead">'
        + "".join(_ods_cell(header, "ceHead") for header in headers)
        + "</table:table-row>"
    )
    for _, row in ordered_rows(workbook):
        cells = []
        lines = 1
        for column, header in enumerate(headers):
            raw = row["values"][column] if column < len(row["values"]) else None
            value = display_value(kind, header, raw)
            lines = max(lines, line_count(value))
            style = "ceCenter" if header in {"Page", "Part", "Doc No", "Book-Page", "Date of Doc", "Rec Date"} else "ceBody"
            if isinstance(value, datetime):
                style = "ceDate"
            cells.append(_ods_cell(value, style))
        row_style = "roTall" if lines > 2 else "roBody"
        rows_xml.append(f'<table:table-row table:style-name="{row_style}">' + "".join(cells) + "</table:table-row>")
    col_styles = []
    for index, width in enumerate(widths, start=1):
        col_styles.append(
            f'<style:style style:name="co{index}" style:family="table-column">'
            f'<style:table-column-properties style:column-width="{width}cm"/>'
            "</style:style>"
        )
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.3">
 <office:font-face-decls>
  <style:font-face style:name="Calibri" svg:font-family="Calibri" xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"/>
 </office:font-face-decls>
 <office:automatic-styles>
  {''.join(col_styles)}
  <style:style style:name="ceLabel" style:family="table-cell">
   <style:text-properties style:font-name="Calibri" fo:font-size="11pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="ceMeta" style:family="table-cell">
   <style:table-cell-properties style:vertical-align="top" fo:wrap-option="wrap"/>
   <style:text-properties style:font-name="Calibri" fo:font-size="11pt"/>
  </style:style>
  <style:style style:name="ceHead" style:family="table-cell">
   <style:table-cell-properties fo:border="0.5pt solid #000000" style:vertical-align="middle" fo:wrap-option="wrap" fo:background-color="#D9E2F3"/>
   <style:paragraph-properties fo:text-align="center"/>
   <style:text-properties style:font-name="Calibri" fo:font-size="11pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="ceBody" style:family="table-cell">
   <style:table-cell-properties fo:border="0.5pt solid #000000" style:vertical-align="top" fo:wrap-option="wrap"/>
   <style:paragraph-properties fo:text-align="start"/>
   <style:text-properties style:font-name="Calibri" fo:font-size="11pt"/>
  </style:style>
  <style:style style:name="ceCenter" style:family="table-cell">
   <style:table-cell-properties fo:border="0.5pt solid #000000" style:vertical-align="top" fo:wrap-option="wrap"/>
   <style:paragraph-properties fo:text-align="center"/>
   <style:text-properties style:font-name="Calibri" fo:font-size="11pt"/>
  </style:style>
  <style:style style:name="ceDate" style:family="table-cell" style:data-style-name="NDate">
   <style:table-cell-properties fo:border="0.5pt solid #000000" style:vertical-align="top" fo:wrap-option="wrap"/>
   <style:paragraph-properties fo:text-align="center"/>
   <style:text-properties style:font-name="Calibri" fo:font-size="11pt"/>
  </style:style>
  <style:style style:name="roMeta" style:family="table-row"><style:table-row-properties style:row-height="0.55cm" style:use-optimal-row-height="true"/></style:style>
  <style:style style:name="roBlank" style:family="table-row"><style:table-row-properties style:row-height="0.3cm"/></style:style>
  <style:style style:name="roHead" style:family="table-row"><style:table-row-properties style:row-height="0.7cm"/></style:style>
  <style:style style:name="roBody" style:family="table-row"><style:table-row-properties style:row-height="0.7cm" style:use-optimal-row-height="true"/></style:style>
  <style:style style:name="roTall" style:family="table-row"><style:table-row-properties style:row-height="1.6cm" style:use-optimal-row-height="true"/></style:style>
  <number:date-style style:name="NDate" xmlns:number="urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0">
   <number:month number:style="short"/><number:text>/</number:text><number:day number:style="short"/><number:text>/</number:text><number:year number:style="long"/>
  </number:date-style>
 </office:automatic-styles>
 <office:body><office:spreadsheet>
  <table:table table:name="Index" table:style-name="ta1">{''.join(columns)}{''.join(rows_xml)}</table:table>
 </office:spreadsheet></office:body>
</office:document-content>"""
    styles = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.3">
 <office:styles>
  <style:default-style style:family="table-cell">
   <style:text-properties style:font-name="Calibri" fo:font-size="11pt"/>
  </style:default-style>
  <style:style style:name="ta1" style:family="table" style:master-page-name="mp1"/>
 </office:styles>
 <office:automatic-styles>
  <style:page-layout style:name="pm1">
   <style:page-layout-properties fo:page-width="17in" fo:page-height="11in" style:print-orientation="landscape"
    fo:margin-top="0.4in" fo:margin-bottom="0.4in" fo:margin-left="0.4in" fo:margin-right="0.4in"
    style:scale-to-X="1" style:scale-to-Y="0"/>
  </style:page-layout>
 </office:automatic-styles>
 <office:master-styles>
  <style:master-page style:name="mp1" style:page-layout-name="pm1"/>
 </office:master-styles>
</office:document-styles>"""
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
 <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/>
 <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
 <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
 <manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""
    meta = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
 office:version="1.3"><office:meta>
 <dc:title>Qualified review index</dc:title>
 <meta:generator>CH185443 candidate formatter 2026-10-19</meta:generator>
</office:meta></office:document-meta>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet", compress_type=ZIP_STORED)
        archive.writestr("content.xml", content, compress_type=ZIP_DEFLATED)
        archive.writestr("styles.xml", styles, compress_type=ZIP_DEFLATED)
        archive.writestr("meta.xml", meta, compress_type=ZIP_DEFLATED)
        archive.writestr("META-INF/manifest.xml", manifest, compress_type=ZIP_DEFLATED)


def audit_workbook(workbook: dict) -> dict:
    headers = workbook["headers"]
    kind = workbook["kind"]
    substantive = substantive_headers(kind, headers)
    blanks = Counter()
    unknowns = Counter()
    qualified = Counter()
    parts = []
    missing_images = 0
    for row in workbook["rows"]:
        for header in headers:
            value = row["values"][headers.index(header)]
            shown = display_value(kind, header, value)
            if header in substantive and is_blank(shown):
                blanks[header] += 1
            if header in substantive and is_literal_unknown(value):
                unknowns[header] += 1
            if header in substantive and is_qualified_unknown(value):
                qualified[header] += 1
        if kind == "county" and "Comments" in headers:
            comment = row["values"][headers.index("Comments")]
            if comment == "missing image":
                missing_images += 1
        if kind != "county" and "Part" in headers:
            part = row["values"][headers.index("Part")]
            if isinstance(part, (int, float)) and not isinstance(part, bool):
                parts.append(int(part))
    return {
        "section": workbook["section"],
        "kind": kind,
        "file": workbook["file"],
        "documents": len(workbook["rows"]),
        "parts": sorted(set(parts)),
        "part_count": len(set(parts)),
        "blank_cells": sum(blanks.values()),
        "blank_by_column": dict(blanks),
        "unknown_cells": sum(unknowns.values()),
        "unknown_by_column": dict(unknowns),
        "qualified_unknown_cells": sum(qualified.values()),
        "missing_images": missing_images,
    }


def build_database(path: Path, master: dict, audits: list[dict]) -> None:
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE source_archives (
            archive_id TEXT PRIMARY KEY,
            role TEXT,
            drive_id TEXT,
            sha256 TEXT,
            byte_note TEXT,
            adoption TEXT
        );
        CREATE TABLE source_files (
            file_key TEXT PRIMARY KEY,
            archive_id TEXT,
            role TEXT,
            sha256 TEXT,
            note TEXT
        );
        CREATE TABLE hash_aliases (
            alias_id INTEGER PRIMARY KEY,
            sha256 TEXT,
            alias TEXT,
            note TEXT
        );
        CREATE TABLE physical_pages (
            case_id TEXT,
            part_label TEXT,
            physical_pages INTEGER,
            count_basis TEXT
        );
        CREATE TABLE blm_cases (
            case_id TEXT PRIMARY KEY,
            pages INTEGER,
            content_status TEXT,
            hold TEXT
        );
        CREATE TABLE blm_parts (
            case_id TEXT,
            part_label TEXT,
            physical_pages INTEGER,
            content_occurrences TEXT,
            count_basis TEXT
        );
        CREATE TABLE document_boundaries (
            boundary_id TEXT PRIMARY KEY,
            case_id TEXT,
            part_label TEXT,
            status TEXT,
            note TEXT
        );
        CREATE TABLE county_index_appearances (
            section INTEGER PRIMARY KEY,
            status TEXT,
            note TEXT
        );
        CREATE TABLE section_applicability (
            section INTEGER PRIMARY KEY,
            township TEXT,
            county_rows INTEGER,
            federal_rows INTEGER
        );
        CREATE TABLE workbook_rows (
            row_id TEXT PRIMARY KEY,
            section INTEGER,
            kind TEXT,
            file TEXT,
            document_type TEXT,
            grantor TEXT,
            grantee TEXT,
            doc_no_display TEXT,
            doc_no_source_text TEXT,
            book_page TEXT,
            date_of_doc TEXT,
            rec_date TEXT,
            legal TEXT,
            comments TEXT,
            page TEXT,
            part TEXT,
            blank_substantive INTEGER,
            unknown_substantive INTEGER,
            qualified_unknown INTEGER,
            missing_image INTEGER
        );
        CREATE TABLE evidence_references (
            ref_id INTEGER PRIMARY KEY,
            subject TEXT,
            basis TEXT,
            drive_id TEXT
        );
        CREATE TABLE missing_sources (
            hold_id TEXT PRIMARY KEY,
            section TEXT,
            item TEXT,
            status TEXT
        );
        CREATE TABLE ai_receipts (
            receipt_id TEXT PRIMARY KEY,
            actor TEXT,
            action TEXT,
            result TEXT
        );
        CREATE TABLE package_versions (
            version_id TEXT PRIMARY KEY,
            status TEXT,
            parent_sha256 TEXT,
            note TEXT
        );
        CREATE TABLE acceptance_gates (
            gate TEXT PRIMARY KEY,
            cycle_no INTEGER,
            status TEXT,
            evidence TEXT
        );
        CREATE TABLE section_summary (
            section INTEGER PRIMARY KEY,
            county_rows INTEGER,
            federal_rows INTEGER,
            federal_workbooks INTEGER,
            blank_cells INTEGER,
            unknown_cells INTEGER,
            qualified_unknown_cells INTEGER,
            unresolved_evidence_cells INTEGER
        );
        CREATE TABLE blm_files (
            section INTEGER,
            file TEXT,
            documents INTEGER,
            part_count INTEGER,
            parts TEXT,
            blank_cells INTEGER,
            unknown_cells INTEGER
        );
        CREATE TABLE index_rows (
            section INTEGER,
            kind TEXT,
            file TEXT,
            row_id TEXT,
            document_type TEXT,
            grantor TEXT,
            grantee TEXT,
            page TEXT,
            part TEXT,
            legal TEXT,
            blank_substantive INTEGER,
            unknown_substantive INTEGER
        );
        """
    )
    parent_sha = master.get("parent_sha256") or ""
    parent_id = master.get("parent_drive_id") or ""
    connection.execute(
        "INSERT INTO source_archives VALUES (?, ?, ?, ?, ?, ?)",
        (
            "selected-parent-1141",
            "source-corrected full successor used as the row source for this candidate",
            parent_id,
            parent_sha,
            "46,494,932 bytes and 565 members as recorded on the 10/19/2026 master notes. This session verified the row JSON, not the ZIP bytes.",
            "NOT ADOPTED over R41",
        ),
    )
    connection.execute(
        "INSERT INTO package_versions VALUES (?, ?, ?, ?)",
        (
            "candidate-20261019-cursor",
            "QUALIFIED / UNSIGNED / HOLD",
            parent_sha,
            "Formatted from the sealed 1,141-row JSON. Does not replace R41 or R45.",
        ),
    )
    for item in master.get("summary") or []:
        connection.execute(
            "INSERT INTO section_summary VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item["section"],
                item["county_rows"],
                item["federal_rows"],
                item["federal_workbooks"],
                item["substantive_display_blanks"],
                item["substantive_display_unknown"],
                item["substantive_display_qualified_unknown"],
                item["unresolved_evidence_cells"],
            ),
        )
        connection.execute(
            "INSERT INTO section_applicability VALUES (?, ?, ?, ?)",
            (item["section"], "", item["county_rows"], item["federal_rows"]),
        )
    for audit in audits:
        if audit["kind"] == "county":
            continue
        connection.execute(
            "INSERT INTO blm_files VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                audit["section"],
                audit["file"],
                audit["documents"],
                audit["part_count"],
                ", ".join(str(part) for part in audit["parts"]),
                audit["blank_cells"],
                audit["unknown_cells"],
            ),
        )
    for workbook in master["workbooks"]:
        headers = workbook["headers"]
        kind = workbook["kind"]
        substantive = substantive_headers(kind, headers)

        def col(name, values):
            if name not in headers:
                return ""
            value = values[headers.index(name)]
            shown = display_value(kind, name, value)
            if shown is None:
                return ""
            if isinstance(shown, datetime):
                return format_date_text(value) or ""
            return str(shown)

        for row in workbook["rows"]:
            values = row["values"]
            blanks = 0
            unknowns = 0
            qualified = 0
            for header in headers:
                raw = values[headers.index(header)]
                shown = display_value(kind, header, raw)
                if header in substantive and is_blank(shown):
                    blanks += 1
                if header in substantive and is_literal_unknown(raw):
                    unknowns += 1
                if header in substantive and is_qualified_unknown(raw):
                    qualified += 1
            source_doc = ""
            if "Doc No" in headers:
                raw_doc = values[headers.index("Doc No")]
                source_doc = "" if raw_doc is None else str(raw_doc)
            comment = col("Comments", values) if kind == "county" else ""
            connection.execute(
                """
                INSERT INTO workbook_rows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("row_id") or "",
                    workbook["section"],
                    kind,
                    workbook["file"],
                    col("Document Type", values),
                    col("Grantor", values),
                    col("Grantee", values),
                    col("Doc No", values),
                    source_doc,
                    col("Book-Page", values),
                    col("Date of Doc", values),
                    col("Rec Date", values),
                    col("Legal Description", values),
                    comment,
                    col("Page", values),
                    col("Part", values),
                    blanks,
                    unknowns,
                    qualified,
                    1 if comment == "missing image" else 0,
                ),
            )
            connection.execute(
                "INSERT INTO index_rows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    workbook["section"],
                    kind,
                    workbook["file"],
                    row.get("row_id") or "",
                    col("Document Type", values),
                    col("Grantor", values),
                    col("Grantee", values),
                    col("Page", values),
                    col("Part", values),
                    col("Legal Description", values),
                    blanks,
                    unknowns,
                ),
            )
    connection.commit()
    connection.close()


def load_master(path: Path) -> dict:
    import json

    return json.loads(path.read_text())
