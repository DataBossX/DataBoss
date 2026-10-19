"""Five QA cycles for a CH185443 candidate package.

Cycles:
1. Source and currentness
2. Omissions and duplicates
3. Field correctness
4. LibreOffice print check when --print is set
5. ZIP bytes, SHA-256, CRC, and reopen
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import subprocess
import zipfile
from pathlib import Path

from openpyxl import load_workbook


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cycle_source(database: Path) -> list[str]:
    connection = sqlite3.connect(database)
    gates = list(connection.execute("SELECT gate, status, evidence FROM acceptance_gates ORDER BY cycle_no"))
    holds = connection.execute("SELECT COUNT(*) FROM missing_sources WHERE status != 'CLOSED'").fetchone()[0]
    posted = connection.execute(
        "SELECT COUNT(*) FROM workbook_rows WHERE date_of_doc = '10/19/2026' OR rec_date = '10/19/2026'"
    ).fetchone()[0]
    connection.close()
    lines = ["# Cycle 1 — source and currentness", ""]
    for gate, status, evidence in gates:
        lines.append(f"- {gate}: {status}. {evidence}")
    lines.append(f"- Open holds: {holds}")
    lines.append(f"- Instrument dates equal to the preparation date: {posted}")
    lines.append("- Date Posted Thru remains Unknown. No official searched-through date is claimed.")
    lines.append("")
    return lines


def cycle_duplicates(database: Path) -> list[str]:
    connection = sqlite3.connect(database)
    rows, unique_ids = connection.execute("SELECT COUNT(*), COUNT(DISTINCT row_id) FROM workbook_rows").fetchone()
    county, federal = connection.execute(
        "SELECT SUM(county_rows), SUM(federal_rows) FROM section_summary"
    ).fetchone()
    connection.close()
    lines = [
        "# Cycle 2 — omissions and duplicates",
        "",
        f"- Workbook rows: {rows}",
        f"- Distinct row ids: {unique_ids}",
        f"- County applications: {county}",
        f"- Federal applications: {federal}",
        "- R41 (566) and R45 (1,545) were not joined row by row in this session.",
        "- Duplicate binaries of the original PDFs were not re-hashed here. The parent ZIP was not re-downloaded.",
        "",
    ]
    if rows != unique_ids:
        lines.append("- FAIL: duplicate row ids.")
    else:
        lines.append("- Row ids inside this candidate are unique.")
    lines.append("")
    return lines


def cycle_fields(output: Path) -> list[str]:
    problems = []
    checked = 0
    for path in sorted(output.rglob("*.xlsx")):
        if path.name.startswith("Abstract_Checklist"):
            continue
        if "package " not in str(path.parent):
            continue
        book = load_workbook(path, data_only=False)
        sheet = book.active
        checked += 1
        headers = [sheet.cell(9, column).value for column in range(1, sheet.max_column + 1)]
        federal = "File No" in headers
        if federal and headers[-1] != "Part":
            problems.append(f"{path.name}: Part is not the last column")
        if not federal and headers != [
            "Document Type",
            "Grantor",
            "Grantee",
            "Doc No",
            "Book-Page",
            "Date of Doc",
            "Rec Date",
            "Legal Description",
            "Comments",
        ]:
            problems.append(f"{path.name}: county headers {headers}")
        if sheet["A8"].value not in (None, ""):
            problems.append(f"{path.name}: row 8 is not blank")
        if sheet["B5"].value != "Unknown":
            problems.append(f"{path.name}: Date Posted Thru is {sheet['B5'].value!r}")
        if sheet["B4"].value not in (None, ""):
            problems.append(f"{path.name}: Starting Date is not blank")
        for row in range(10, sheet.max_row + 1):
            if all(sheet.cell(row, column).value in (None, "") for column in range(1, len(headers) + 1)):
                continue
            if federal:
                if sheet.cell(row, headers.index("File No") + 1).value not in (None, ""):
                    problems.append(f"{path.name} row {row}: File No is not blank")
                if sheet.cell(row, headers.index("Comments") + 1).value not in (None, ""):
                    problems.append(f"{path.name} row {row}: Comments is not blank")
                page = sheet.cell(row, headers.index("Page") + 1).value
                part = sheet.cell(row, headers.index("Part") + 1).value
                if page not in (None, "") and not isinstance(page, int):
                    problems.append(f"{path.name} row {row}: Page is {page!r}")
                if part not in (None, "") and not isinstance(part, int):
                    problems.append(f"{path.name} row {row}: Part is {part!r}")
            else:
                comment = sheet.cell(row, headers.index("Comments") + 1).value
                if comment not in (None, "", "missing image"):
                    problems.append(f"{path.name} row {row}: Comments is {comment!r}")
    lines = ["# Cycle 3 — field correctness", "", f"- Index workbooks checked: {checked}"]
    if problems:
        lines.append(f"- FAIL: {len(problems)} problems")
        lines.extend(f"- {problem}" for problem in problems[:50])
    else:
        lines.append("- Candidate field rules passed on the formatted workbooks.")
    lines.append("")
    return lines


def cycle_print(output: Path, enabled: bool) -> list[str]:
    lines = ["# Cycle 4 — print and style", ""]
    if not enabled:
        lines.append("- Not run. Pass --print to convert workbooks with LibreOffice.")
        lines.append("- Excel and Acrobat on the Windows PC were not available.")
        lines.append("")
        return lines
    soffice = "soffice"
    rendered = 0
    failures = []
    for path in sorted(output.rglob("*.xlsx")):
        if "package " not in str(path.parent):
            continue
        target = path.parent / "_print"
        target.mkdir(exist_ok=True)
        result = subprocess.run(
            [soffice, "--headless", "--norestore", "--convert-to", "pdf", "--outdir", str(target), str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        pdf = target / (path.stem + ".pdf")
        if result.returncode != 0 or not pdf.exists():
            failures.append(path.name)
            continue
        rendered += 1
        # Media box width greater than height means landscape.
        raw = pdf.read_bytes()
        marker = raw.find(b"/MediaBox")
        if marker == -1:
            failures.append(f"{path.name}: no MediaBox")
    lines.append(f"- LibreOffice PDFs written: {rendered}")
    if failures:
        lines.append(f"- FAIL: {len(failures)}")
        lines.extend(f"- {item}" for item in failures[:30])
    else:
        lines.append("- LibreOffice converted the index and checklist workbooks in this candidate.")
        lines.append("- This is not Excel or Acrobat parity.")
    lines.append("")
    return lines


def cycle_zip(output: Path) -> list[str]:
    lines = ["# Cycle 5 — ZIP, SHA-256, CRC, and reopen", ""]
    for path in sorted(output.glob("*.zip")):
        digest = sha256_file(path)
        try:
            archive = zipfile.ZipFile(path)
            bad = archive.testzip()
            members = len(archive.namelist())
            archive.close()
            state = "reopen ok" if bad is None else f"bad member {bad}"
        except zipfile.BadZipFile as exc:
            members = 0
            state = f"FAIL {exc}"
        lines.append(f"- `{path.name}` bytes={path.stat().st_size} sha256={digest} members={members} {state}")
    lines.append("")
    return lines


def run(output: Path, do_print: bool) -> Path:
    database = output / "CH185443_inventory_20261019.sqlite"
    lines = ["# CH185443 QA cycles — 10/19/2026", "", "Candidate only. Not an acceptance.", ""]
    lines.extend(cycle_source(database))
    lines.extend(cycle_duplicates(database))
    lines.extend(cycle_fields(output))
    lines.extend(cycle_print(output, do_print))
    lines.extend(cycle_zip(output))
    report = output / "QA_CYCLES_20261019.md"
    report.write_text("\n".join(lines))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args()
    print(run(args.output, args.print))


if __name__ == "__main__":
    main()
