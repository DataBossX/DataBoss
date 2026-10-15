#!/usr/bin/env python3
"""Finish Combine-Harvest abstract packages in the completed Overtime layout.

Source facts are copied from the current client packages. A blank fact cell in
columns A-H of an index data row is written as Unknown. No party, date, book,
page, or legal description is invented. Comments stay as they were. Letters
remain unsigned.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.shared import Inches, Pt, RGBColor
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
IN_DIR = Path("/tmp/ch/in")
OUT_DIR = ROOT / "deliverables"
PREPARED = datetime(2026, 10, 15)
PREPARED_TEXT = "10/15/2026"
CLIENT = "Anschutz Exploration Corporation"
PROJECT = "Abstract 210275 Combine-Harvest-Winnow"
LANDMAN = "Ryan Gille"
ADDRESS = [
    "Gille Energy, LLC, Agent for",
    "Penterra Services, LLC",
    "15314 N. May Avenue",
    "Edmond, OK 73013",
]

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "calcext": "urn:org:documentfoundation:names:experimental:calc:xmlns:calcext:1.0",
}
OFFICE = "{%s}" % NS["office"]
TABLE = "{%s}" % NS["table"]
TEXT = "{%s}" % NS["text"]
CALCEXT = "{%s}" % NS["calcext"]

THIN = Border(
    left=Side(style="thin", color="BFBFBF"),
    right=Side(style="thin", color="BFBFBF"),
    top=Side(style="thin", color="BFBFBF"),
    bottom=Side(style="thin", color="BFBFBF"),
)
FONT = Font(name="Calibri", size=11, color="000000")
FONT_BOLD = Font(name="Calibri", size=11, bold=True, color="000000")
WRAP = Alignment(wrap_text=True, vertical="center")

BLOCK1 = [
    "County Index",
    "County Documents",
    "Plat",
    "STR online search",
    "Compare index to Uploads",
    "BLM File",
    "SRP",
    "State File",
    "Lease Report if applicable",
    "Reviewed SRP vs BLM file or State file",
    "Certification Letter",
]
BLOCK2 = [
    "Abstract Excel Sheet",
    "County",
    "Lands Covered",
    "Date completed",
    "Starting Date",
    "Date Certified/Verified",
    "Landman Name",
    "Project/Prospect",
]
BLOCK3 = [
    "Certification Letter",
    "Client",
    "STR & County",
    "Contents for County Records",
    "Contents for BLM or State Records",
    "SRP Info",
    "Completed and Certified Date",
]

PACKAGES = [
    {"key": "06", "section": 6, "township": "47N", "range": "76W", "kind": "ods", "zip": "s6.zip"},
    {"key": "07", "section": 7, "township": "47N", "range": "76W", "kind": "ods", "zip": "s7.zip"},
    {"key": "13", "section": 13, "township": "47N", "range": "77W", "kind": "ods", "zip": "s13.zip"},
    {"key": "18", "section": 18, "township": "47N", "range": "76W", "kind": "ods", "zip": "s18.zip"},
    {"key": "19", "section": 19, "township": "47N", "range": "76W", "kind": "xlsx", "zip": "s19.zip", "partial": True},
    {"key": "24", "section": 24, "township": "47N", "range": "77W", "kind": "ods", "zip": "s24.zip"},
    {"key": "30", "section": 30, "township": "47N", "range": "76W", "kind": "xlsx", "zip": "s30.zip", "partial": True},
    {"key": "31", "section": 31, "township": "47N", "range": "76W", "kind": "xlsx", "zip": "s31.zip", "partial": True},
]


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def cell_text(cell) -> str:
    parts: list[str] = []
    for node in cell.iter():
        if local(node.tag) == "p":
            if node.text:
                parts.append(node.text)
            for child in node:
                if child.text:
                    parts.append(child.text)
                if child.tail:
                    parts.append(child.tail)
            if node.tail:
                parts.append(node.tail)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def explicit_cells(row):
    found = []
    for cell in row:
        if local(cell.tag) != "table-cell":
            continue
        repeated = int(cell.get(TABLE + "number-columns-repeated") or "1")
        if repeated > 30:
            break
        found.append(cell)
    return found


def fact_values(row, fact_count: int) -> list[str]:
    values: list[str] = []
    for cell in row:
        if local(cell.tag) != "table-cell":
            continue
        repeated = int(cell.get(TABLE + "number-columns-repeated") or "1")
        text = cell_text(cell)
        take = min(repeated, fact_count - len(values))
        values.extend([text] * take)
        if len(values) >= fact_count:
            break
    while len(values) < fact_count:
        values.append("")
    return values


def fill_fact_row(row, fact_count: int) -> int:
    """Write Unknown into blank fact columns, splitting a trailing repeated cell when needed."""
    filled = 0
    covered = 0
    for cell in list(row):
        if local(cell.tag) != "table-cell" or covered >= fact_count:
            continue
        repeated = int(cell.get(TABLE + "number-columns-repeated") or "1")
        blank = is_blank(cell)
        if covered + repeated <= fact_count:
            if blank:
                if repeated == 1:
                    write_unknown(cell)
                    filled += 1
                else:
                    cell.set(TABLE + "number-columns-repeated", "1")
                    write_unknown(cell)
                    filled += 1
                    for _ in range(repeated - 1):
                        clone = etree.Element(cell.tag, cell.attrib)
                        for child in cell:
                            clone.append(etree.fromstring(etree.tostring(child)))
                        cell.addnext(clone)
                        cell = clone
                        filled += 1
            covered += repeated
            continue
        need = fact_count - covered
        rest = repeated - need
        if blank and need:
            cell.set(TABLE + "number-columns-repeated", "1")
            write_unknown(cell)
            filled += 1
            previous = cell
            for _ in range(need - 1):
                clone = etree.Element(cell.tag, cell.attrib)
                for child in cell:
                    clone.append(etree.fromstring(etree.tostring(child)))
                previous.addnext(clone)
                previous = clone
                filled += 1
            if rest > 0:
                tail = etree.Element(TABLE + "table-cell")
                if rest > 1:
                    tail.set(TABLE + "number-columns-repeated", str(rest))
                previous.addnext(tail)
        covered = fact_count
    return filled


def is_blank(cell) -> bool:
    if cell.get(OFFICE + "value") or cell.get(OFFICE + "date-value") or cell.get(OFFICE + "value-type"):
        text = cell_text(cell)
        if text:
            return False
        if cell.get(OFFICE + "value") or cell.get(OFFICE + "date-value"):
            return False
    return cell_text(cell) == ""


def write_unknown(cell) -> None:
    cell.set(OFFICE + "value-type", "string")
    cell.set(CALCEXT + "value-type", "string")
    for attr in (OFFICE + "value", OFFICE + "date-value", OFFICE + "boolean-value"):
        if attr in cell.attrib:
            del cell.attrib[attr]
    for child in list(cell):
        if local(child.tag) == "p":
            cell.remove(child)
    paragraph = etree.SubElement(cell, TEXT + "p")
    paragraph.text = "Unknown"


def set_text(cell, value: str) -> None:
    cell.set(OFFICE + "value-type", "string")
    cell.set(CALCEXT + "value-type", "string")
    for attr in (OFFICE + "value", OFFICE + "date-value"):
        if attr in cell.attrib:
            del cell.attrib[attr]
    for child in list(cell):
        if local(child.tag) == "p":
            cell.remove(child)
    paragraph = etree.SubElement(cell, TEXT + "p")
    paragraph.text = value


def header_labels(table) -> list[str]:
    for group in table:
        if local(group.tag) != "table-header-rows":
            continue
        for row in group:
            if local(row.tag) == "table-row":
                return [cell_text(cell) for cell in explicit_cells(row)]
    return []


def body_rows(table):
    return [row for row in table if local(row.tag) == "table-row"]


def finish_ods(data: bytes, fills: list[dict], file_name: str) -> tuple[bytes, dict]:
    root = etree.fromstring(data)
    stats = {"rows": 0, "unknown_before": 0, "filled": 0, "posted_thru": "", "lands": ""}
    for table in root.findall(".//table:table", NS):
        labels = header_labels(table)
        if not labels or labels[0] != "Document Type":
            continue
        fact_count = min(8, len(labels))
        rows = body_rows(table)
        for index, row in enumerate(rows, start=1):
            cells = explicit_cells(row)
            if index <= 7 and len(cells) >= 2:
                label = cell_text(cells[0]).rstrip(":")
                if label == "Date":
                    set_text(cells[1], PREPARED_TEXT)
                elif label == "Date Posted Thru":
                    stats["posted_thru"] = cell_text(cells[1])
                elif label == "Lands":
                    stats["lands"] = cell_text(cells[1])
            if index < 9 or not cells:
                continue
            values = fact_values(row, fact_count)
            if not any(values):
                continue
            stats["rows"] += 1
            newly = fill_fact_row(row, fact_count)
            stats["filled"] += newly
            for offset, current in enumerate(values):
                if current.upper() == "UNKNOWN":
                    stats["unknown_before"] += 1
                elif current == "":
                    fills.append(
                        {
                            "file": file_name,
                            "sheet": table.get(TABLE + "name") or "Index",
                            "row": index + 1,
                            "column": "ABCDEFGH"[offset],
                            "field": labels[offset] if offset < len(labels) else "",
                            "value": "Unknown",
                        }
                    )
    xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    return xml, stats


def repack_ods(original: bytes, content_xml: bytes) -> bytes:
    source = zipfile.ZipFile(io.BytesIO(original))
    payload = {info.filename: source.read(info.filename) for info in source.infolist()}
    payload["content.xml"] = content_xml
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as dest:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        dest.writestr(info, payload["mimetype"])
        for name, blob in payload.items():
            if name == "mimetype":
                continue
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            dest.writestr(info, blob)
    return out.getvalue()


def audit_ods(data: bytes) -> dict:
    root = etree.fromstring(zipfile.ZipFile(io.BytesIO(data)).read("content.xml"))
    result = {"rows": 0, "blank": 0, "unknown": 0, "posted_thru": "", "lands": ""}
    for table in root.findall(".//table:table", NS):
        labels = header_labels(table)
        if not labels or labels[0] != "Document Type":
            continue
        fact_count = min(8, len(labels))
        for index, row in enumerate(body_rows(table), start=1):
            cells = explicit_cells(row)
            if index <= 7 and len(cells) >= 2:
                label = cell_text(cells[0]).rstrip(":")
                if label == "Date Posted Thru":
                    result["posted_thru"] = cell_text(cells[1])
                elif label == "Lands":
                    result["lands"] = cell_text(cells[1])
            if index < 9:
                continue
            values = fact_values(row, fact_count)
            if not any(values):
                continue
            result["rows"] += 1
            for value in values:
                if value == "":
                    result["blank"] += 1
                elif value.upper() == "UNKNOWN":
                    result["unknown"] += 1
    return result


def style_cell(cell, bold=False, date=False):
    cell.font = FONT_BOLD if bold else FONT
    cell.alignment = WRAP
    cell.border = THIN
    if date:
        cell.number_format = "M/D/YYYY"


def write_checklist(path: Path, spec: dict) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Abstract checklist"
    rows = {
        2: BLOCK1,
        3: spec["block1"],
        5: BLOCK2,
        6: spec["block2"],
        8: BLOCK3,
        9: spec["block3"],
    }
    for row_number, values in rows.items():
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row_number, col, value)
            style_cell(cell, bold=row_number in (2, 5, 8), date=isinstance(value, datetime))
        ws.row_dimensions[row_number].height = 22 if row_number in (2, 5, 8) else 48
    widths = [28, 34, 42, 24, 32, 38, 32, 36, 30, 38, 26]
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.page_setup.horizontalCentered = True
    ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.5, bottom=0.5)
    ws.sheet_view.showGridLines = False
    ws.oddFooter.center.text = "Combine-Harvest  |  qualified unsigned abstract  |  15 October 2026"
    ws.oddFooter.center.font = "Calibri"
    ws.oddFooter.center.size = 9
    ws.freeze_panes = "A2"
    ws.print_title_rows = "1:1"
    ws.page_setup.scale = 70
    wb.save(path)


def add_paragraph(doc: Document, text: str, bold=False, space_after=8, space_before=0):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(space_after)
    paragraph.paragraph_format.space_before = Pt(space_before)
    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    run = paragraph.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(11)
    run.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)
    return paragraph


def write_letter(path: Path, spec: dict) -> None:
    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(0.85)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    add_paragraph(doc, f"Section {spec['section']} Abstract Certification Letter", bold=True, space_after=2)
    add_paragraph(doc, f"Township {spec['township_words']}, Range {spec['range_words']}, 6th P.M.", space_after=0)
    add_paragraph(doc, f"Section {spec['section']}: All", space_after=0)
    add_paragraph(doc, "Johnson County, Wyoming", space_after=12)
    add_paragraph(doc, "Contents of abstract:", bold=True, space_after=6)
    add_paragraph(doc, spec["county_paragraph"])
    add_paragraph(doc, spec["assessor_paragraph"])
    add_paragraph(doc, spec["federal_paragraph"])
    add_paragraph(doc, spec["srp_paragraph"])
    add_paragraph(doc, "Judgment, lien, mortgage, and civil-suit search: not performed.")
    if spec.get("partial_paragraph"):
        add_paragraph(doc, spec["partial_paragraph"])
    add_paragraph(doc, spec["disclaimer"])
    add_paragraph(
        doc,
        f"Prepared on October 15, 2026, as a qualified working abstract, through the source dates shown above, by: {LANDMAN}.",
    )
    add_paragraph(doc, "_________________________________", space_before=14, space_after=2)
    add_paragraph(doc, LANDMAN, space_after=0)
    for line in ADDRESS:
        add_paragraph(doc, line, space_after=0)
    add_paragraph(doc, "Unsigned. Examiner acceptance, official certification, and a client release are not claimed.", space_before=12)
    doc.save(path)


def township_words(value: str) -> str:
    number = value[:-1]
    return f"{number} {'North' if value.endswith('N') else 'South'}"


def range_words(value: str) -> str:
    number = value[:-1]
    return f"{number} {'West' if value.endswith('W') else 'East'}"


def checklist_grid(path: Path) -> dict[tuple[int, int], object]:
    wb = openpyxl.load_workbook(path, data_only=False)
    ws = wb[wb.sheetnames[0]]
    grid = {}
    for row in ws.iter_rows(max_row=ws.max_row, max_col=min(ws.max_column or 1, 12)):
        for cell in row:
            if cell.value is not None:
                grid[(cell.row, cell.column)] = cell.value
    return grid


def text_of(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%-m/%-d/%Y")
    return "" if value is None else str(value).strip()


def finish_xlsx_index(path: Path, fills: list[dict], file_name: str) -> dict:
    wb = openpyxl.load_workbook(path)
    ws = wb["Index"] if "Index" in wb.sheetnames else wb.active
    stats = {"rows": 0, "unknown_before": 0, "filled": 0, "posted_thru": "", "lands": ""}
    labels = [text_of(ws.cell(9, col).value) for col in range(1, 9)]
    for row in range(1, 8):
        label = text_of(ws.cell(row, 1).value).rstrip(":")
        if label == "Date":
            ws.cell(row, 2).value = PREPARED
            ws.cell(row, 2).number_format = "M/D/YYYY"
        elif label == "Date Posted Thru":
            stats["posted_thru"] = text_of(ws.cell(row, 2).value)
        elif label == "Lands":
            stats["lands"] = text_of(ws.cell(row, 2).value)
    for row in range(10, ws.max_row + 1):
        values = [ws.cell(row, col).value for col in range(1, 9)]
        if not any(text_of(value) for value in values):
            continue
        stats["rows"] += 1
        for col, value in enumerate(values, start=1):
            current = text_of(value)
            if current.upper() == "UNKNOWN":
                stats["unknown_before"] += 1
            elif current == "":
                ws.cell(row, col).value = "Unknown"
                stats["filled"] += 1
                fills.append(
                    {
                        "file": file_name,
                        "sheet": ws.title,
                        "row": row,
                        "column": "ABCDEFGH"[col - 1],
                        "field": labels[col - 1],
                        "value": "Unknown",
                    }
                )
    for row in ws.iter_rows(max_row=ws.max_row, max_col=min(ws.max_column, 9)):
        for cell in row:
            if cell.value is None:
                continue
            name = cell.font.name or "Calibri"
            size = cell.font.size or 11
            cell.font = Font(name=name if name != "Aptos Narrow" else "Calibri", size=size, bold=cell.font.bold)
            cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.sheet_view.showGridLines = False
    ws.oddFooter.center.text = "Combine-Harvest  |  qualified unsigned abstract  |  15 October 2026"
    wb.save(path)
    return stats


def federal_name(path: Path) -> str:
    match = re.search(r"(WYW-\d+|W-\d+)", path.name)
    return match.group(1) if match else path.stem


def build_spec(meta: dict, county: dict, federals: list[dict], partial: bool) -> dict:
    serials = [item["serial"] for item in federals if item["rows"] or item["posted_thru"]]
    federal_bits = [
        f"{item['serial']}: {item['rows']} entries, posted through {item['posted_thru'] or 'Unknown'}"
        for item in federals
    ]
    unknown = county["unknown"] + sum(item["unknown"] for item in federals)
    lands = f"T{meta['township']}-R{meta['range']} Section {meta['section']}: All"
    starting = county.get("starting") or "Inception"
    starting_phrase = "Inception" if starting == "Inception" else "an unknown starting date"
    posted = county["posted_thru"] or "Unknown"
    if posted.upper() == "UNKNOWN":
        posted_phrase = "an official posted-through date that remains Unknown"
    else:
        posted_phrase = f"the last indexed instrument recorded {posted}"
    if unknown:
        unknown_sentence = (
            f"{unknown} of those cells are Unknown because the examined source did not establish the fact."
        )
    else:
        unknown_sentence = "No fact cell in columns A through H is Unknown."
    county_paragraph = (
        f"Index of documents reflecting the entries posted in the tract indices located and maintained "
        f"by the Johnson County Clerk, from {starting_phrase} through {posted_phrase}. "
        f"County index entries: {county['rows']}. Every fact cell in columns A through H is filled. "
        f"{unknown_sentence}"
    )
    if serials:
        federal_paragraph = "Images of federal lease files: " + "; ".join(federal_bits) + "."
        srp_paragraph = (
            "Bureau of Land Management (MLRS) Serial Register Pages: included for "
            + ", ".join(serials)
            + ", through the posted-through date shown on each federal index."
        )
        blm_value = "\n".join(serials)
        srp_value = "Yes for the serials listed in this package"
        reviewed = "Yes — serial register pages were compared with the federal indexes in this package"
    else:
        federal_paragraph = "Images of federal lease files: N/A. No separate federal lease index is included for this section."
        srp_paragraph = "Bureau of Land Management (MLRS) Serial Register Pages: N/A."
        blm_value = "N/A"
        srp_value = "N/A"
        reviewed = "N/A — no federal serial register page is included"
    partial_paragraph = ""
    if partial:
        entry_word = "entry" if county["rows"] == 1 else "entries"
        verb = "is" if county["rows"] == 1 else "are"
        partial_paragraph = (
            f"This section is a qualified partial abstract. Only the {county['rows']} source-supported "
            f"county {entry_word} in the index {verb} admitted. Tract-index leads that do not have an authenticated "
            f"original in this package are not added. Section 30 instruments 142117, 174634, and 309041 remain "
            f"unapplied, and 169051 remains on hold for missing folio 363, because those complete index fields "
            f"were not established in the selected parent."
            if meta["section"] == 30
            else (
                f"This section is a qualified partial abstract. Only the {county['rows']} source-supported "
                f"county {entry_word} in the index {verb} admitted. Additional tract-index leads are not added without "
                "an authenticated original."
            )
        )
    status = "Qualified partial" if partial else "Qualified unsigned"
    return {
        "section": meta["section"],
        "township_words": township_words(meta["township"]),
        "range_words": range_words(meta["range"]),
        "county_paragraph": county_paragraph,
        "assessor_paragraph": "Johnson County Assessor and Treasurer reports, detailing surface-owner accounts and taxes due: N/A.",
        "federal_paragraph": federal_paragraph,
        "srp_paragraph": srp_paragraph,
        "partial_paragraph": partial_paragraph,
        "disclaimer": (
            f"This abstract was prepared and made solely for the benefit of {CLIENT}. It is not a title opinion "
            "and it is not a guaranty of title. The information is conditioned on the accuracy of the tract indices "
            "of Johnson County, including any errors or omissions in those indices. This abstract is limited to the "
            "materials reviewed. Unknown means the examined source did not establish that fact. It is not a zero, "
            "a waiver, or a finding that no instrument exists."
        ),
        "block1": [
            "Yes",
            "Yes — county index and linked qualifications" if not partial else "Partial — admitted rows only",
            "Included where a plat or corner record is an index entry; no separate plat deliverable",
            "Yes — tract index compared with the indexed entries",
            "Yes",
            blm_value,
            srp_value,
            "N/A",
            "N/A",
            reviewed,
            "Yes — unsigned",
        ],
        "block2": [
            "Yes",
            "Johnson",
            lands,
            PREPARED,
            county.get("starting") or "Inception",
            "Unsigned",
            LANDMAN,
            PROJECT,
        ],
        "block3": [
            "Yes — unsigned",
            CLIENT,
            f"{lands}\nJohnson County, Wyoming",
            f"County index: {county['rows']} entries; {posted_phrase}; Unknown fact cells: {county['unknown']}.",
            federal_paragraph.removeprefix("Images of federal lease files: ").rstrip("."),
            srp_paragraph.removeprefix("Bureau of Land Management (MLRS) Serial Register Pages: ").rstrip("."),
            PREPARED,
        ],
        "status": status,
        "unknown": unknown,
        "serials": serials,
    }


def load_members(package_zip: Path) -> list[tuple[str, bytes]]:
    archive = zipfile.ZipFile(package_zip)
    members = []
    for info in archive.infolist():
        if info.is_dir():
            continue
        if info.filename.startswith("__MACOSX") or "/." in info.filename:
            continue
        members.append((info.filename, archive.read(info.filename)))
    return members


def process_ods_package(meta: dict, fills: list[dict]) -> dict:
    folder_name = f"{meta['section']}-{meta['township']}-{meta['range']}"
    dest = OUT_DIR / folder_name
    dest.mkdir(parents=True, exist_ok=True)
    county = {"rows": 0, "unknown": 0, "posted_thru": "", "starting": "Inception", "filled": 0}
    federals = []
    for name, blob in load_members(IN_DIR / meta["zip"]):
        if not name.lower().endswith(".ods"):
            continue
        content_xml = zipfile.ZipFile(io.BytesIO(blob)).read("content.xml")
        content, touched = finish_ods(content_xml, fills, Path(name).name)
        packed = repack_ods(blob, content)
        audit = audit_ods(packed)
        if audit["blank"]:
            raise SystemExit(f"{name} still has {audit['blank']} blank fact cells")
        out_name = Path(name).name
        (dest / out_name).write_bytes(packed)
        record = {
            "serial": federal_name(Path(out_name)),
            "rows": audit["rows"],
            "unknown": audit["unknown"],
            "posted_thru": audit["posted_thru"],
            "filled": touched["filled"],
            "file": out_name,
            "county_file": "Johnson_Co" in out_name or out_name.startswith(f"{meta['township']}"),
        }
        if record["county_file"]:
            county = {
                "rows": audit["rows"],
                "unknown": audit["unknown"],
                "posted_thru": audit["posted_thru"],
                "starting": "Inception",
                "filled": touched["filled"],
                "file": out_name,
            }
        else:
            federals.append(record)
    spec = build_spec(meta, county, federals, meta.get("partial", False))
    checklist = dest / f"Abstract_Checklist_{meta['section']}-{meta['township']}-{meta['range']}.xlsx"
    letter = dest / f"{meta['section']}-{meta['township']}-{meta['range']}_Certification_Letter.docx"
    write_checklist(checklist, spec)
    write_letter(letter, spec)
    return {
        "meta": meta,
        "county": county,
        "federals": federals,
        "spec": spec,
        "folder": dest,
    }


def process_xlsx_package(meta: dict, fills: list[dict]) -> dict:
    folder_name = f"{meta['section']}-{meta['township']}-{meta['range']}"
    dest = OUT_DIR / folder_name
    dest.mkdir(parents=True, exist_ok=True)
    county_blob = None
    county_name = ""
    for name, blob in load_members(IN_DIR / meta["zip"]):
        base = Path(name).name
        if base.endswith("_County.xlsx"):
            county_blob = blob
            county_name = f"{meta['township']}-{meta['range']}-{meta['section']}_Johnson_Co_Penterra_Abstract_Index.xlsx"
    if county_blob is None:
        raise SystemExit(f"no county workbook in {meta['zip']}")
    path = dest / county_name
    path.write_bytes(county_blob)
    touched = finish_xlsx_index(path, fills, county_name)
    wb = openpyxl.load_workbook(path)
    ws = wb["Index"]
    blank = 0
    unknown = 0
    rows = 0
    for row in range(10, ws.max_row + 1):
        values = [text_of(ws.cell(row, col).value) for col in range(1, 9)]
        if not any(values):
            continue
        rows += 1
        for value in values:
            if value == "":
                blank += 1
            elif value.upper() == "UNKNOWN":
                unknown += 1
    if blank:
        raise SystemExit(f"{county_name} still has {blank} blank fact cells")
    county = {
        "rows": rows,
        "unknown": unknown,
        "posted_thru": touched["posted_thru"],
        "starting": "Inception" if text_of(ws["B4"].value).upper() != "UNKNOWN" else "Unknown",
        "filled": touched["filled"],
        "file": county_name,
    }
    if text_of(ws["B4"].value).upper() == "UNKNOWN":
        county["starting"] = "Unknown"
    spec = build_spec(meta, county, [], True)
    checklist = dest / f"Abstract_Checklist_{meta['section']}-{meta['township']}-{meta['range']}.xlsx"
    letter = dest / f"{meta['section']}-{meta['township']}-{meta['range']}_Certification_Letter.docx"
    write_checklist(checklist, spec)
    write_letter(letter, spec)
    return {"meta": meta, "county": county, "federals": [], "spec": spec, "folder": dest}


def checklist_complete(path: Path) -> None:
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    expected = {2: 11, 3: 11, 5: 8, 6: 8, 8: 7, 9: 7}
    for row, width in expected.items():
        for col in range(1, width + 1):
            value = ws.cell(row, col).value
            if value is None or str(value).strip() == "":
                raise SystemExit(f"{path.name} cell {get_column_letter(col)}{row} is empty")
            if ws.cell(row, col).font.name != "Calibri" or ws.cell(row, col).font.size != 11:
                raise SystemExit(f"{path.name} cell {get_column_letter(col)}{row} is not Calibri 11")


def letter_complete(path: Path, section: int) -> None:
    doc = Document(path)
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    required = [
        f"Section {section} Abstract Certification Letter",
        "Johnson County, Wyoming",
        CLIENT,
        "October 15, 2026",
        "Unsigned",
        "15314 N. May Avenue",
        "Unknown means the examined source did not establish that fact",
    ]
    for item in required:
        if item not in text:
            raise SystemExit(f"{path.name} is missing {item!r}")


def write_reconciliation(results: list[dict], fills: list[dict]) -> None:
    wb = openpyxl.Workbook()
    summary = wb.active
    summary.title = "Counts"
    headers = [
        "Section",
        "Twp-Rng",
        "Status",
        "County entries",
        "County Unknown A:H",
        "Blank A:H after finish",
        "Federal indexes",
        "Federal entries",
        "Cells filled from blank",
        "Posted through",
    ]
    summary.append(headers)
    for result in results:
        meta = result["meta"]
        county = result["county"]
        summary.append(
            [
                meta["section"],
                f"{meta['township']}-{meta['range']}",
                result["spec"]["status"],
                county["rows"],
                county["unknown"],
                0,
                len(result["federals"]),
                sum(item["rows"] for item in result["federals"]),
                county["filled"] + sum(item["filled"] for item in result["federals"]),
                county["posted_thru"],
            ]
        )
    summary.append(
        [
            "TOTAL",
            "",
            "",
            f"=SUM(D2:D{1+len(results)})",
            f"=SUM(E2:E{1+len(results)})",
            0,
            f"=SUM(G2:G{1+len(results)})",
            f"=SUM(H2:H{1+len(results)})",
            f"=SUM(I2:I{1+len(results)})",
            "",
        ]
    )
    filled = wb.create_sheet("Blank cells filled")
    filled.append(["File", "Sheet", "Visual row", "Column", "Field", "Value written"])
    for item in fills:
        filled.append([item["file"], item["sheet"], item["row"], item["column"], item["field"], item["value"]])
    parity = wb.create_sheet("Format parity")
    parity.append(["Element", "Finished Overtime rule", "Combine-Harvest finish"])
    parity.append(["Index type", "Calibri 11; metadata rows 1-7; blank row 8; headings row 9; data from row 10", "Preserved on every county and federal index"])
    parity.append(["Fact cells A:H", "No blank fact cells; unknown facts stay explicit", "Blank fact cells written as Unknown; existing values unchanged"])
    parity.append(["Comments", "Not used as a place to invent narrative", "Left unchanged"])
    parity.append(["Checklist", "Three blocks, Calibri 11, every label and value filled", "Rebuilt to the Section 11 checklist labels and filled"])
    parity.append(["Letter heading", "Section N Abstract Certification Letter", "Applied; the Section 15 heading defect was not copied"])
    parity.append(["Signature", "Signed Overtime letters were already accepted", "Unsigned. No certification date is invented"])
    parity.append(["Preparation date", "Package date, not a county cutoff", "October 15, 2026"])
    open_items = wb.create_sheet("Open items")
    open_items.append(["Section", "Item", "Disposition"])
    open_items.append(["All", "Examiner signature, official certification, and client release", "Open. Letters are unsigned on purpose."])
    open_items.append(["All", "Judgment, lien, mortgage, and civil-suit search", "Not performed."])
    open_items.append(["All", "Assessor and treasurer tax reports", "N/A in these packages."])
    open_items.append(["06", "Federal case files and the 22 composite source dependencies", "Open. No federal index was added."])
    open_items.append(["07", "Corner Record 161576", "Open. 161575 is not a substitute and was not relabeled."])
    open_items.append(["13", "County acreage 296.600 versus federal 298.600, survey 163698, and post-June 5, 2026 continuation", "Open. Conflicting readings were not collapsed."])
    open_items.append(["13 and 24", "Original-source joins and current chain", "Open."])
    open_items.append(["18", "Original-source joins and governing agreements", "Open."])
    open_items.append(["19, 30, 31", "Partial admitted rows only", "Not expanded from unauthenticated tract leads."])
    open_items.append(["30", "142117, 174634, and 309041", "Described by the source return and left unapplied. Full index fields were not in the selected parent."])
    open_items.append(["30", "169051 folio 363", "Hold. The supplied images stop at folio 362."])
    open_items.append(["All", "Windows, live Acrobat, and PC acceptance", "Not claimed."])
    for ws in wb.worksheets:
        for cell in ws[1]:
            style_cell(cell, bold=True)
        for column in ws.columns:
            letter = get_column_letter(column[0].column)
            width = min(56, max(14, max(len(text_of(cell.value)) for cell in column) + 2))
            ws.column_dimensions[letter].width = width
        ws.auto_filter.ref = ws.dimensions
        ws.freeze_panes = "A2"
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 1
        ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
        ws.sheet_view.showGridLines = False
    path = OUT_DIR / "Combine_Harvest_Finish_Reconciliation.xlsx"
    wb.save(path)


def main() -> None:
    if OUT_DIR.exists():
        for child in OUT_DIR.rglob("*"):
            if child.is_file():
                child.unlink()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fills: list[dict] = []
    results = []
    for meta in PACKAGES:
        if meta["kind"] == "ods":
            results.append(process_ods_package(meta, fills))
        else:
            results.append(process_xlsx_package(meta, fills))
    for result in results:
        meta = result["meta"]
        checklist_complete(result["folder"] / f"Abstract_Checklist_{meta['section']}-{meta['township']}-{meta['range']}.xlsx")
        letter_complete(result["folder"] / f"{meta['section']}-{meta['township']}-{meta['range']}_Certification_Letter.docx", meta["section"])
    write_reconciliation(results, fills)
    lines = []
    for path in sorted(OUT_DIR.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.relative_to(OUT_DIR).as_posix()}")
    (OUT_DIR / "SHA256_MANIFEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"packages {len(results)} blank-to-unknown {len(fills)}")
    for result in results:
        meta = result["meta"]
        county = result["county"]
        federal_rows = sum(item["rows"] for item in result["federals"])
        print(
            f"S{meta['section']}: county {county['rows']} unknown {county['unknown']} "
            f"federal {len(result['federals'])}/{federal_rows} filled {county['filled'] + sum(item['filled'] for item in result['federals'])}"
        )


if __name__ == "__main__":
    main()
