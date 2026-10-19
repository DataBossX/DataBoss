"""Add section applications proved by a visual case-part census.

The census JSON stays outside the repository. This module copies only
documents whose reviewed legal names a project section. Jacket, postal,
and administrative occurrences stay out. A document with no listed lands
is not copied onto a section. Depth and formation stay out of the client
legal. An existing row with the same Part and starting Page keeps its
text; a blank Rec Date is filled only when that census document states a
received date.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime
from pathlib import Path

from format_indexes import audit_workbook, substantive_headers

EXCEL_EPOCH = datetime(1899, 12, 30)
CASE_FILE = "WYW-153681_Johnson_Co_Penterra_Abstract_Index.xlsx"
PROJECT_TOWNSHIP = {
    6: "76W",
    7: "76W",
    13: "77W",
    18: "76W",
    19: "76W",
    24: "77W",
    30: "76W",
    31: "76W",
}
FEDERAL_HEADERS = [
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
]


def excel_serial(text: str | None):
    if text is None or not str(text).strip():
        return None
    month, day, year = str(text).strip().split("/")
    found = datetime(int(year), int(month), int(day))
    return (found - EXCEL_EPOCH).days


def party_cell(names) -> str | None:
    clean = [str(name).strip() for name in names or [] if str(name).strip()]
    if not clean:
        return None
    return ",\n".join(clean)


def _lot_text(raw: str) -> str:
    pieces = [piece.strip() for piece in raw.split(",") if piece.strip()]
    return "Lots " + ", ".join(pieces)


def clean_description(text: str) -> str:
    """Drop acreage. Keep lot and aliquot language from the reviewed description."""
    cleaned = re.sub(r"\(\s*[\d.]+\s*acres\s*,\s*", "(", text, flags=re.I)
    cleaned = re.sub(r",\s*[\d.]+\s*acres\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r",(?!\s)", ", ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" ,")


def _fragment(item: dict) -> str | None:
    lots = str(item.get("lots_raw") or "").strip()
    aliquot = str(item.get("aliquot_raw") or "").strip()
    if lots or aliquot:
        bits = []
        if lots:
            bits.append(_lot_text(lots))
        if aliquot:
            bits.append(aliquot)
        return "; ".join(bits)
    description = clean_description(str(item.get("description") or ""))
    return description or None


def section_legal(document: dict, section: int, township: str) -> str | None:
    hits = [
        item
        for item in document.get("target_legals") or []
        if item.get("township") == "47N" and item.get("range") == township and item.get("section") == section
    ]
    if not hits:
        return None
    fragments = []
    for item in hits:
        fragment = _fragment(item)
        if fragment and fragment not in fragments:
            fragments.append(fragment)
    if not fragments:
        return None
    legal = "; ".join(fragments) + f" of {section}-47N-{township}"
    other = bool(document.get("outside_lands")) or any(
        not (item.get("township") == "47N" and item.get("range") == township and item.get("section") == section)
        for item in document.get("target_legals") or []
    )
    if other:
        legal += ", aol"
    return legal


def _included(document: dict) -> bool:
    if document.get("category") != "SUBSTANTIVE_DOCUMENT":
        return False
    disposition = str(document.get("client_index_disposition") or "")
    return disposition == "INCLUDE" or disposition.startswith("INCLUDE")


def _number(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _find_book(master: dict, section: int):
    for workbook in master["workbooks"]:
        if workbook["section"] == section and workbook["file"] == CASE_FILE:
            return workbook
    return None


def _template(master: dict) -> dict | None:
    for workbook in master["workbooks"]:
        if workbook["file"] == CASE_FILE:
            return workbook
    return None


def _new_book(master: dict, section: int) -> dict:
    township = PROJECT_TOWNSHIP[section]
    template = _template(master)
    if template is None:
        workbook = {
            "section": section,
            "kind": "federal",
            "file": CASE_FILE,
            "metadata": [
                ["County:", "Johnson", ""],
                ["Lands:", f"WYW-153681; T47N-R{township} Section {section}", ""],
                ["Date:", "2026-10-19T00:00:00.000Z", ""],
                ["Starting Date:", None, ""],
                ["Date Posted Thru:", None, ""],
                ["Indexed By:", "Ryan Gille", ""],
                ["Project:", "Combine-Harvest CH185443 / AFE210275", ""],
            ],
            "headers": list(FEDERAL_HEADERS),
            "rows": [],
            "row_count": 0,
        }
    else:
        workbook = copy.deepcopy(template)
        workbook["section"] = section
        workbook["rows"] = []
        workbook["row_count"] = 0
        for row in workbook.get("metadata") or []:
            if row and str(row[0]).startswith("Lands"):
                row[1] = f"WYW-153681; T47N-R{township} Section {section}"
    master["workbooks"].append(workbook)
    return workbook


def _match(workbook: dict, page: int, part: int):
    headers = workbook["headers"]
    page_at = headers.index("Page")
    part_at = headers.index("Part")
    for row in workbook["rows"]:
        if _number(row["values"][page_at]) == page and _number(row["values"][part_at]) == part:
            return row
    return None


def apply_part_census(master: dict, occurrences: list[dict]) -> dict:
    added = []
    filled = []
    skipped = []
    for document in occurrences:
        if not _included(document):
            skipped.append(document.get("id"))
            continue
        page = int(document["start_page"])
        part = int(document["part"])
        placed = False
        received = excel_serial(document.get("received_date"))
        for workbook in master["workbooks"]:
            if workbook.get("file") != CASE_FILE:
                continue
            headers = workbook["headers"]
            existing = _match(workbook, page, part)
            if existing is None:
                continue
            placed = True
            rec_at = headers.index("Rec Date")
            if existing["values"][rec_at] in (None, "") and received is not None:
                existing["values"][rec_at] = received
                filled.append(
                    {"section": workbook["section"], "id": document.get("id"), "page": page, "part": part}
                )
        for section, township in PROJECT_TOWNSHIP.items():
            legal = section_legal(document, section, township)
            if legal is None:
                continue
            placed = True
            workbook = _find_book(master, section) or _new_book(master, section)
            headers = workbook["headers"]
            if _match(workbook, page, part) is not None:
                continue
            values = [None] * len(headers)
            values[headers.index("Document Type")] = document.get("type")
            values[headers.index("Grantor")] = party_cell(document.get("grantors"))
            values[headers.index("Grantee")] = party_cell(document.get("grantees"))
            values[headers.index("Page")] = page
            values[headers.index("Date of Doc")] = excel_serial(document.get("date_of_document"))
            values[headers.index("Rec Date")] = received
            values[headers.index("Legal Description")] = legal
            values[headers.index("Part")] = part
            workbook["rows"].append(
                {
                    "row_id": f"Sec{section:02d}/{CASE_FILE}#Index!{document.get('id')}",
                    "values": values,
                    "source_census_id": document.get("id"),
                }
            )
            added.append({"section": section, "id": document.get("id"), "page": page, "part": part})
        if not placed:
            skipped.append(document.get("id"))
    for workbook in master["workbooks"]:
        workbook["row_count"] = len(workbook["rows"])
    receipt = {
        "case_file": CASE_FILE,
        "source": "visual part census",
        "added_applications": added,
        "filled_received_dates": filled,
        "not_placed_on_a_project_section": sorted({item for item in skipped if item}),
        "added_count": len(added),
        "filled_count": len(filled),
    }
    master["wyw153681_part2_import"] = {
        "added_count": receipt["added_count"],
        "filled_count": receipt["filled_count"],
        "not_placed_on_a_project_section": receipt["not_placed_on_a_project_section"],
    }
    refresh_summary(master)
    return receipt


def refresh_summary(master: dict) -> None:
    by_section = {item["section"]: item for item in master.get("summary") or []}
    blanks = {section: 0 for section in PROJECT_TOWNSHIP}
    unknowns = {section: 0 for section in PROJECT_TOWNSHIP}
    populated = {section: 0 for section in PROJECT_TOWNSHIP}
    county_rows = {section: 0 for section in PROJECT_TOWNSHIP}
    federal_rows = {section: 0 for section in PROJECT_TOWNSHIP}
    federal_books = {section: 0 for section in PROJECT_TOWNSHIP}
    empty_books = {section: 0 for section in PROJECT_TOWNSHIP}
    for workbook in master["workbooks"]:
        section = workbook["section"]
        if section not in PROJECT_TOWNSHIP:
            continue
        audit = audit_workbook(workbook)
        blanks[section] += audit["blank_cells"]
        unknowns[section] += audit["unknown_cells"]
        substantive = substantive_headers(workbook["kind"], workbook["headers"])
        populated[section] += len(substantive) * audit["documents"] - audit["blank_cells"]
        if workbook["kind"] == "county":
            county_rows[section] += audit["documents"]
        else:
            federal_rows[section] += audit["documents"]
            federal_books[section] += 1
            if audit["documents"] == 0:
                empty_books[section] += 1
    summary = []
    for section in sorted(PROJECT_TOWNSHIP):
        prior = by_section.get(section) or {}
        qualified = prior.get("substantive_display_qualified_unknown") or 0
        summary.append(
            {
                "section": section,
                "county_rows": county_rows[section],
                "federal_rows": federal_rows[section],
                "federal_workbooks": federal_books[section],
                "empty_federal_workbooks": empty_books[section],
                "administrative_rows_excluded": prior.get("administrative_rows_excluded") or 0,
                "substantive_display_blanks": blanks[section],
                "substantive_display_unknown": unknowns[section],
                "substantive_display_qualified_unknown": qualified,
                "substantive_display_populated": populated[section],
                "unresolved_evidence_cells": blanks[section] + unknowns[section] + qualified,
                "source_status_counts": {
                    "unknown": unknowns[section],
                    "qualified_unknown": qualified,
                },
            }
        )
    master["summary"] = summary


def load_occurrences(path: Path) -> list[dict]:
    payload = json.loads(path.read_text())
    if isinstance(payload, dict):
        for key in ("documents", "occurrences", "records"):
            if isinstance(payload.get(key), list):
                return payload[key]
    if not isinstance(payload, list):
        raise ValueError("Census JSON must be a list of document occurrences")
    return payload


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("master_json", type=Path)
    parser.add_argument("census_json", type=Path)
    parser.add_argument("receipt_json", type=Path)
    args = parser.parse_args()
    master = json.loads(args.master_json.read_text())
    receipt = apply_part_census(master, load_occurrences(args.census_json))
    args.master_json.write_text(json.dumps(master))
    args.receipt_json.write_text(json.dumps(receipt, indent=2))
    print(json.dumps({"added": receipt["added_count"], "filled": receipt["filled_count"]}))


if __name__ == "__main__":
    main()
