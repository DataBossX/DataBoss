#!/usr/bin/env python3
"""Build unsigned Johnson County abstract packages from the iDoc printouts.

Recording dates, parties, document numbers, and book-page values come from the
typed iDoc search pages inside the tract-index PDFs. A date of document is
entered only where an instrument image was already read. Nothing here is an
examiner signature or a certified searched-through date.
"""
import re
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableRow, TableCell
from odf.text import P

sys.path.insert(0, str(Path(__file__).resolve().parent))
from idoc_parse import parse_pdf, book_page  # noqa: E402

OUT = Path(__file__).resolve().parent
PREP = "10/18/2026"
PREP_LONG = "October 18, 2026"
CLIENT = "Anschutz Exploration Corporation"
PROJECT = "Abstract 210275 Combine-Harvest"
INDEXER = "Ryan Gille"

THIN = Border(
    left=Side(style="thin", color="000000"),
    right=Side(style="thin", color="000000"),
    top=Side(style="thin", color="000000"),
    bottom=Side(style="thin", color="000000"),
)
FONT = Font(name="Calibri", size=11, color="000000")
FONT_B = Font(name="Calibri", size=11, bold=True, color="000000")
WRAP = Alignment(wrap_text=True, vertical="center")
WHITE = PatternFill(fill_type=None)


def norm_key(bp):
    book, _, page = (bp or "").partition("-")
    book = re.sub(r"[^A-Z0-9]", "", book.upper())
    page = re.sub(r"[^A-Z0-9]", "", page.upper())
    m = re.match(r"0*(\d+)(.*)", page)
    if m:
        page = (m.group(1) or "0") + m.group(2)
    return f"{book}-{page}"


# Instrument-proved fields. Comments stay blank or exactly "missing image".
OVERLAYS = {
    (19, norm_key("87A35-0318")): dict(
        type="Warranty Deed",
        grantor="Harriet Bros. Limited Partnership",
        grantee="Iberlin Ranch Partnership",
        doc="017554",
        dod="1/31/1994",
        rec="2/1/1994",
        legal="Lots 1, 2, E/2 NW/4, NE/4 of 19-47N-76W, aol",
        comments="",
        source="instrument image",
    ),
    (19, norm_key("RW32-0623")): dict(
        type="Memorandum of Amended and Restated Gas Transportation Agreement",
        grantor="Moriah Powder River, LLC",
        grantee="Thunder Creek Gas Services, L.L.C.",
        doc="171060",
        dod="12/18/2017",
        rec="4/20/2018",
        legal="All of 19-47N-76W, aol",
        comments="",
        source="instrument image",
    ),
    (19, norm_key("0371-0354")): dict(
        type="Assignment, Conveyance and Bill of Sale",
        grantor="Grayson Mill Powder River, LLC",
        grantee="AEC GM 2, LLC",
        doc="169051",
        dod="12/21/2017",
        rec="1/16/2018",
        legal="Lots 15 and 18, E/2 SW/4 of 19-47N-76W, aol",
        comments="missing image",
        source="instrument page 1 and Exhibit A-1; folio 363 / Exhibit B was not in the supplied image",
    ),
    (31, norm_key("0084-0029")): dict(
        type="Warranty Deed, With Release of Homestead",
        grantor="George O. Wormwood and Florence S. Wormwood, HW",
        grantee="Iberlin and Son, a co-partnership composed of John Iberlin, Simon Iberlin, and John P. Iberlin",
        doc="36246",
        dod="5/3/1951",
        rec="5/17/1951",
        legal="S/2 S/2, NE/4 SE/4 of 31-47N-76W, aol",
        comments="",
        source="instrument image",
    ),
    (31, norm_key("RW32-0623")): dict(
        type="Memorandum of Amended and Restated Gas Transportation Agreement",
        grantor="Moriah Powder River, LLC",
        grantee="Thunder Creek Gas Services, L.L.C.",
        doc="171060",
        dod="12/18/2017",
        rec="4/20/2018",
        legal="All of 31-47N-76W, aol",
        comments="",
        source="instrument image",
    ),
    (31, norm_key("0392-0536")): dict(
        type="Mineral Deed",
        grantor="Mary A. Torske",
        grantee="TorPit, LLC, a Wyoming limited liability company",
        doc="305188",
        dod="12/29/2020",
        rec="1/11/2021",
        legal="NE/4 SE/4, S/2 S/2 of 31-47N-76W, Parcel IV, aol",
        comments="",
        source="instrument image",
    ),
    (31, norm_key("0405-0049")): dict(
        type="Corrective Mineral Deed",
        grantor="Mary A. Torske",
        grantee="TorPit, LLC",
        doc="335434",
        dod="9/20/2024",
        rec="10/29/2024",
        legal="NE/4 SE/4, S/2 S/2 of 31-47N-76W, aol",
        comments="",
        source="instrument image",
    ),
    (31, norm_key("0371-0354")): dict(
        type="Assignment, Conveyance and Bill of Sale",
        grantor="Grayson Mill Powder River, LLC",
        grantee="AEC GM 2, LLC",
        doc="169051",
        dod="12/21/2017",
        rec="1/16/2018",
        legal="Lots 8, 9, 16 and 17, W/2 W/2 of 31-47N-76W, aol",
        comments="missing image",
        source="instrument page 1 and Exhibit A-1; folio 363 / Exhibit B was not in the supplied image",
    ),
}

S30_ROW = dict(
    type="Assignment, Conveyance and Bill of Sale",
    grantor="Grayson Mill Powder River, LLC",
    grantee="AEC GM 2, LLC",
    doc="169051",
    bp=book_page("371", "354"),
    dod="12/21/2017",
    rec="1/16/2018",
    legal="Lots 8, 9, 16 and 17, W/2 W/2 of 30-47N-76W, aol",
    comments="missing image",
    source="instrument page 1 and Exhibit A-1; folio 363 / Exhibit B was not in the supplied image",
)


def default_legal(section, twp, rng):
    return (
        f"All of {section}-{twp}N-{rng}W, aol. "
        "Aliquot not stated on the county index printout."
    )


def apply_overlay(section, row):
    ov = OVERLAYS.get((section, norm_key(row["bp"])))
    if not ov:
        return row
    # Keep the printout recording date if the image reading names a different one.
    if ov.get("rec") and row.get("rec") and ov["rec"] != row["rec"]:
        row = dict(row)
        row["source"] = (
            f"conflict: printout recording date {row['rec']}; "
            f"instrument reading {ov['rec']}. Left as printed."
        )
        return row
    row = dict(row)
    row.update(ov)
    return row


def style_ws(ws):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.horizontalCentered = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.5, bottom=0.5, header=0.2, footer=0.2)
    ws.sheet_view.showGridLines = False
    ws.oddFooter.left.text = "Johnson County, Wyoming  |  Abstract 210275  |  Unsigned"
    ws.oddFooter.right.text = "Page &P of &N"
    ws.page_setup.scale = None
    ws.sheet_format.defaultRowHeight = 18
    ws.sheet_view.view = "normal"
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID


def write_index(path, meta, rows, lands):
    wb = Workbook()
    ws = wb.active
    ws.title = "Index"
    style_ws(ws)
    pairs = [
        (1, "Index County:", "Johnson"),
        (2, "Lands:", lands),
        (3, "Date:", PREP),
        (4, "Starting Date:", rows[0]["rec"] if rows else "Unknown"),
        (5, "Date Posted Thru:", meta["validated"]),
        (6, "Indexed By:", INDEXER),
        (7, "Project:", PROJECT),
    ]
    for r, label, val in pairs:
        c1 = ws.cell(r, 1, label)
        c2 = ws.cell(r, 2, val)
        c1.font = FONT_B
        c2.font = FONT
        c1.fill = WHITE
        c2.fill = WHITE
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=9)
    headers = [
        "Document Type", "Grantor", "Grantee", "Doc No", "Book-Page",
        "Date of Doc", "Rec Date", "Legal Description", "Comments",
    ]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(9, col, h)
        cell.font = FONT_B
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        cell.border = THIN
        cell.fill = WHITE
    for i, row in enumerate(rows):
        vals = [
            row["type"], row["grantor"], row["grantee"], row["doc"], row["bp"],
            row["dod"], row["rec"], row["legal"], row["comments"],
        ]
        for col, val in enumerate(vals, 1):
            cell = ws.cell(10 + i, col, val)
            cell.font = FONT
            cell.alignment = WRAP
            cell.border = THIN
            cell.fill = WHITE
        ws.row_dimensions[10 + i].height = 32
    widths = [42, 46, 46, 16, 16, 14, 14, 62, 18]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    last = 9 + max(len(rows), 1)
    ws.auto_filter.ref = f"A9:I{last}"
    ws.freeze_panes = "A10"
    ws.row_dimensions[9].height = 22
    ws.print_title_rows = "1:9"
    ws.oddHeader.center.text = lands
    wb.save(path)


def write_ods(path, meta, rows, lands):
    doc = OpenDocumentSpreadsheet()
    table = Table(name="Index")

    def add(values):
        tr = TableRow()
        for v in values:
            tc = TableCell()
            tc.addElement(P(text="" if v is None else str(v)))
            tr.addElement(tc)
        table.addElement(tr)

    add(["Index County:", "Johnson"])
    add(["Lands:", lands])
    add(["Date:", PREP])
    add(["Starting Date:", rows[0]["rec"] if rows else "Unknown"])
    add(["Date Posted Thru:", meta["validated"]])
    add(["Indexed By:", INDEXER])
    add(["Project:", PROJECT])
    add([""])
    add(["Document Type", "Grantor", "Grantee", "Doc No", "Book-Page", "Date of Doc", "Rec Date", "Legal Description", "Comments"])
    for row in rows:
        add([row["type"], row["grantor"], row["grantee"], row["doc"], row["bp"], row["dod"], row["rec"], row["legal"], row["comments"]])
    doc.spreadsheet.addElement(table)
    doc.save(str(path))


def write_checklist(path, meta, rows, lands, images_note):
    wb = Workbook()
    ws = wb.active
    ws.title = "Checklist"
    style_ws(ws)
    labels = [
        "County Index", "County Documents", "Plat", "STR online search",
        "Compare index to Uploads", "BLM File", "SRP", "State File",
        "Lease Report if applicable", "Reviewed SRP vs BLM file or State file",
        "Certification Letter",
    ]
    values = ["Yes", "Partial", "No", "Yes", "Partial", "N/A", "N/A", "N/A", "N/A", "N/A", "Yes, unsigned"]
    ws.cell(1, 1, "Abstract checklist").font = FONT_B
    for i, lab in enumerate(labels, 1):
        c = ws.cell(2, i, lab)
        c.font = FONT_B
        c.alignment = WRAP
        c.border = THIN
        c.fill = WHITE
        v = ws.cell(3, i, values[i - 1])
        v.font = FONT
        v.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        v.border = THIN
        v.fill = WHITE
        ws.column_dimensions[get_column_letter(i)].width = 18
    ws.row_dimensions[2].height = 36
    heads2 = ["County", "Lands Covered", "Date Prepared", "Starting Date", "Date Reviewed", "Landman Name", "Project / Prospect"]
    vals2 = ["Johnson", lands, PREP, rows[0]["rec"] if rows else "Unknown", PREP, INDEXER, PROJECT]
    for i, lab in enumerate(heads2, 1):
        c = ws.cell(5, i, lab)
        c.font = FONT_B
        c.border = THIN
        c.fill = WHITE
        v = ws.cell(6, i, vals2[i - 1])
        v.font = FONT
        v.border = THIN
        v.alignment = WRAP
        v.fill = WHITE
    proved = sum(1 for r in rows if str(r["source"]).startswith("instrument image"))
    partial = sum(1 for r in rows if str(r["source"]).startswith("instrument page"))
    contents = (
        f"County index: {len(rows)} entries. County land-record validation date printed on the search: {meta['validated']}. "
        f"Instrument images read: {proved}. Instrument pages read with pages still missing: {partial}. {images_note}"
    )
    heads3 = ["Client", "STR & County", "Contents for County Records", "Contents for BLM / State", "SRP Info", "Preparation Date"]
    vals3 = [CLIENT, lands + ", Johnson County, Wyoming", contents, "Not included in this county package.", "N/A", PREP]
    for i, lab in enumerate(heads3, 1):
        c = ws.cell(8, i, lab)
        c.font = FONT_B
        c.border = THIN
        c.fill = WHITE
        c.alignment = WRAP
        v = ws.cell(9, i, vals3[i - 1])
        v.font = FONT
        v.border = THIN
        v.alignment = WRAP
        v.fill = WHITE
    ws.row_dimensions[8].height = 32
    ws.row_dimensions[9].height = 64
    wb.save(path)


def write_letter(path, meta, rows, lands, role, images_note):
    doc = Document()
    for s in doc.sections:
        s.top_margin = Inches(0.85)
        s.bottom_margin = Inches(0.75)
        s.left_margin = Inches(1)
        s.right_margin = Inches(1)
        s.page_width = Inches(8.5)
        s.page_height = Inches(11)
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    def add(text, bold=False, center=False, space_after=6):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.space_before = Pt(0)
        if center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = bold
        run.font.name = "Calibri"
        run.font.size = Pt(11)

    section = meta["section"]
    add(f"Section {section} Abstract Certification Letter", bold=True, center=True, space_after=4)
    add("UNSIGNED", bold=True, center=True, space_after=10)
    add(lands)
    add("Johnson County, Wyoming", space_after=10)
    add("Contents of abstract:", bold=True)
    proved = sum(1 for r in rows if str(r["source"]).startswith("instrument image"))
    partial = sum(1 for r in rows if str(r["source"]).startswith("instrument page"))
    add(role)
    add(
        f"The index contains {len(rows)} instruments. The county search printout states that the land records were validated through {meta['validated']}. "
        f"The printout date is {meta['printed']}. Date Posted Thru on the index is that validation date. It is not an examiner's certified searched-through cutoff."
    )
    add(
        f"Instrument images were read for {proved} entries. {partial} additional entries use an instrument page and Exhibit A-1, and the comment on those rows is \"missing image\" because folio 363 / Exhibit B was not in the supplied image. "
        f"For every other entry the recording date, parties, document number, and book-page are the values printed on the county search. The date of the document is Unknown unless an instrument image was read. {images_note}"
    )
    add("Where the printout gives no book and page, Book-Page is Unknown. Corner records in this search are in that group.")
    add("Johnson County Assessor and Treasurer office reports are not included.")
    add("Federal lease files and Bureau of Land Management serial register pages are not included in this county package.")
    add("Judgment, lien, mortgage, and civil-suit searches beyond the instruments named on the county index printout were not performed.", space_after=10)
    add(
        f"This abstract was prepared and made solely for the benefit of {CLIENT} and is not to be construed as a title opinion, nor a guaranty of title, and the information contained herein is conditioned upon the accuracy of the records of Johnson County, including any errors or omissions contained therein. "
        "This abstract is limited to the materials reviewed and described herein. The instruments referred to have not been examined to determine their legal sufficiency, except for the instrument images identified in the qualifications sheet."
    )
    add(f"Prepared on {PREP_LONG}, through the source dates shown above, by: {INDEXER}.", space_after=16)
    add("_________________________________")
    add("Unsigned. Examiner signature is not on this letter.", space_after=12)
    add("Gille Energy, LLC, Agent for")
    add("Penterra Services, LLC")
    add("15314 N. May Avenue")
    add("Edmond, OK 73013")
    doc.save(path)


def write_quals(path, meta, rows, extra_lines):
    wb = Workbook()
    ws = wb.active
    ws.title = "Qualifications"
    style_ws(ws)
    headers = ["Doc No", "Book-Page", "What is proved", "What remains Unknown", "Source"]
    for col, h in enumerate(headers, 1):
        c = ws.cell(1, col, h)
        c.font = FONT_B
        c.border = THIN
        c.fill = WHITE
    for i, row in enumerate(rows, 2):
        src = str(row["source"])
        if src.startswith("instrument image"):
            proved = "Parties, document type, document number, book-page, date of document, recording date, and the legal description on this row."
            unknown = "Current ownership, burdens not named on the face that was read, and any page that was not in the supplied image."
        elif src.startswith("instrument page"):
            proved = "Parties, document type, document number, book-page, date of document, recording date, and the legal description taken from page 1 and Exhibit A-1."
            unknown = "Folio 363 and Exhibit B were not in the supplied image. The comment is \"missing image\"."
        else:
            proved = "The county electronic-index printout reports the document type, parties, document number, book-page, and the date entered here as the recording date."
            unknown = "Date of document, aliquot or lot legal, and the instrument image. The printout does not prove execution, acknowledgment, or present ownership."
        vals = [row["doc"], row["bp"], proved, unknown, src]
        for col, val in enumerate(vals, 1):
            cell = ws.cell(i, col, val)
            cell.font = FONT
            cell.alignment = WRAP
            cell.border = THIN
            cell.fill = WHITE
        ws.row_dimensions[i].height = 48
    for i, w in enumerate([16, 16, 55, 62, 55], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:E{1 + len(rows)}"
    note = wb.create_sheet("Scope")
    note["A1"] = "Scope"
    note["A1"].font = FONT_B
    lines = [
        f"Section {meta['section']}, T{meta['twp']}N-R{meta['rng']}W, Johnson County, Wyoming.",
        f"Prepared {PREP_LONG}. County validation date printed on the search: {meta['validated']}. Printout date: {meta['printed']}.",
        f"Entries: {len(rows)}. This matches the Showing count on the printout.",
        "The index is unsigned. It is not a title opinion and not a guaranty of title.",
        "Date Posted Thru is the validation date printed by the county search. It is not an examiner's certified searched-through cutoff.",
        "Comments are blank where an instrument image was read, and \"missing image\" where the instrument image is not in the package.",
        "Index-only party names and document types are the spellings printed by the county search, including the search's own abbreviations.",
    ] + extra_lines
    for i, line in enumerate(lines, 2):
        note.cell(i, 1, line).font = FONT
        note.row_dimensions[i].height = 32
    note.column_dimensions["A"].width = 140
    wb.save(path)


PDFS = {
    6: "/tmp/s6_tract.pdf",
    7: "/tmp/s7_tract.pdf",
    13: "/tmp/s13_tract.pdf",
    18: "/tmp/s18_tract.pdf",
    19: "/tmp/s19_tract.pdf",
    31: "/tmp/s31_tract.pdf",
}

ROLES = {
    6: (
        "This index is the Johnson County electronic land-record search for Section 6 printed in the tract-index PDF. "
        "It lists the 32 instruments on that search. It does not replace the longer image-examined runsheet already in the Section 6 folder. "
        "That runsheet carries aliquot descriptions this printout does not state. The search's latest recording date is 12/27/2022."
    ),
    7: (
        "This index is the Johnson County electronic land-record search for Section 7 printed in the tract-index PDF. "
        "It is an electronic-search schedule. Where an image-examined runsheet in the section folder states an aliquot, that aliquot remains the examined legal. This printout does not state aliquots."
    ),
    13: (
        "This index is the Johnson County electronic land-record search for Section 13, Township 47 North, Range 77 West, printed in the tract-index PDF. "
        "It does not retire aliquot legals already entered on an image-examined runsheet in the section folder."
    ),
    18: (
        "This index is the Johnson County electronic land-record search for Section 18 printed in the tract-index PDF. "
        "It is an electronic-search schedule. Where an image-examined runsheet in the section folder states an aliquot, that aliquot remains the examined legal. This printout does not state aliquots."
    ),
    19: (
        "This index replaces the two-row partial index dated October 19, 2026. "
        "It is the Johnson County electronic land-record search for Section 19, 69 instruments, with the instrument images that were already in the section folder written over the matching rows."
    ),
    31: (
        "This index replaces the four-row partial index dated October 19, 2026. "
        "It is the Johnson County electronic land-record search for Section 31, 91 instruments, with the instrument images that were already in the section folder written over the matching rows."
    ),
}

NOTES = {
    6: "On the separate image-examined Section 6 runsheet, Book 0141-0528 is document 32630. A cell on that runsheet that still reads 22630 is the open stamp conflict; the instrument image reads 32630. That instrument is not one of the 32 rows on this electronic search.",
    7: "Document 169051, Book 0371-0354, is on this search. Its Section 7 aliquot was not read from an instrument image in this package, so the row stays index-only.",
    13: "The Section 13 search was validated through 7/9/2026 and printed 7/15/2026. Later searches for the Range 76 West sections were validated in October 2026. This section was not re-searched to that later date in the materials on hand.",
    18: "Document 169051, Book 0371-0354, is on this search. Its Section 18 aliquot was not read from an instrument image in this package, so the row stays index-only.",
    19: "Book 87A35-0318 and Book RW32-0623 were read from the images in the section folder. Book 0371-0354 was read from page 1 and Exhibit A-1 only.",
    31: "Books 0084-0029, RW32-0623, 0392-0536, and 0405-0049 were read from the images in the section folder. Book 0371-0354 was read from page 1 and Exhibit A-1 only. The Wormwood deed's recording stamp is 5/17/1951; the deed itself is dated 5/3/1951.",
}


def load(section):
    meta, rows, warnings = parse_pdf(PDFS[section])
    if warnings or len(rows) != meta["n"] or meta["section"] != section:
        raise SystemExit(f"S{section} parse failed: {len(rows)} vs {meta['n']} warnings={warnings} meta={meta}")
    # Township/range are not always tokenized the same way; the printouts are the known tracts.
    twp, rng = (47, 77) if section == 13 else (47, 76)
    meta["twp"], meta["rng"], meta["section"] = twp, rng, section
    out = []
    for row in rows:
        row["legal"] = default_legal(section, twp, rng)
        row = apply_overlay(section, row)
        if row["comments"] not in ("", "missing image"):
            raise SystemExit(f"bad comment {row['comments']!r}")
        out.append(row)

    def key(r):
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", r["rec"])
        if not m:
            return (9999, 99, 99, r["doc"])
        return (int(m.group(3)), int(m.group(1)), int(m.group(2)), r["doc"])

    out.sort(key=key)
    return meta, out


def lands_of(meta):
    return f"T{meta['twp']}N-R{meta['rng']}W Section {meta['section']}"


def emit(meta, rows, role, extra):
    folder = OUT / f"Section_{meta['section']:02d}_T{meta['twp']}N_R{meta['rng']}W"
    folder.mkdir(parents=True, exist_ok=True)
    lands = lands_of(meta)
    stem = f"{meta['twp']}N-{meta['rng']}W-{meta['section']:02d}_Johnson_Co_Penterra_Abstract_Index"
    write_index(folder / f"{stem}.xlsx", meta, rows, lands)
    write_ods(folder / f"{stem}.ods", meta, rows, lands)
    write_checklist(folder / f"Abstract_Checklist_{meta['section']}-{meta['twp']}N-{meta['rng']}W.xlsx", meta, rows, lands, extra[0] if extra else "")
    write_letter(
        folder / f"{meta['section']}-{meta['twp']}N-{meta['rng']}W_Certification_Letter.docx",
        meta, rows, lands, role, extra[0] if extra else "",
    )
    write_quals(folder / f"{meta['section']}-{meta['twp']}N-{meta['rng']}W_Qualifications.xlsx", meta, rows, extra)
    return folder


def emit_s30():
    meta = {
        "section": 30, "twp": 47, "rng": 76,
        "validated": "Unknown", "printed": "Unknown", "n": 1,
    }
    rows = [dict(S30_ROW)]
    folder = OUT / "Section_30_T47N_R76W"
    folder.mkdir(parents=True, exist_ok=True)
    lands = "T47N-R76W Section 30"
    role = (
        "This Section 30 package is not a full county index. The PDF saved in the Section 30 tract-index folder is a Johnson County search of Section 19, Township 47 North, Range 76 West, 69 of 69 results, validated through 10/13/2026. "
        "Its document numbers match the Section 19 search. It was not used to build a Section 30 index. "
        "The one row in this workbook is Document 169051, Book 0371-0354, taken from page 1 and Exhibit A-1 of that instrument. Folio 363 and Exhibit B were not in the supplied image."
    )
    extra = [
        "The file named as the Section 30 tract index is a Section 19 iDoc search. No Section 30 electronic index was built from it.",
        "One proved row is included: Document 169051, Book 0371-0354, dated 12/21/2017, recorded 1/16/2018, Grayson Mill Powder River, LLC to AEC GM 2, LLC, covering Lots 8, 9, 16 and 17, W/2 W/2 of 30-47N-76W.",
        "The image-examined Section 30 runsheet, the 12/5/2017 purchase and sale agreement, and the rest of the section index remain open.",
    ]
    stem = "47N-76W-30_Johnson_Co_Penterra_Abstract_Index"
    # Date Posted Thru stays Unknown: there is no Section 30 validation date in hand.
    write_index(folder / f"{stem}.xlsx", meta, rows, lands)
    write_ods(folder / f"{stem}.ods", meta, rows, lands)
    write_checklist(folder / "Abstract_Checklist_30-47N-76W.xlsx", meta, rows, lands, extra[0])
    write_letter(folder / "30-47N-76W_Certification_Letter.docx", meta, rows, lands, role, extra[0])
    write_quals(folder / "30-47N-76W_Qualifications.xlsx", meta, rows, extra)
    # The quals scope line says the count matches Showing. Correct that sheet's scope for this partial.
    return folder


def main():
    summary = []
    for section in (6, 7, 13, 18, 19, 31):
        meta, rows = load(section)
        emit(meta, rows, ROLES[section], [NOTES[section]])
        unknown = sum(1 for r in rows if r["dod"] == "Unknown")
        images = sum(1 for r in rows if str(r["source"]).startswith("instrument"))
        summary.append((section, len(rows), meta["validated"], rows[0]["rec"], rows[-1]["rec"], unknown, images))
        print(f"S{section}: {len(rows)} validated {meta['validated']} {rows[0]['rec']} -> {rows[-1]['rec']} unknown DoD {unknown} image rows {images}")
    emit_s30()
    print("S30: one proved row; full index withheld")
    # Fix the S30 scope sentence that claims a Showing match.
    from openpyxl import load_workbook
    q = OUT / "Section_30_T47N_R76W" / "30-47N-76W_Qualifications.xlsx"
    wb = load_workbook(q)
    chk = load_workbook(OUT / "Section_30_T47N_R76W" / "Abstract_Checklist_30-47N-76W.xlsx")
    chk.active["A3"] = "No"
    chk.active["A3"].font = FONT
    chk.active["B3"] = "No"
    chk.active["D3"] = "No"
    chk.active["E3"] = "No"
    chk.active["K3"] = "Yes, unsigned — not a full section"
    chk.save(OUT / "Section_30_T47N_R76W" / "Abstract_Checklist_30-47N-76W.xlsx")
    wb = load_workbook(q)
    ws = wb["Scope"]
    for row in ws.iter_rows(min_row=2, max_col=1):
        val = row[0].value or ""
        if val.startswith("Entries:"):
            row[0].value = "Entries: 1. This is the one instrument row proved for Section 30. It is not the Showing count of a Section 30 search."
    wb.save(q)
    return summary


if __name__ == "__main__":
    main()
