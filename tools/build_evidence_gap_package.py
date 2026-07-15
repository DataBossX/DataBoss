#!/usr/bin/env python3
"""Build a non-fabricated title-report package when source evidence is absent.

This utility is intentionally limited to documenting a blocked examination. It
does not extract instruments, calculate interests, or represent that title was
examined. Real client artifacts should be written to an ignored/private path.
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


WORKBOOK_NAMES = (
    "MASTER_DOCUMENT_LOG.xlsx",
    "MASTER_RUNSHEET.xlsx",
    "TITLE_CHAIN.xlsx",
    "OPEN_ITEMS.xlsx",
    "CONFLICT_REPORT.xlsx",
    "IMAGE_REFERENCE_INDEX.xlsx",
    "FINAL_REPORT.xlsx",
)
MARKDOWN_NAMES = (
    "QA_REPORT.md",
    "CHANGE_LOG.md",
    "FINAL_EXECUTIVE_SUMMARY.md",
)
OUTPUT_NAMES = WORKBOOK_NAMES + MARKDOWN_NAMES

BLUE = "1F4E78"
RED = "C00000"
WHITE = "FFFFFF"
PRIVATE_REPOSITORY_DIRS = ("client_work", "private_projects", "evidence", "runtime")


def _excel_text(value: str) -> str:
    """Return user-provided text that Excel cannot interpret as a formula."""
    text = str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


def _validate_output_location(output: Path) -> Path:
    """Keep client artifacts out of public portions of this repository."""
    resolved = output.expanduser().resolve()
    repository = Path(__file__).resolve().parents[1]
    try:
        relative = resolved.relative_to(repository)
    except ValueError:
        return resolved
    if not relative.parts or relative.parts[0] not in PRIVATE_REPOSITORY_DIRS:
        allowed = ", ".join(PRIVATE_REPOSITORY_DIRS)
        raise ValueError(
            f"Repository-local output must be under an ignored private directory: {allowed}"
        )
    return resolved


def _style_sheet(ws, *, freeze: str = "A2") -> None:
    ws.freeze_panes = freeze
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor=BLUE)
        cell.font = Font(color=WHITE, bold=True)
        cell.alignment = Alignment(vertical="top", wrap_text=True)
    for column in range(1, ws.max_column + 1):
        values = [str(ws.cell(row, column).value or "") for row in range(1, ws.max_row + 1)]
        ws.column_dimensions[get_column_letter(column)].width = min(
            55, max(12, max(map(len, values), default=0) + 2)
        )
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)


def _workbook(
    path: Path,
    sheets: Sequence[tuple[str, Sequence[str], Iterable[Sequence[object]]]],
) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    for name, headers, rows in sheets:
        ws = wb.create_sheet(name)
        ws.append(list(headers))
        for row in rows:
            ws.append(list(row))
        _style_sheet(ws)
    wb.save(path)


def _blocking_row(message: str, columns: int) -> tuple[str, ...]:
    return ("INSUFFICIENT EVIDENCE", message, *(["NOT VERIFIED"] * (columns - 2)))


def _document_log(path: Path) -> None:
    headers = (
        "Document Number",
        "Book",
        "Page",
        "Recording Date",
        "Execution Date",
        "Instrument Type",
        "Grantor(s)",
        "Grantee(s)",
        "Legal Description",
        "Section",
        "Township",
        "Range",
        "Quarter Calls",
        "Acreage",
        "Reservations",
        "Exceptions",
        "Assignments",
        "Releases",
        "Well Names",
        "Lease Numbers",
        "Exhibit References",
        "Notes",
        "Confidence Score",
        "Image Filename",
        "Image Number",
        "Source Path",
        "Page Count",
        "Unreadable Areas",
        "Evidence Status",
    )
    _workbook(
        path,
        [
            (
                "Document Log",
                headers,
                [
                    _blocking_row(
                        "No recorded images, PDFs, OCR, or county index files were supplied to this invocation.",
                        len(headers),
                    )
                ],
            )
        ],
    )


def _runsheet(path: Path) -> None:
    headers = (
        "Document Number",
        "Book/Page",
        "Recording Date",
        "Execution Date",
        "Instrument",
        "Grantor",
        "Grantee",
        "Legal",
        "Notes",
        "Confidence",
        "Source Image",
        "Evidence Status",
    )
    _workbook(
        path,
        [
            (
                "Runsheet",
                headers,
                [
                    _blocking_row(
                        "No instruments were supplied; none can be entered until recorded evidence is provided.",
                        len(headers),
                    )
                ],
            )
        ],
    )


CHAIN_HEADERS = (
    "Sequence",
    "From",
    "To",
    "Interest",
    "Supporting Document",
    "Recording Information",
    "Legal Description",
    "Depth/Wellbore Limitation",
    "Reservation/Reversion",
    "Source Image",
    "Evidence Confidence",
    "Status",
)


def _title_chain(path: Path) -> None:
    sheets = []
    for name in ("Fee Title", "Mineral Title", "Leasehold", "Assignments", "Overrides"):
        sheets.append(
            (
                name,
                CHAIN_HEADERS,
                [
                    _blocking_row(
                        f"{name} chain cannot be reconstructed without recorded instruments.",
                        len(CHAIN_HEADERS),
                    )
                ],
            )
        )
    _workbook(path, sheets)


def _open_item_rows(client: str) -> tuple[tuple[str, ...], ...]:
    return (
        (
            "OI-001",
            "BLOCKING",
            "Authoritative recorded-image corpus unavailable",
            "No source images, PDFs, or evidence manifest were supplied to this invocation.",
            "Provide read-only access to the complete recorded-image folder for the subject lands.",
            "OPEN ITEM",
        ),
        (
            "OI-002",
            "BLOCKING",
            "Horizon template unavailable",
            "The referenced Section 32 Horizon workbook/template was not supplied.",
            "Provide the authoritative template and its verified SHA-256 hash.",
            "OPEN ITEM",
        ),
        (
            "OI-003",
            "BLOCKING",
            "Index and protocol records unavailable",
            "No protocoled index, county export, runsheet, or image manifest was supplied.",
            "Provide all index exports and reconcile them to the image corpus.",
            "OPEN ITEM",
        ),
        (
            "OI-004",
            "BLOCKING",
            "Ownership not determinable",
            "No conveyances, reservations, probate instruments, leases, assignments, or releases were supplied.",
            "Complete image-first examination before stating any ownership, WI, NRI, RI, MRI, or ORRI.",
            "NOT VERIFIED",
        ),
        (
            "OI-005",
            "BLOCKING",
            _excel_text(f"{client} interest not determinable"),
            "No recorded evidence supporting an interest calculation was supplied to this invocation.",
            f"Trace {client} and all predecessors through recorded instruments and exact-interest calculations.",
            "NOT VERIFIED",
        ),
        (
            "OI-006",
            "BLOCKING",
            "Template compliance cannot be tested",
            "Exact formulas, styles, merged cells, print settings, and row structure cannot be inferred without the template.",
            "Run deterministic workbook comparison after the authoritative template is supplied.",
            "OPEN ITEM",
        ),
    )


def _open_items(path: Path, client: str) -> None:
    _workbook(
        path,
        [
            (
                "Open Items",
                ("Item ID", "Severity", "Issue", "Evidence", "Recommended Resolution", "Status"),
                _open_item_rows(client),
            )
        ],
    )


def _conflicts(path: Path) -> None:
    rows = (
        (
            "CF-001",
            "BLOCKING",
            "Evidence sufficiency failure",
            "Title conflicts cannot be tested because no recorded corpus was supplied.",
            "Invocation processed zero recorded images, PDFs, indexes, or title workbooks.",
            "Acquire and inventory the complete evidence set; then rerun conflict detection.",
            "INSUFFICIENT EVIDENCE",
        ),
    )
    _workbook(
        path,
        [
            (
                "Conflict Report",
                (
                    "Conflict ID",
                    "Severity",
                    "Type",
                    "Explanation",
                    "Supporting Evidence",
                    "Recommended Resolution",
                    "Status",
                ),
                rows,
            )
        ],
    )


def _image_index(path: Path) -> None:
    headers = (
        "Logical Document ID",
        "Image Filename",
        "Image Number",
        "Source Path",
        "Source SHA-256",
        "Page Number",
        "Page Count",
        "Document Number",
        "Book",
        "Page",
        "Visual Review Status",
        "OCR Status",
        "Unreadable Areas",
        "Notes",
    )
    _workbook(
        path,
        [
            (
                "Image Reference Index",
                headers,
                [
                    _blocking_row(
                        "No images were supplied to inventory, hash, group, or inspect.",
                        len(headers),
                    )
                ],
            )
        ],
    )


def _final_report(path: Path, project: dict[str, str]) -> None:
    wb = Workbook()
    title = wb.active
    title.title = "Title"
    title_rows = (
        ("TITLE REPORT — EVIDENCE NOT SUPPLIED",),
        ("Client", _excel_text(project["client"])),
        ("County", _excel_text(project["county"])),
        ("Legal", _excel_text(project["legal"])),
        ("Report Status", "INSUFFICIENT EVIDENCE — NOT A TITLE OPINION"),
        (f"{_excel_text(project['client'])} Exact Interest", "NOT VERIFIED"),
        ("Working Interest (WI)", "NOT VERIFIED"),
        ("Net Revenue Interest (NRI)", "NOT VERIFIED"),
        ("Mineral/Royalty/Override Interests", "NOT VERIFIED"),
        ("Reason", "No recorded images, indexes, or authoritative Horizon template were supplied."),
    )
    for row in title_rows:
        title.append(row)
    title.merge_cells("A1:P1")
    title["A1"].fill = PatternFill("solid", fgColor=RED)
    title["A1"].font = Font(color=WHITE, bold=True, size=14)
    title["A1"].alignment = Alignment(horizontal="center")
    for cell in title["A"][1:]:
        cell.font = Font(bold=True)
    title.column_dimensions["A"].width = 36
    title.column_dimensions["B"].width = 85
    title.freeze_panes = "A2"

    runsheet_headers = (
        "Entry No",
        "Instrument Date",
        "Recorded Date",
        "Doc Type",
        "Grantor",
        "Grantee",
        "Instrument Number",
        "Book",
        "Page",
        "Legal Description",
        "Gross Acres",
        "Conveyed Interest",
        "Retained Interest",
        "Net Mineral Acres",
        "Status",
        "Remarks",
    )
    for name in ("Runsheet", "OGL"):
        ws = wb.create_sheet(name)
        ws.append(runsheet_headers)
        ws.append(
            _blocking_row(
                "No recorded instruments available; no ownership or leasehold conclusion made.",
                len(runsheet_headers),
            )
        )
        _style_sheet(ws)
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.save(path)


def _markdown_files(output: Path, project: dict[str, str], generated: str) -> None:
    (output / "QA_REPORT.md").write_text(
        f"""# QA Report

Project: {project['legal']}, {project['county']}
Client: {project['client']}
Generated: {generated}
Release status: **BLOCKED — INSUFFICIENT EVIDENCE**

| Review | Result | Finding |
|---|---|---|
| 1 — Missing data | BLOCKED | No evidence manifest or source files were supplied to this invocation. |
| 2 — Formatting | BLOCKED | Authoritative Horizon template not supplied. |
| 3 — Evidence | BLOCKED | Zero recorded documents supplied for visual verification. |
| 4 — Ownership | BLOCKED | No ownership conclusion or decimal was calculated. |
| 5 — Lease coverage | BLOCKED | No leases, assignments, releases, or well documents available. |
| 6 — Chronology | BLOCKED | No instruments available to sequence. |
| 7 — Template compliance | BLOCKED | Exact template comparison cannot be performed. |
| 8 — Spelling | PASS (limited) | Package labels reviewed; document text unavailable. |
| 9 — Names | BLOCKED | Grantor/grantee and owner names cannot be verified. |
| 10 — Final release audit | BLOCKED | Evidence and template gates failed. |

## Invocation evidence status

- Evidence manifest supplied: No
- Recorded source files processed: 0
- Visually reviewed recorded pages: 0
- Verified instruments entered: 0

These are invocation-processing counts, not an assertion that the underlying private
project corpus contains no records.

## Ownership QA

{project['client']}'s exact interest, WI, NRI, RI, MRI, and ORRI are **NOT VERIFIED**.
No ownership statement in this package should be treated as a fact, estimate, abstract,
title opinion, or legal opinion.
""",
        encoding="utf-8",
    )
    (output / "CHANGE_LOG.md").write_text(
        f"""# Change Log

## {generated}

- Generated the package without an evidence manifest or source files.
- Recorded that no images, indexes, OCR output, or authoritative Horizon template were supplied to this invocation.
- Created the ten requested deliverables as an evidence-gap package.
- Entered no document facts, ownership chains, acreage, or interest decimals.
- Marked unsupported conclusions `NOT VERIFIED`, `OPEN ITEM`, or `INSUFFICIENT EVIDENCE`.
- Preserved the expected `Title`, `Runsheet`, `OGL` sheet order in `FINAL_REPORT.xlsx`;
  exact Horizon styling and formulas remain unverified because the template is absent.
""",
        encoding="utf-8",
    )
    (output / "FINAL_EXECUTIVE_SUMMARY.md").write_text(
        f"""# Final Executive Summary

Subject: {project['legal']}, {project['county']}
Client: {project['client']}

## Result

**{project['client']}'s exact interest is NOT VERIFIED.**

No recorded images, PDFs, county index exports, OCR results, prior title workbooks, or
authoritative Horizon template were supplied to this package-generation invocation.
Consequently, no instrument, title chain, leasehold chain, ownership fraction, WI, NRI,
RI, MRI, ORRI, acreage, depth limitation, or wellbore limitation can be established by
this package. This does not assert that the underlying private project corpus is empty.

This package documents a blocked examination. It does not estimate ownership and is not
a title opinion. Completion requires the full recorded-image corpus, index materials,
and authoritative Horizon template, followed by image-first examination and independent
quality control.
""",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate(output: Path) -> None:
    missing = [name for name in OUTPUT_NAMES if not (output / name).is_file()]
    if missing:
        raise RuntimeError(f"Missing outputs: {', '.join(missing)}")

    for name in WORKBOOK_NAMES:
        workbook = load_workbook(output / name, read_only=True, data_only=False)
        try:
            if not workbook.sheetnames:
                raise RuntimeError(f"{name} has no worksheets")
        finally:
            workbook.close()

    final_report = load_workbook(output / "FINAL_REPORT.xlsx", read_only=True)
    try:
        if final_report.sheetnames != ["Title", "Runsheet", "OGL"]:
            raise RuntimeError(
                f"Unexpected FINAL_REPORT sheet order: {final_report.sheetnames}"
            )
    finally:
        final_report.close()


def build(output: Path, project: dict[str, str], generated: str) -> None:
    output = _validate_output_location(output)
    if output.exists():
        raise FileExistsError(
            f"Output path already exists; use a new versioned directory: {output}"
        )
    output.mkdir(parents=True, exist_ok=False)
    _document_log(output / "MASTER_DOCUMENT_LOG.xlsx")
    _runsheet(output / "MASTER_RUNSHEET.xlsx")
    _title_chain(output / "TITLE_CHAIN.xlsx")
    _open_items(output / "OPEN_ITEMS.xlsx", project["client"])
    _conflicts(output / "CONFLICT_REPORT.xlsx")
    _image_index(output / "IMAGE_REFERENCE_INDEX.xlsx")
    _final_report(output / "FINAL_REPORT.xlsx", project)
    _markdown_files(output, project, generated)
    _validate(output)

    checksums = "\n".join(
        f"{_sha256(output / name)}  {name}" for name in OUTPUT_NAMES
    )
    (output / "SHA256SUMS.txt").write_text(f"{checksums}\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--client", required=True)
    parser.add_argument("--legal", required=True)
    parser.add_argument("--county", required=True)
    parser.add_argument(
        "--as-of",
        default=date.today().isoformat(),
        help="Report date (YYYY-MM-DD); defaults to the current date.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated = datetime.combine(
        date.fromisoformat(args.as_of), datetime.min.time(), tzinfo=timezone.utc
    ).isoformat()
    build(
        args.output,
        {"client": args.client, "legal": args.legal, "county": args.county},
        generated,
    )
    print(f"Created evidence-gap package at {args.output}")


if __name__ == "__main__":
    main()
