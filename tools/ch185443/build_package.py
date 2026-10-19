"""Build dated Combine-Harvest index packages from a selected master JSON.

The master JSON stays outside the public repository. Pass its path explicitly.
This builder does not overwrite a selected production master and does not
issue an adoption receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.page import PageMargins

from format_indexes import (
    PREP_DATE,
    audit_workbook,
    build_database,
    load_master,
    write_ods,
    write_xlsx,
)

TOWNSHIP = {
    6: ("47N-76W", "T47N-R76W Section 6"),
    7: ("47N-76W", "T47N-R76W Section 7"),
    13: ("47N-77W", "T47N-R77W Section 13"),
    18: ("47N-76W", "T47N-R76W Section 18"),
    19: ("47N-76W", "T47N-R76W Section 19"),
    24: ("47N-77W", "T47N-R77W Section 24"),
    30: ("47N-76W", "T47N-R76W Section 30"),
    31: ("47N-76W", "T47N-R76W Section 31"),
}

# Published competing inventories. R41 and R45 figures are transcribed from the
# October 19 Drive status documents. They were not re-counted from those ZIPs
# in this session. The 1,141 figures are re-counted from the master JSON.
PUBLISHED_INVENTORIES = {
    "R41": {
        "role": "Earlier selected qualified unsigned reference. Not replaced.",
        "county": 501,
        "federal": 65,
        "total": 566,
        "by_section_applications": {6: 69, 7: 35, 13: 111, 18: 49, 19: 38, 24: 212, 30: 23, 31: 29},
    },
    "R3-derived-1141": {
        "role": "Source-corrected successor used as the row source for this candidate.",
        "county": 652,
        "federal": 489,
        "total": 1141,
    },
    "R45": {
        "role": "Different index population. Not interchangeable with R41 or the 1,141-row successor.",
        "county": 1370,
        "federal": 175,
        "total": 1545,
        "by_section": {
            6: (121, 0),
            7: (185, 132),
            13: (227, 14),
            18: (133, 3),
            19: (165, 0),
            24: (345, 26),
            30: (107, 0),
            31: (87, 0),
        },
    },
}

HOLDS = [
    ("H-S18-CUSTODY", "18", "Section 18 historical source-custody gap. The October 19 source-root snapshot left the selected Section 18 intake empty, with 136 historical filename/size records not matched in current roots.", "OPEN"),
    ("H-S30-APPENDIX", "30", "Section 30 tract-index physical page 8 typed appendix of 69 results identifies Section 19, not Section 30.", "OPEN"),
    ("H-WYW145618-P1", "24", "WYW145618 Part 1 of 2 is absent. The located file is Part 2, 35 pages. Index rows stored as Part 1 on pages 164, 166, 170, and 188 do not fall inside that PDF and were not renumbered.", "OPEN"),
    ("H-CASES", "all", "Referenced federal files W40637, W39577, W094604, W114684, and W134230 are not a complete acquired case file for every serial cited.", "OPEN"),
    ("H-169051", "7,18", "County instrument 169051 is missing printed folio 363 / Exhibit B. Existing missing-image flags stay.", "OPEN"),
    ("H-105911", "6", "County Doc 105911, Book 335 pages 580-583, remains a source hold.", "OPEN"),
    ("H-161576", "7", "Corner record 161576 remains a source hold.", "OPEN"),
    ("H-CENSUS", "federal", "Full document-boundary census remains open for WYW094605 parts 1-2, WYW134914, WYW149799 parts 1-2, WYW153528, WYW153681 part 1, and any uncounted exhibits.", "OPEN"),
    ("H-S6-FED", "6", "Zero selected federal rows is a selection condition, not proof that no federal lease affects Section 6. WYW149799 still needs source-to-section reconciliation.", "OPEN"),
    ("H-CUTOFF", "all", "No official county, BLM, or OSLI searched-through date was verified. 10/19/2026 is the preparation date only.", "OPEN"),
    ("H-NATIVE", "all", "Windows Excel, Word, and Acrobat cold-open and print parity were not run. RyansPC was offline.", "OPEN"),
    ("H-EXAMINER", "all", "No examiner signature and no five completed legal-acceptance cycles.", "OPEN"),
]

PART_LEDGER = [
    ("WYW094605", "1", 211, "Unknown", "Full boundary census open"),
    ("WYW094605", "2", 195, "Unknown", "Full boundary census open"),
    ("WYW094605", "3", 88, "39", "Fresh complete part census: 27 substantive, 7 administrative, 5 postal, plus jacket"),
    ("WYW094605", "4", 2, "0", "Jacket and empty-folder notice"),
    ("WYW131225", "1", 217, "72", "Attributed complete ledger"),
    ("WYW131225", "2", 151, "79", "Attributed complete ledger"),
    ("WYW131225", "3", 115, "51", "Attributed complete ledger"),
    ("WYW131225", "4", 2, "0", "Attributed complete ledger"),
    ("WYW133620", "1", 190, "81", "Attributed complete ledger"),
    ("WYW133620", "2", 164, "70", "Attributed complete ledger"),
    ("WYW133620", "3", 261, "115", "Attributed complete ledger"),
    ("WYW133620", "4", 2, "0", "Attributed complete ledger"),
    ("WYW153681", "1", 195, "Unknown", "Full boundary census open"),
    ("WYW153681", "2", 79, "28", "Fresh census: 25 substantive, 1 administrative, 2 postal, plus jacket"),
    ("WYW153528", "unnumbered", 233, "Unknown", "Full boundary census open"),
    ("WYW145618", "2", 35, "12", "Part 2 of 2 located. Part 1 missing. Plus jacket."),
    ("WYW134914", "unnumbered", 212, "Unknown", "Full boundary census open"),
    ("WYW191271X", "unnumbered", 74, "Unknown", "Tractor (Deep) Unit. A 74-page visual census is attributed in the October 19 status. Document-boundary acceptance is not closed here."),
    ("WYW149799", "1", 155, "Unknown", "Needs reconciliation with sections 6 and 7"),
    ("WYW149799", "2", 139, "Unknown", "Full boundary census open"),
]


def section_folder_name(section: int) -> str:
    township, _lands = TOWNSHIP[section]
    return f"Section {section} package {township}"


def _paragraphs(body: str) -> str:
    chunks = []
    run_props = '<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr>'
    for paragraph in body.split("\n\n"):
        runs = []
        for index, line in enumerate(paragraph.split("\n")):
            if index:
                runs.append(f"<w:r>{run_props}<w:br/></w:r>")
            runs.append(f'<w:r>{run_props}<w:t xml:space="preserve">{escape(line)}</w:t></w:r>')
        chunks.append(f"<w:p>{''.join(runs)}</w:p>")
    return "".join(chunks)


def write_letter(path: Path, section: int, federal_files: list[str], county_rows: int, federal_rows: int) -> None:
    township, lands = TOWNSHIP[section]
    township_no, range_no = township.split("-")
    serials = ", ".join(federal_files) if federal_files else ""
    federal_text = (
        f"The accompanying federal indexes list {federal_rows} section applications from {serials}. Page is the first physical page of each indexed occurrence. Part is the source part number. Unnumbered parts are blank. No official federal search-through date is asserted."
        if serials
        else "No federal case workbook is selected for this section. That is not proof that no federal lease affects the section."
    )
    body = f"""Township {township_no.replace('N', '')} North, Range {range_no.replace('W', '')} West, 6th P.M.
Section {section}: {lands}
Johnson County, Wyoming

Contents of abstract:

Index of documents reflecting entries in the materials selected for this section, limited to the {county_rows} county applications in the accompanying index. County Comments are blank or exactly "missing image". No official search-through date is asserted.

{federal_text}

Bureau of Land Management serial-register pages and case jackets are accounted in the evidence database and are not operative client rows merely to increase the row count.

Judgment, lien, mortgage, and civil-suit search not performed.

This package was prepared on 10/19/2026 as qualified review work product for Combine-Harvest CH185443. It is not a title opinion, not a guaranty of title, and not a certified abstract. It is limited to the materials reviewed and listed. The instruments have not been examined for legal sufficiency. This letter is unsigned. Final acceptance is reserved for the authorized examiner and owner.

Prepared 10/19/2026 by: Ryan Gille

_________________________________
Gille Energy, LLC
"""
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:body>{_paragraphs(body)}
  <w:sectPr>
   <w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/>
   <w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720"/>
  </w:sectPr>
 </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="xml" ContentType="application/xml"/>
 <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)


def write_checklist(path: Path, section: int, county_rows: int, federal_rows: int, federal_files: list[str]) -> None:
    _township, lands = TOWNSHIP[section]
    book = Workbook()
    sheet = book.active
    sheet.title = "Checklist"
    rows = [
        ("County", "Johnson"),
        ("Lands Covered", lands),
        ("Date completed", PREP_DATE),
        ("Starting Date", None),
        ("Date Certified/Verified", None),
        ("Date Posted Thru", "Unknown"),
        ("Landman Name", "Ryan Gille"),
        ("Project/Prospect", "Combine-Harvest CH185443 / AFE210275"),
        ("County Index", f"Formatted candidate; {county_rows} selected applications"),
        ("County Documents", "Not certified complete against every handwritten appearance"),
        ("Plat", "No separate plat member in this candidate"),
        ("STR online search", "Reference route only; no authenticated cutoff"),
        ("Compare index to source images", "Open except where a named visual census receipt already exists"),
        ("BLM File", ", ".join(federal_files) if federal_files else "No selected federal workbook"),
        ("BLM section applications", federal_rows),
        ("SRP", "Administrative; excluded from operative rows"),
        ("State File", "Not included"),
        ("Certification Letter", "Unsigned; no search-through date"),
        ("Status", "QUALIFIED REVIEW / UNSIGNED / HOLD"),
        ("Adoption", "No adoption receipt. R41 remains unreplaced."),
    ]
    bold = Font(name="Calibri", size=11, bold=True)
    body = Font(name="Calibri", size=11)
    thin = Border(
        left=Side(style="thin", color="000000"),
        right=Side(style="thin", color="000000"),
        top=Side(style="thin", color="000000"),
        bottom=Side(style="thin", color="000000"),
    )
    fill = PatternFill("solid", fgColor="D9E2F3")
    for index, (label, value) in enumerate(rows, start=1):
        left = sheet.cell(index, 1, label)
        left.font = bold
        left.fill = fill
        left.border = thin
        cell = sheet.cell(index, 2, value)
        cell.font = body
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        cell.border = thin
        if hasattr(value, "year"):
            cell.number_format = "m/d/yyyy"
        sheet.row_dimensions[index].height = 18
    sheet.column_dimensions["A"].width = 42
    sheet.column_dimensions["B"].width = 88
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToPage = True
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 1
    sheet.page_setup.paperSize = sheet.PAPERSIZE_TABLOID
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_margins = PageMargins(left=0.4, right=0.4, top=0.4, bottom=0.4, header=0.2, footer=0.2)
    path.parent.mkdir(parents=True, exist_ok=True)
    book.save(path)


def write_custody(path: Path, section: int, master: dict) -> None:
    township, lands = TOWNSHIP[section]
    relevant = [hold for hold in HOLDS if hold[1] in {str(section), "all", "federal"} or str(section) in hold[1].split(",")]
    lines = [
        f"# Source custody — Section {section} {township}",
        "",
        "This candidate does not contain a fresh copy of every original image. Originals stay in their existing Drive locations and are not overwritten.",
        "",
        f"Lands: {lands}",
        f"Row source locator: `{master.get('parent_drive_id', '')}`",
        f"Recorded parent SHA-256: `{master.get('parent_sha256', '')}`",
        "The row JSON used for this candidate is named on the private master. Overtime sections 11, 13, and 15 are formatting donors only.",
        "",
        "Preparation date 10/19/2026 is not a recording cutoff. Date Posted Thru remains Unknown.",
        "",
        "## Holds that apply here",
        "",
    ]
    for hold_id, _scope, text, status in relevant:
        lines.append(f"- `{hold_id}` ({status}): {text}")
    lines.append("")
    path.write_text("\n".join(lines))


def status_markdown(master: dict, audits: list[dict]) -> str:
    lines = [
        "# CH185443 Combine-Harvest candidate status",
        "",
        "Prepared 10/19/2026. QUALIFIED REVIEW. UNSIGNED. HOLD.",
        "",
        "This is not a certified abstract, title opinion, or guaranty of title. Final acceptance is reserved for the authorized examiner and owner.",
        "",
        "No adoption receipt is issued. R41 (566 applications) is not replaced. R45 (1,545 applications) is a different population. This candidate formats the sealed 1,141-row source-corrected successor.",
        "",
        "## Section applications in this candidate",
        "",
        "A row is a section application. It is not, by itself, a unique original instrument, and it is not proof that every page of a case file has been listed.",
        "",
        "| Section | Township | County | Federal | BLM workbooks | Blank | Unknown | Qualified Unknown | Unresolved | Missing image | Release |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    by_section = defaultdict(list)
    for audit in audits:
        by_section[audit["section"]].append(audit)
    totals = defaultdict(int)
    for item in master["summary"]:
        section = item["section"]
        township = TOWNSHIP[section][0]
        missing = sum(audit["missing_images"] for audit in by_section[section])
        lines.append(
            f"| {section} | {township} | {item['county_rows']} | {item['federal_rows']} | {item['federal_workbooks']} | {item['substantive_display_blanks']} | {item['substantive_display_unknown']} | {item['substantive_display_qualified_unknown']} | {item['unresolved_evidence_cells']} | {missing} | HOLD |"
        )
        for key in (
            "county_rows",
            "federal_rows",
            "federal_workbooks",
            "substantive_display_blanks",
            "substantive_display_unknown",
            "substantive_display_qualified_unknown",
            "unresolved_evidence_cells",
        ):
            totals[key] += item[key]
    lines.append(
        f"| TOTAL |  | {totals['county_rows']} | {totals['federal_rows']} | {totals['federal_workbooks']} | {totals['substantive_display_blanks']} | {totals['substantive_display_unknown']} | {totals['substantive_display_qualified_unknown']} | {totals['unresolved_evidence_cells']} | {sum(a['missing_images'] for a in audits)} | HOLD |"
    )
    lines += [
        "",
        "Blank, Unknown, and qualified Unknown counts are substantive cells. County Comments and BLM File No and Comments are excluded from that gap total. County Comments in this candidate are blank or exactly `missing image`.",
        "",
        "## BLM workbooks in this candidate",
        "",
        "Documents are operative index rows. Parts are the distinct numeric Part values on those rows. A header-only workbook is retained. An unnumbered source is not called Part 1.",
        "",
        "| Section | BLM file | Documents | Parts | Part numbers | Blank cells | Unknown cells |",
        "| --- | --- | ---: | ---: | --- | ---: | ---: |",
    ]
    for audit in audits:
        if audit["kind"] == "county":
            continue
        part_text = ", ".join(str(part) for part in audit["parts"]) if audit["parts"] else ""
        lines.append(
            f"| {audit['section']} | {audit['file']} | {audit['documents']} | {audit['part_count']} | {part_text} | {audit['blank_cells']} | {audit['unknown_cells']} |"
        )
    lines += [
        "",
        "## Located BLM parts",
        "",
        "Page counts below are the October 19 source census, not a new rendering of every page in this session. Content occurrence is Unknown where the boundary census is still open.",
        "",
        "| Case | Part | Physical pages | Content occurrences | Basis |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for case_id, part, pages, occurrences, basis in PART_LEDGER:
        lines.append(f"| {case_id} | {part} | {pages} | {occurrences} | {basis} |")
    lines += [
        "",
        "Located case and SRP union previously measured as 27 PDF binaries and 2,759 physical pages. Seven SRP files, 39 pages, stay out of the operative indexes. WYW145618 Part 1 is absent.",
        "",
        "## Competing inventories",
        "",
        "| Inventory | County | Federal | Total | Treatment |",
        "| --- | ---: | ---: | ---: | --- |",
        "| R41 | 501 | 65 | 566 | Selected earlier reference. Not replaced. Section application counts 69, 35, 111, 49, 38, 212, 23, 29. |",
        "| R3-derived successor | 652 | 489 | 1,141 | Row source for this candidate. Re-counted from the master JSON. |",
        "| R45 | 1,370 | 175 | 1,545 | Different population. Transcribed from the October 19 verified-status note. Not re-parsed here. |",
        "",
        "These populations are not interchangeable completion counts. The larger count does not control.",
        "",
        "## What this session verified",
        "",
        "- The 1,141-row JSON was downloaded and hashed.",
        "- County Comments are only blank or `missing image`.",
        "- BLM File No and Comments cells are blank.",
        "- All-digit document numbers are stored as integers. Leading-zero spellings remain in `workbook_rows.doc_no_source_text`.",
        "- Date Posted Thru is the visible value Unknown. Starting Date is an intentional blank because `Available records` is not a date.",
        "- Overtime sections 11, 13, and 15 were downloaded and their county column widths were measured.",
        "",
        "## What remains held",
        "",
    ]
    for hold_id, _scope, text, status in HOLDS:
        lines.append(f"- `{hold_id}` {status}: {text}")
    lines += [
        "",
        "C:\\DataBoss, Google Drive for Desktop on the Windows PC, Landman Helper, Adobe Acrobat, and local Ollama or LM Studio were not available on this cloud session. RyansPC was already reported offline.",
        "",
    ]
    return "\n".join(lines) + "\n"


def discrepancy_markdown() -> str:
    return """# CH185443 discrepancy ledger — 10/19/2026

No adoption receipt.

| Population | Applications | Basis in this session | Decision |
| --- | ---: | --- | --- |
| R41 | 566 | Transcribed from the independent October 19 audit. Not re-opened as a ZIP here. | Remains the earlier selected reference. Not replaced. |
| R3-derived successor | 1,141 | Re-counted from `CH185443_Current_Master_Rows_52035_20261019.json`: 652 county and 489 federal, 1,141 unique row ids. | Used only as the row source for this qualified candidate. |
| R45 | 1,545 | Transcribed from the October 19 verified-status note: 1,370 county and 175 federal. The R45 ODS files were not re-parsed here. | Different population. Not merged into the candidate. |

Held candidates, unsupported extras, and section-inapplicable rows from other branches stay outside this candidate. They are not deleted.

Section 6 federal rows in the 1,141-row successor are zero. That is not a finding that Section 6 has no federal lease. WYW149799 remains open.

The Section 30 tract-index appendix that describes Section 19 is a source-identity hold, not a reason to move Section 30 rows into Section 19 without the original page.
"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(folder: Path, manifest_path: Path) -> None:
    lines = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path != manifest_path and path.suffix != ".zip":
            lines.append(f"{sha256_file(path)}  {path.relative_to(folder).as_posix()}")
    manifest_path.write_text("\n".join(lines) + ("\n" if lines else ""))


def zip_directory(folder: Path, archive_path: Path) -> None:
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path != archive_path:
                archive.write(path, path.relative_to(folder).as_posix())


def seed_evidence(database: Path, master: dict) -> None:
    connection = sqlite3.connect(database)
    for case_id, part, pages, occurrences, basis in PART_LEDGER:
        connection.execute(
            "INSERT INTO blm_parts VALUES (?, ?, ?, ?, ?)",
            (case_id, part, pages, occurrences, basis),
        )
        connection.execute(
            "INSERT INTO physical_pages VALUES (?, ?, ?, ?)",
            (case_id, part, pages, basis),
        )
        connection.execute(
            "INSERT INTO document_boundaries VALUES (?, ?, ?, ?, ?)",
            (
                f"{case_id}-{part}",
                case_id,
                part,
                "closed" if occurrences not in {"Unknown", ""} and str(occurrences).isdigit() else "open",
                basis,
            ),
        )
    cases = {}
    for case_id, _part, pages, _occurrences, _basis in PART_LEDGER:
        cases.setdefault(case_id, 0)
        cases[case_id] += pages
    for case_id, pages in cases.items():
        connection.execute(
            "INSERT INTO blm_cases VALUES (?, ?, ?, ?)",
            (case_id, pages, "see part ledger", "Part 1 missing" if case_id == "WYW145618" else ""),
        )
    appearances = {
        6: "Complete 7-page census attributed: 128 appearances, 117 locator groups. 36 candidates not promoted.",
        7: "Complete 11-page census attributed: 251 appearances, 196 locator groups.",
        13: "Original-index vision still open in the October 19 notes.",
        18: "Source-custody gap. Appearance census not closed here.",
        19: "Original-index vision still open. Section 30 appendix reportedly describes this section.",
        24: "Original-index vision still open.",
        30: "Tract-index page 8 appendix identifies Section 19.",
        31: "Original-index vision still open.",
    }
    for section, note in appearances.items():
        connection.execute(
            "INSERT INTO county_index_appearances VALUES (?, ?, ?)",
            (section, "attributed" if section in {6, 7} else "open", note),
        )
    for hold_id, scope, text, status in HOLDS:
        connection.execute("INSERT INTO missing_sources VALUES (?, ?, ?, ?)", (hold_id, scope, text, status))
    connection.execute(
        "INSERT INTO evidence_references VALUES (?, ?, ?, ?)",
        (1, "master rows JSON", "downloaded and hashed in this session", master.get("rows_drive_id") or ""),
    )
    connection.execute(
        "INSERT INTO evidence_references VALUES (?, ?, ?, ?)",
        (2, "Overtime donors 11, 13, 15", "ZIP downloaded and column widths measured", master.get("overtime_drive_id") or ""),
    )
    connection.execute(
        "INSERT INTO evidence_references VALUES (?, ?, ?, ?)",
        (3, "selected parent archive", "identity recorded from the master JSON; ZIP bytes not re-downloaded", master.get("parent_drive_id") or ""),
    )
    connection.execute(
        "INSERT INTO ai_receipts VALUES (?, ?, ?, ?)",
        (
            "cursor-20261019",
            "cloud writer",
            "format sealed 1141-row JSON into qualified unsigned candidate",
            "no adoption; originals not overwritten",
        ),
    )
    gates = [
        (1, "source/currentness", "HOLD", "No official cutoff. Parent ZIP bytes not re-hashed in this session."),
        (2, "omissions and duplicates", "HOLD", "1141 row ids are unique. R41 and R45 were not joined instrument-by-instrument."),
        (3, "field correctness", "PASS-FOR-CANDIDATE-RULES", "Comments, File No, dates, numeric doc numbers, and Unknown cells checked against the row JSON."),
        (4, "native print parity", "HOLD", "LibreOffice print check may run here. Excel and Acrobat on the PC did not."),
        (5, "zip hash and reopen", "SEE PACKAGE LOG", "SHA-256, CRC, and reopen are recorded with the package."),
    ]
    for cycle, gate, status, evidence in gates:
        connection.execute(
            "INSERT INTO acceptance_gates VALUES (?, ?, ?, ?)",
            (gate, cycle, status, evidence),
        )
    for section, (township, _lands) in TOWNSHIP.items():
        connection.execute(
            "UPDATE section_applicability SET township = ? WHERE section = ?",
            (township, section),
        )
    connection.commit()
    connection.close()


def build(master_path: Path, output: Path) -> Path:
    master = load_master(master_path)
    output.mkdir(parents=True, exist_ok=True)
    audits = []
    grouped = defaultdict(list)
    for workbook in master["workbooks"]:
        grouped[int(workbook["section"])].append(workbook)
        audits.append(audit_workbook(workbook))
    for section, books in grouped.items():
        folder = output / section_folder_name(section)
        folder.mkdir(parents=True, exist_ok=True)
        federal_files = [Path(book["file"]).stem.split("_")[0] for book in books if book["kind"] != "county"]
        county_rows = next(book["row_count"] for book in books if book["kind"] == "county")
        federal_rows = sum(book["row_count"] for book in books if book["kind"] != "county")
        township = TOWNSHIP[section][0]
        write_letter(
            folder / f"{section}-{township}_Certification_Letter.docx",
            section,
            federal_files,
            county_rows,
            federal_rows,
        )
        write_checklist(
            folder / f"Abstract_Checklist_{section}-{township}.xlsx",
            section,
            county_rows,
            federal_rows,
            federal_files,
        )
        write_custody(folder / "SOURCE_CUSTODY.md", section, master)
        for book in books:
            stem = Path(book["file"]).stem
            write_xlsx(folder / f"{stem}.xlsx", book)
            write_ods(folder / f"{stem}.ods", book)
        write_manifest(folder, folder / "SHA256SUMS.txt")
        zip_directory(folder, output / f"Section_{section}_package_{township}_QUALIFIED_UNSIGNED_20261019.zip")
    database = output / "CH185443_inventory_20261019.sqlite"
    build_database(database, master, audits)
    seed_evidence(database, master)
    report = status_markdown(master, audits)
    (output / "CH185443_Status_Report_20261019.md").write_text(report)
    (output / "DISCREPANCY_LEDGER.md").write_text(discrepancy_markdown())
    (output / "README.md").write_text(
        "\n".join(
            [
                "# CH185443 candidate — 10/19/2026",
                "",
                "Qualified, unsigned, and held. This folder does not replace R41, R45, or the sealed parent archive.",
                "",
                "Each section ZIP contains the county workbook, the applicable BLM workbooks, the checklist, the unsigned certification letter, a source-custody note, and SHA-256 sums.",
                "",
                "Original images remain at their existing Drive locations. See SOURCE_CUSTODY.md inside each section folder.",
                "",
            ]
        )
    )
    (output / "audits.json").write_text(json.dumps(audits, indent=2))
    archive_path = output / "CH185443_Formatted_Section_Packages_20261019.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file() and path.suffix != ".zip":
                archive.write(path, path.relative_to(output).as_posix())
    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("master_json", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(build(args.master_json, args.output))


if __name__ == "__main__":
    main()
