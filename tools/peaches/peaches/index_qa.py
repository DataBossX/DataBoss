"""Structural QA for county (9-column) and federal (10-column) index workbooks.

Checks executed (and only these are reported):
- row 8 blank; row 9 headers vs the expected schema for the detected kind
- data begins at row 10; blank rows inside the data region
- duplicate (Doc No, Book-Page) keys [county]
- near-duplicate (Page, Part, Date of Doc) keys [federal]
- UNKNOWN / blank census by column
- Comments violations (county: anything other than blank or exactly
  'missing image'; federal: any non-blank Comments or File No cell)
- Page / Part scalar checks [federal]
- date-format violations in Date of Doc / Rec Date (M/D/YYYY, UNKNOWN, blank)
- sort order by (Book, Page) numeric where Book-Page parses [county]

CLI: python -m peaches.index_qa <workbook> <outdir>
Writes index_qa_<stem>.json and findings_<stem>.csv into <outdir>.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

from . import wb

DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
RANGE_RE = re.compile(r"\d+\s*[-–,]\s*\d+")
BOOKPAGE_RE = re.compile(r"^\s*([0-9A-Za-z]+)[-\s]+(\d+)\s*$")
MAX_FINDING_ROWS = 1000

# Column indexes (0-based) per kind.
COLS = {
    "county": {"doc_type": 0, "grantor": 1, "grantee": 2, "doc_no": 3,
               "book_page": 4, "date_of_doc": 5, "rec_date": 6,
               "legal": 7, "comments": 8},
    "federal": {"doc_type": 0, "grantor": 1, "grantee": 2, "file_no": 3,
                "page": 4, "date_of_doc": 5, "rec_date": 6,
                "comments": 7, "legal": 8, "part": 9},
}


def _cell(grid, r, c):
    if 0 <= r < len(grid) and 0 <= c < len(grid[r]):
        return (grid[r][c] or "").strip()
    return ""


def _is_unknown(text):
    return text.strip().upper() == "UNKNOWN"


def _contains_unknown(text):
    return "UNKNOWN" in text.strip().upper()


def _date_ok(text):
    if not text or _contains_unknown(text):
        return True
    m = DATE_RE.match(text)
    if not m:
        return False
    month, day = int(m.group(1)), int(m.group(2))
    return 1 <= month <= 12 and 1 <= day <= 31


def detect_kind(headers):
    norm = [wb._norm(h) for h in headers]
    county = [wb._norm(h) for h in wb.COUNTY_HEADERS]
    federal = [wb._norm(h) for h in wb.FEDERAL_HEADERS]
    if norm[:len(county)] == county:
        return "county", True
    if norm[:len(federal)] == federal:
        return "federal", True
    c_score = sum(1 for i, h in enumerate(county)
                  if i < len(norm) and norm[i] == h)
    f_score = sum(1 for i, h in enumerate(federal)
                  if i < len(norm) and norm[i] == h)
    return ("county" if c_score >= f_score else "federal"), False


def qa_workbook(path):
    sheet_name, grid = wb.read_index_sheet(path)
    findings = []

    def finding(severity, check, detail, row=None, col=None):
        findings.append({
            "severity": severity, "check": check,
            "row": "" if row is None else row,
            "col": "" if col is None else col,
            "detail": detail,
        })

    headers = [_cell(grid, 8, c) for c in range(10)]
    kind, schema_match = detect_kind(headers)
    schema = wb.COUNTY_HEADERS if kind == "county" else wb.FEDERAL_HEADERS
    cols = COLS[kind]
    if not schema_match:
        finding("HIGH", "SCHEMA_MISMATCH",
                "row 9 headers %r do not exactly match the %s schema %r"
                % (headers[:len(schema)], kind, schema))
    row8_blank = all(not _cell(grid, 7, c) for c in range(12))
    if not row8_blank:
        finding("MEDIUM", "ROW8_NOT_BLANK",
                "row 8 contains content: %r"
                % ([_cell(grid, 7, c) for c in range(10)],))

    last = len(grid) - 1
    while last >= 9 and not any(_cell(grid, last, c) for c in range(12)):
        last -= 1
    data_row_numbers = []
    blank_inside = 0
    for r in range(9, last + 1):
        if any(_cell(grid, r, c) for c in range(12)):
            data_row_numbers.append(r + 1)  # 1-based sheet row
        else:
            blank_inside += 1
    if blank_inside:
        finding("LOW", "BLANK_ROWS_IN_DATA",
                "%d fully blank rows inside the data region" % blank_inside)

    # Census by schema column.
    census = {}
    for name, idx in cols.items():
        header = schema[idx] if idx < len(schema) else name
        entry = {"blank": 0, "unknown": 0, "unknown_qualified": 0, "populated": 0}
        for r in range(9, last + 1):
            if not any(_cell(grid, r, c) for c in range(12)):
                continue
            v = _cell(grid, r, idx)
            if not v:
                entry["blank"] += 1
            elif _is_unknown(v):
                entry["unknown"] += 1
            elif _contains_unknown(v):
                entry["unknown_qualified"] += 1
            else:
                entry["populated"] += 1
        census[header] = entry

    duplicates = {"keys": 0, "extra_rows": 0}
    near_duplicates = {"keys": 0, "extra_rows": 0}
    if kind == "county":
        seen = {}
        for r in range(9, last + 1):
            key = (_cell(grid, r, cols["doc_no"]).upper(),
                   _cell(grid, r, cols["book_page"]).upper())
            if not any(key):
                continue
            if key in seen:
                duplicates["extra_rows"] += 1
                if seen[key] == 1:
                    duplicates["keys"] += 1
                    finding("HIGH", "DUPLICATE_KEY",
                            "duplicate (Doc No, Book-Page) %r first at row %d, "
                            "again at row %d" % (key, seen[key], r + 1),
                            row=r + 1)
                seen[key] += 1
            else:
                seen[key] = 1
    else:
        seen = {}
        for r in range(9, last + 1):
            key = (_cell(grid, r, cols["page"]),
                   _cell(grid, r, cols["part"]),
                   _cell(grid, r, cols["date_of_doc"]))
            if not any(key):
                continue
            if key in seen:
                near_duplicates["extra_rows"] += 1
                if seen[key] == 1:
                    near_duplicates["keys"] += 1
                    finding("MEDIUM", "NEAR_DUPLICATE_KEY",
                            "repeated (Page, Part, Date of Doc) %r first at "
                            "row %d, again at row %d" % (key, seen[key], r + 1),
                            row=r + 1)
                seen[key] += 1
            else:
                seen[key] = 1

    comments_violations = 0
    file_no_violations = 0
    page_part_violations = 0
    date_violations = 0
    for r in range(9, last + 1):
        if not any(_cell(grid, r, c) for c in range(12)):
            continue
        comment = _cell(grid, r, cols["comments"])
        if kind == "county":
            if comment and comment.lower() != "missing image":
                comments_violations += 1
                finding("MEDIUM", "COMMENTS_VIOLATION",
                        "county Comments must be blank or exactly "
                        "'missing image'; found %r" % comment,
                        row=r + 1, col="Comments")
        else:
            if comment:
                comments_violations += 1
                finding("MEDIUM", "COMMENTS_VIOLATION",
                        "federal Comments must be blank; found %r" % comment,
                        row=r + 1, col="Comments")
            file_no = _cell(grid, r, cols["file_no"])
            if file_no:
                file_no_violations += 1
                finding("MEDIUM", "FILE_NO_NOT_BLANK",
                        "federal File No must be blank; found %r" % file_no,
                        row=r + 1, col="File No")
            for col_name in ("page", "part"):
                v = _cell(grid, r, cols[col_name])
                if v and not _contains_unknown(v) and not v.isdigit():
                    page_part_violations += 1
                    finding("MEDIUM", "PAGE_PART_NOT_SCALAR",
                            "%s must be one integer or UNKNOWN/blank; "
                            "found %r" % (col_name.title(), v),
                            row=r + 1, col=col_name.title())
        for col_name in ("date_of_doc", "rec_date"):
            v = _cell(grid, r, cols[col_name])
            if not _date_ok(v):
                date_violations += 1
                finding("MEDIUM", "DATE_FORMAT",
                        "%s value %r is not M/D/YYYY, UNKNOWN or blank"
                        % (col_name, v), row=r + 1, col=col_name)

    sort_violations = None
    if kind == "county":
        sort_violations = 0
        prev = None
        for r in range(9, last + 1):
            raw = _cell(grid, r, cols["book_page"])
            m = BOOKPAGE_RE.match(raw)
            if not m:
                continue
            cur = (m.group(1).upper(), int(m.group(2)))
            if prev is not None and cur < prev[0]:
                sort_violations += 1
                finding("LOW", "SORT_ORDER",
                        "Book-Page %r at row %d sorts before previous %r "
                        "at row %d" % (raw, r + 1, prev[1], prev[2]),
                        row=r + 1, col="Book-Page")
            prev = (cur, raw, r + 1)

    result = {
        "file": os.path.basename(path),
        "path": os.path.abspath(path),
        "sheet": sheet_name,
        "kind": kind,
        "schema_match": schema_match,
        "headers_row9": headers[:len(schema)],
        "row8_blank": row8_blank,
        "data_first_row": 10,
        "data_row_count": len(data_row_numbers),
        "census": census,
        "unknown_total": sum(e["unknown"] for e in census.values()),
        "unknown_qualified_total": sum(
            e["unknown_qualified"] for e in census.values()),
        "duplicates": duplicates,
        "near_duplicates": near_duplicates,
        "comments_violations": comments_violations,
        "file_no_violations": file_no_violations,
        "page_part_violations": page_part_violations,
        "date_violations": date_violations,
        "sort_violations": sort_violations,
        "findings": findings,
    }
    return result


def write_outputs(result, outdir):
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(result["file"])[0]
    json_path = os.path.join(outdir, "index_qa_%s.json" % stem)
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    csv_path = os.path.join(outdir, "findings_%s.csv" % stem)
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["severity", "check", "row", "col", "detail"])
        writer.writeheader()
        for f in result["findings"][:MAX_FINDING_ROWS]:
            writer.writerow(f)
    return json_path, csv_path


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python -m peaches.index_qa <workbook> <outdir>",
              file=sys.stderr)
        return 2
    result = qa_workbook(argv[0])
    write_outputs(result, argv[1])
    print("index_qa: %s (%s, %d data rows, %d findings) -> %s"
          % (result["file"], result["kind"], result["data_row_count"],
             len(result["findings"]), argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
