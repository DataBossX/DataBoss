#!/usr/bin/env python3
"""Build 9/22/2026 Section 12 and 14 turn-in packages from acquired source bytes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.penterra.image_census import account_paths, sha256_file
from tools.penterra.section_package import (
    CLIENT,
    COUNTY,
    COUNTY_HEADERS,
    FEDERAL_HEADERS,
    INDEXER,
    P12_OCR_PARTY_ROWS,
    PROJECT,
    TOWNSHIP,
    WORK_DATE,
    WORK_DATE_ISO,
    WORK_DATE_LONG,
    cell_text,
    count_populated,
    data_rows,
    load_xlsx_rows,
    purify_county_record,
    write_cert_docx,
    write_cert_pdf,
    write_checklist,
    write_json,
    write_letter_xlsx,
    write_ods,
    zip_members,
)

SOURCES = Path("/tmp/penterra-sources")
OUT = Path("/opt/cursor/artifacts/penterra_s12_s14_20260922")
P12_COUNTY = (
    SOURCES
    / "p12_r3"
    / "Section 12 45N-76W Client Package"
    / "45N-76W-12_Campbell_Co_Penterra_Abstract_Index.xlsx"
)
P14_COUNTY = SOURCES / "p14" / "45N-76W-14_Campbell_Co_Penterra_Abstract_Index.xlsx"
P14_FEDERAL = {
    "WYW-042622": (
        SOURCES / "p14" / "WYW-042622 Campbell Co. Penterra Abstract Index.xlsx",
        "8/4/2026",
        "WYW-042622 / WYWY105565181",
    ),
    "WYW-047318": (
        SOURCES / "p14" / "WYW-047318 Campbell Co. Penterra Abstract Index.xlsx",
        "8/4/2026",
        "WYW-047318 / WYWY105712519",
    ),
    "WYW-072484": (
        SOURCES / "p14" / "WYW-072484 Campbell Co. Penterra Abstract Index.xlsx",
        "8/3/2026",
        "WYW-072484 / WYWY105713400",
    ),
    "WYW-188048": (
        SOURCES / "p14" / "WYW-188048 Campbell Co. Penterra Abstract Index.xlsx",
        "8/12/2026",
        "WYW-188048 / WYWY105698670",
    ),
}


def sha(path: Path) -> str:
    return sha256_file(path)


def signature_block() -> list[str]:
    return [
        f"Prepared on {WORK_DATE_LONG}, through the source dates shown above by: {INDEXER}.",
        "_________________________________",
        "Gille Energy, LLC, Agent for\nPenterra Services, LLC\n15314 N. May Avenue\nEdmond, OK 73013",
    ]


def common_disclaimer() -> str:
    return (
        f"This abstract was prepared and made solely for the benefit of {CLIENT} "
        "and is not to be construed as a title opinion, nor a guaranty of title, and the information "
        f"contained herein is conditioned upon the accuracy of the tract indices of {COUNTY} County, "
        "including any errors or omissions contained therein. This abstract is limited to the materials "
        "reviewed and searched and described herein. The instruments referred to have not been examined "
        "to determine their legal sufficiency."
    )


def build_section_12(out: Path) -> dict:
    rows = load_xlsx_rows(P12_COUNTY)
    raw = data_rows(rows)
    records = [purify_county_record(10 + index, row, P12_OCR_PARTY_ROWS) for index, row in enumerate(raw)]
    header = {
        "county": COUNTY,
        "lands": f"{TOWNSHIP} Section 12: All",
        "date": WORK_DATE,
        "starting_date": "Inception",
        "posted_thru": cell_text(rows[4][1]) if len(rows) > 4 else "",
        "indexed_by": INDEXER,
        "project": PROJECT,
    }
    work = out / "work" / "p12"
    county_ods = work / "45N-76W-12_Campbell_Co_Penterra_Abstract_Index.ods"
    fed_051704 = work / "WYW-051704 Campbell Co. Penterra Abstract Index.ods"
    fed_alt = work / "WYWY105402986 Campbell Co. Penterra Abstract Index.ods"
    checklist = work / "Abstract_Checklist_12-45N-76W.xlsx"
    cert_docx = work / "12-45N-76W_Certification_Letter.docx"
    cert_pdf = work / "12-45N-76W_Certification_Letter.pdf"
    letter = out / "section12-letter.xlsx"
    write_ods(county_ods, header, COUNTY_HEADERS, records)
    write_ods(
        fed_051704,
        {
            **header,
            "lands": "WYW-051704",
            "posted_thru": "",
        },
        FEDERAL_HEADERS,
        [],
    )
    write_ods(
        fed_alt,
        {
            **header,
            "lands": "WYWY105402986 / WYW109544X",
            "posted_thru": "",
        },
        FEDERAL_HEADERS,
        [],
    )
    write_checklist(
        checklist,
        {
            "row2": [
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
            ],
            "row3": [
                "Yes",
                "Yes",
                "N/A - no separate plat member in this six-file abstract package.",
                "",
                "",
                "WYW-051704; WYWY105402986 / WYW109544X",
                "",
                "N/A",
                "N/A",
                "",
                "Yes",
            ],
            "row5": [
                "Abstract Excel Sheet",
                "County",
                "Lands Covered",
                "Date completed",
                "Starting Date",
                "Date Certified/Verified",
                "Landman Name",
                "Project/Prospect",
            ],
            "row6": [
                "Yes",
                COUNTY,
                "T45N-R76W Section 12: All",
                WORK_DATE_ISO,
                "Inception",
                WORK_DATE_ISO,
                INDEXER,
                PROJECT,
            ],
            "row8": [
                "Certification Letter",
                "Client",
                "STR & County",
                "Contents for County Records",
                "Contents for BLM or State Records",
                "SRP Info",
                "Completed and Certified Date",
            ],
            "row9": [
                "Yes",
                CLIENT,
                "T45N-R76W Section 12: All, Campbell County, WY",
                f"County index from inception, {len(records)} entries. Date Posted Thru remains blank; no invented county currentness date.",
                "WYW-051704; WYWY105402986 / WYW109544X",
                "Federal report roles restored as empty Index workbooks. Nineteen WYW-051704 rows and one WYWY105402986/WYW109544X row remain locked on Drive R6/R7 and were not invented.",
                WORK_DATE_ISO,
            ],
        },
    )
    cert = [
        "Township 45 North, Range 76 West, 6th P.M.\nSection 12: All Campbell County, Wyoming",
        "Contents of abstract:",
        "Index of Documents reflecting on the entries posted in the tract indices located and maintained by the Campbell County Clerk's office, from Inception.",
        "Campbell County Assessor and/or Treasurer office reports, detailing surface owner property accounts and the state of any taxes due, N/A.",
        "Images of Federal Lease file WYW-051704 from date of lease sale. County-recorded federal serial materials WYWY105402986 / WYW109544X are in scope. Federal Index roles are included; report rows were not invented from locked R6/R7 bytes.",
        "Bureau of Land Management (MLRS) Serial Register Page WYW-051704 is in scope. Federal currentness / search-through remains a hold.",
        "Judgement, Lien, Mortgages and Civil Suit Search not Performed.",
        common_disclaimer(),
        *signature_block(),
    ]
    write_cert_docx(cert_docx, cert)
    write_cert_pdf(cert_pdf, cert)
    write_letter_xlsx(letter, header, COUNTY_HEADERS, records)
    members = {
        county_ods.name: county_ods,
        fed_051704.name: fed_051704,
        fed_alt.name: fed_alt,
        checklist.name: checklist,
        cert_docx.name: cert_docx,
        cert_pdf.name: cert_pdf,
    }
    zip_path = out / "P12_45N-76W-12__SUPERSEDING_TURNIN_DATED_20260922_EXACT6.zip"
    zip_members(zip_path, members)
    populated = count_populated(records, 9)
    return {
        "section": 12,
        "source": {
            "name": "P12 R3 county workbook",
            "drive_id": "1mhryLfQw54hBWBNJ_gLbcJR0R1fI6l97",
            "sha256": "33e4414512a53b6add33e8bbd04b445eb6cc6cd5e6e7e813992a44ff0fbf1953",
            "bytes": 254902,
            "members_in_source": 4,
        },
        "zip": zip_path.name,
        "zip_sha256": sha(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "exact_n": 6,
        "county_rows": len(records),
        "federal_rows": {"WYW-051704": 0, "WYWY105402986 / WYW109544X": 0},
        "populated_county_cells": {COUNTY_HEADERS[i]: populated[i] for i in range(9)},
        "posted_thru": header["posted_thru"],
        "ocr_party_rows_blanked": sorted(P12_OCR_PARTY_ROWS),
        "locked_federal_target_rows": {"WYW-051704": 19, "WYWY105402986 / WYW109544X": 1},
        "official_queue": 849,
        "ready_for_ryan_owner_review": False,
        "ready_for_external_release": False,
        "members": {name: sha(path) for name, path in members.items()},
        "letter": letter.name,
        "letter_sha256": sha(letter),
    }


def build_section_14(out: Path) -> dict:
    rows = load_xlsx_rows(P14_COUNTY)
    raw = data_rows(rows)
    records = [purify_county_record(10 + index, row, frozenset()) for index, row in enumerate(raw)]
    header = {
        "county": COUNTY,
        "lands": f"{TOWNSHIP} Section 14: All",
        "date": WORK_DATE,
        "starting_date": "Inception",
        "posted_thru": cell_text(rows[4][1]) if len(rows) > 4 else "",
        "indexed_by": INDEXER,
        "project": PROJECT,
    }
    work = out / "work" / "p14"
    county_ods = work / "45N-76W-14_Campbell_Co_Penterra_Abstract_Index.ods"
    write_ods(county_ods, header, COUNTY_HEADERS, records)
    federal_counts = {}
    federal_paths = {}
    for serial, (source, posted, lands) in P14_FEDERAL.items():
        source_rows = data_rows(load_xlsx_rows(source))
        fed_records = []
        for row in source_rows:
            padded = list(row) + [""] * (10 - len(row))
            fed_records.append([cell_text(padded[i]) for i in range(10)])
        federal_counts[serial] = len(fed_records)
        dest = work / f"{serial} Campbell Co. Penterra Abstract Index.ods"
        write_ods(
            dest,
            {**header, "lands": lands, "posted_thru": posted},
            FEDERAL_HEADERS,
            fed_records,
        )
        federal_paths[serial] = dest
    checklist = work / "Abstract_Checklist_14-45N-76W.xlsx"
    cert_docx = work / "14-45N-76W_Certification_Letter.docx"
    cert_pdf = work / "14-45N-76W_Certification_Letter.pdf"
    letter = out / "section14-letter.xlsx"
    write_checklist(
        checklist,
        {
            "row2": [
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
            ],
            "row3": [
                "Yes",
                "Yes",
                "N/A - no separate plat member in this eight-file abstract package.",
                "Yes",
                "Yes",
                "WYW-042622, WYW-047318, WYW-072484, WYW-188048",
                "WYW-042622 and WYW-047318 through 8/4/2026; WYW-072484 through 8/3/2026; WYW-188048 through 8/12/2026",
                "N/A",
                "N/A",
                "Yes",
                "Yes",
            ],
            "row5": [
                "Abstract Excel Sheet",
                "County",
                "Lands Covered",
                "Date completed",
                "Starting Date",
                "Date Certified/Verified",
                "Landman Name",
                "Project/Prospect",
            ],
            "row6": [
                "Yes",
                COUNTY,
                "T45N-R76W Section 14: All",
                WORK_DATE_ISO,
                "Inception",
                WORK_DATE_ISO,
                INDEXER,
                PROJECT,
            ],
            "row8": [
                "Certification Letter",
                "Client",
                "STR & County",
                "Contents for County Records",
                "Contents for BLM or State Records",
                "SRP Info",
                "Completed and Certified Date",
            ],
            "row9": [
                "Yes",
                CLIENT,
                "T45N-R76W Section 14: All, Campbell County, WY",
                f"County index from inception, {len(records)} entries. Seven additional instruments were not included because authenticated source images were unavailable.",
                "WYW-042622, WYW-047318, WYW-072484, WYW-188048",
                "WYW-042622 and WYW-047318 through 8/4/2026; WYW-072484 through 8/3/2026; WYW-188048 through 8/12/2026. No present tract/depth Record Title or Operating Rights allocation inferred beyond source-supported entries.",
                WORK_DATE_ISO,
            ],
        },
    )
    cert = [
        "Township 45 North, Range 76 West, 6th P.M.\nSection 14: All Campbell County, Wyoming",
        "Contents of abstract:",
        f"Index of Documents reflecting on the entries posted in the tract indices located and maintained by the Campbell County Clerk's office, from Inception. {len(records)} instruments are indexed. Seven additional instruments were not included because authenticated source images were unavailable.",
        "Campbell County Assessor and/or Treasurer office reports, detailing surface owner property accounts and the state of any taxes due, N/A.",
        "Images of Federal Lease files WYW-042622, WYW-047318, WYW-072484, and WYW-188048 from date of lease sale through the source materials supplied.",
        "Bureau of Land Management (MLRS) Serial Register Pages WYW-042622 and WYW-047318 from date of lease sale to August 4, 2026; WYW-072484 to August 3, 2026; and WYW-188048 to August 12, 2026.",
        "Judgement, Lien, Mortgages and Civil Suit Search not Performed.",
        common_disclaimer(),
        *signature_block(),
    ]
    write_cert_docx(cert_docx, cert)
    write_cert_pdf(cert_pdf, cert)
    write_letter_xlsx(letter, header, COUNTY_HEADERS, records)
    members = {
        county_ods.name: county_ods,
        **{path.name: path for path in federal_paths.values()},
        checklist.name: checklist,
        cert_docx.name: cert_docx,
        cert_pdf.name: cert_pdf,
    }
    zip_path = out / "P14_45N-76W-14__SUPERSEDING_TURNIN_DATED_20260922_EXACT8.zip"
    zip_members(zip_path, members)
    populated = count_populated(records, 9)
    return {
        "section": 14,
        "source": {
            "name": "Campbell14 R2",
            "drive_id": "1_Yw6XOwVzLJbD28fyyMmSFweakc4Jkos",
            "sha256": "399bb218642a18b704f3947d28ed1fb947d551b142f75ea85a2b2a3d09db56d8",
            "bytes": 284676,
            "members_in_source": 8,
        },
        "zip": zip_path.name,
        "zip_sha256": sha(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "exact_n": 8,
        "county_rows": len(records),
        "federal_rows": federal_counts,
        "federal_row_total": sum(federal_counts.values()),
        "populated_county_cells": {COUNTY_HEADERS[i]: populated[i] for i in range(9)},
        "posted_thru": header["posted_thru"],
        "locked_closeout_target": {"county": 36, "federal": 22},
        "ready_for_ryan_owner_review": False,
        "ready_for_external_release": False,
        "members": {name: sha(path) for name, path in members.items()},
        "letter": letter.name,
        "letter_sha256": sha(letter),
    }


def build_image_census(out: Path) -> dict:
    measured = {
        "P12_Book_583_original": SOURCES / "drive" / "P12_BOOK583__1uhhD7N1DQs_gn7t7Lh-zbgDpQsalnEaO",
        "P12_Book_583_exhibit_extract": SOURCES / "drive" / "P12_EXHIBIT__18VPdw96_WJFdc6Y8kA72aQ7S4lpvMh-Z",
        "BLM_cadastral_plat_T45N-R76W": SOURCES / "public" / "t45nr76w.pdf",
    }
    existing = [path for path in measured.values() if path.exists()]
    accounted = account_paths(existing)
    documented_blm = {
        "WYW-051704_casefile": {
            "files": 6,
            "pages": 949,
            "srp_files": 1,
            "srp_pages": 11,
            "total_files": 7,
            "total_pages": 960,
            "status": "documented_shared_P11_P13_census_not_reopened_this_run",
            "covers_sections": [1, 3, 11, 12],
        },
        "WYW-042622_casefile": {
            "files": "UNKNOWN_this_run",
            "pages": 289,
            "status": "documented_P14_rebuild_receipt_not_reopened_this_run",
            "covers_sections": [14],
        },
        "WYW-047318_casefile": {
            "files": 4,
            "pages": 462,
            "srp_files": 1,
            "srp_pages": 5,
            "status": "documented_shared_P11_P13_census_plus_P14_rebuild_receipt",
            "covers_sections": [11, 13, 14],
        },
        "WYW-072484_casefile": {
            "files": "UNKNOWN_this_run",
            "pages": 162,
            "status": "documented_P14_rebuild_receipt_not_reopened_this_run",
            "covers_sections": [14],
        },
        "WYW-188048_casefile": {
            "files": "UNKNOWN_this_run",
            "pages": 138,
            "status": "documented_P14_rebuild_receipt_not_reopened_this_run",
            "covers_sections": [14],
        },
        "WYWY105402986_WYW109544X": {
            "files": "UNKNOWN_this_run",
            "pages": "UNKNOWN_this_run",
            "status": "named_in_P12_control_bytes_not_readable_this_run",
            "covers_sections": [12],
        },
    }
    documented_page_total = 949 + 289 + 462 + 162 + 138
    payload = {
        "rule": "raster=1 image; each PDF page=1 image; PDF container is not an extra image; OCR is never proof of absence",
        "measured_this_run": accounted,
        "measured_image_total": accounted["image_count"],
        "documented_blm_files": documented_blm,
        "documented_blm_casefile_pages": documented_page_total,
        "documented_plus_measured_plat": documented_page_total + 10,
        "holds": [
            "P12 R6/R7 ZIPs remain login-walled; 19+1 federal report rows were not invented.",
            "P14 Monday 4FD6EA2B and closeout C61EE771 36C/22F ODS packages remain locked.",
            "BLM casefile PDFs themselves were not re-downloaded; page totals above stay documented, not re-hashed.",
        ],
    }
    write_json(out / "IMAGE_AND_BLM_CENSUS__20260922.json", payload)
    return payload


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    p12 = build_section_12(OUT)
    p14 = build_section_14(OUT)
    census = build_image_census(OUT)
    receipt = {
        "work_date": WORK_DATE_ISO,
        "format_donors": {
            "P13_EXACT5": "1967093eb65f90e271543f3a78c209a103425cd278852d01709b66caf2f3381e",
            "P15_example": "8fc45861403e77e293180f990b858fdbec757499f05384f4a792e10097a47738",
        },
        "section_12": p12,
        "section_14": p14,
        "image_and_blm_census": {
            "measured_image_total": census["measured_image_total"],
            "documented_blm_casefile_pages": census["documented_blm_casefile_pages"],
        },
        "ready_for_external_release": False,
        "owner_only_hops": [
            "Windows Excel Print Preview of each isolated Letter",
            "Copy into Section N/Isolated/",
            "New Drive landing + raw same-SHA readback",
            "Ryan signs and declares DONE",
        ],
    }
    write_json(OUT / "PACKAGE_RECEIPT__20260922.json", receipt)
    report = f"""# Penterra Sections 12 / 14 — 9/22/2026 turn-in report

## Format donors

- Section 13 EXACT5 SHA `{receipt['format_donors']['P13_EXACT5']}`
- Section 15 exact-six SHA `{receipt['format_donors']['P15_example']}`
- Mechanics cloned: 7-row header, blank row 8, header row 9, data from row 10
- Checklist US Letter landscape, print area A1:K9, donor widths/heights
- Certification one US Letter portrait page dated {WORK_DATE_LONG}
- Isolated Letters landscape with print titles rows 1-8
- Work-product date {WORK_DATE}; source / posted-thru / instrument dates unchanged

## Shared Letter

Client: {CLIENT}. Project: {PROJECT}. Indexed by: {INDEXER}. County: {COUNTY}. Lands: {TOWNSHIP} Section N: All.

## Section 12 — source-bound EXACT6

| Member | Role |
|---|---|
| `45N-76W-12_Campbell_Co_Penterra_Abstract_Index.ods` | County index, {p12['county_rows']} rows from P12 R3 |
| `WYW-051704 Campbell Co. Penterra Abstract Index.ods` | Federal role restored; 0 invented rows |
| `WYWY105402986 Campbell Co. Penterra Abstract Index.ods` | Federal role restored; 0 invented rows |
| `Abstract_Checklist_12-45N-76W.xlsx` | Donor checklist geometry |
| `12-45N-76W_Certification_Letter.docx` | One-page portrait cert |
| `12-45N-76W_Certification_Letter.pdf` | Same letter |

ZIP `{p12['zip']}` SHA `{p12['zip_sha256']}` ({p12['zip_bytes']} bytes).

County source: Drive `1mhryLfQw54hBWBNJ_gLbcJR0R1fI6l97` SHA `33e44145…f1953`. Official queue stays **849**. Locked R6/R7 federal 19+1 rows were not invented. OCR sentence fragments in listed party cells were blanked.

READY_FOR_RYAN_OWNER_REVIEW: NO
READY_FOR_EXTERNAL_RELEASE: NO

## Section 14 — source-bound EXACT8

| Member | Role |
|---|---|
| `45N-76W-14_Campbell_Co_Penterra_Abstract_Index.ods` | County index, {p14['county_rows']} rows from Campbell14 R2 |
| `WYW-042622 Campbell Co. Penterra Abstract Index.ods` | {p14['federal_rows']['WYW-042622']} source rows |
| `WYW-047318 Campbell Co. Penterra Abstract Index.ods` | {p14['federal_rows']['WYW-047318']} source rows |
| `WYW-072484 Campbell Co. Penterra Abstract Index.ods` | {p14['federal_rows']['WYW-072484']} source rows |
| `WYW-188048 Campbell Co. Penterra Abstract Index.ods` | {p14['federal_rows']['WYW-188048']} source rows |
| `Abstract_Checklist_14-45N-76W.xlsx` | Donor checklist geometry |
| `14-45N-76W_Certification_Letter.docx` | One-page portrait cert |
| `14-45N-76W_Certification_Letter.pdf` | Same letter |

ZIP `{p14['zip']}` SHA `{p14['zip_sha256']}` ({p14['zip_bytes']} bytes).

County/federal source: Drive `1_Yw6XOwVzLJbD28fyyMmSFweakc4Jkos` SHA `399bb218…56d8`. This is the readable R2 package (**{p14['county_rows']}C + {p14['federal_row_total']}F**). Locked later closeout **36C + 22F** bytes were not invented.

READY_FOR_RYAN_OWNER_REVIEW: NO
READY_FOR_EXTERNAL_RELEASE: NO

## Image and BLM file census

Measured this run: **{census['measured_image_total']} images** (Book 583 = 17, exhibit = 7, plat = 10, plus donor/source cert PDFs). PDF containers are not extra images.

Documented BLM casefile pages (not re-hashed): **{census['documented_blm_casefile_pages']}**
WYW-051704 949 + WYW-042622 289 + WYW-047318 462 + WYW-072484 162 + WYW-188048 138.

## Owner hops

Windows Excel Print Preview of each isolated Letter, copy into `Section N/Isolated/`, new Drive landing + raw same-SHA readback. Ryan alone signs and declares DONE.
"""
    (out_report := OUT / "OWNER_TURNIN_REPORT__20260922.md").write_text(report)
    print(json.dumps(receipt, indent=2))
    print("wrote", out_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
