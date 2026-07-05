"""Generate realistic sample Section 31 inputs to exercise the pipeline.

Writes two candidate workbooks (one richer than the other) plus a runsheet into
a target folder's ``_candidate_workbooks`` so a full pipeline run has something
to find, rank, merge, crosswalk, and export. For local testing only.
"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook


def _wb(path: Path, sheets: dict):
    wb = Workbook()
    wb.remove(wb.active)
    for name, (headers, rows) in sheets.items():
        ws = wb.create_sheet(name[:31])
        ws.append(headers)
        for r in rows:
            ws.append(r)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))


def main(root: str):
    inbox = Path(root) / "_candidate_workbooks"

    # Rich base workbook.
    _wb(inbox / "Section 31-12N-24W Roger Mills Title FINAL.xlsx", {
        "Tract & Title Ownership": (
            ["Tract", "Legal Description", "Owner Name", "Owner Address",
             "Gross Acres", "Net Mineral Acres", "Mineral Interest",
             "Royalty", "Lease Status", "Lessee", "OGL Number"],
            [
                ["1", "NE/4", "John A. Rancher", "PO Box 12, Cheyenne OK 73628",
                 160, 40, "1/4", "3/16", "Leased", "Apex Oil", "OGL-1001"],
                ["2", "NW/4", "Mary Beth Owner Trust", "100 Main St, Elk City OK",
                 160, 80, "1/2", "1/8", "Leased", "Apex Oil", ""],
                ["3", "SW/4 of SW/4", "Estate of H. Landman", "unknown",
                 40, 40, "1/1", "", "Open", "", ""],
            ],
        ),
        "Leasehold WI": (
            ["OGL Number", "Tract", "WI Owner", "Working Interest", "NRI",
             "Assignment Chain", "Effective Date", "Status"],
            [
                ["OGL-1001", "1", "Apex Oil", "0.75", "0.60",
                 "Original Lessee Apex Oil then Farmout to Bravo Energy",
                 "2023-04-01", "Leased"],
                ["OGL-1001", "1", "Bravo Energy", "0.25", "0.20",
                 "Apex Oil -> Bravo Energy", "2023-06-15", "Leased"],
            ],
        ),
        "OGL Register": (
            ["OGL Number", "Lessor", "Lessee", "Instrument Date",
             "Recorded Date", "Book", "Page", "Legal Description",
             "Gross Acres", "Royalty", "Primary Term", "Status"],
            [
                ["OGL-1001", "John A. Rancher", "Apex Oil", "2023-03-15",
                 "2023-03-20", "512", "88", "NE/4", 160, "3/16", "3 years",
                 "Active"],
                ["OGL-1002", "Mary Beth Owner Trust", "Apex Oil", "2023-05-01",
                 "2023-05-05", "513", "12", "NW/4", 160, "1/8", "3 years",
                 "Active"],
            ],
        ),
        "Wells": (
            ["API", "Well Name", "Operator", "Status", "Formation",
             "Section", "Township", "Range"],
            [["35-129-24567", "Rancher 31-1H", "Apex Oil", "Producing",
              "Marmaton", "31", "12N", "24W"]],
        ),
    })

    # Thinner second workbook that fills a gap (address for tract 3 owner).
    _wb(inbox / "roger mills draft copy.xlsx", {
        "Owners": (
            ["Owner Name", "Legal Description", "Owner Address", "Net Mineral Acres"],
            [["Estate of H. Landman", "SW/4 SW/4",
              "c/o Probate Court, Roger Mills County", 40]],
        ),
    })

    # Runsheet with the controlling legal descriptions + OGL notes.
    _wb(inbox / "Section 31 Runsheet.xlsx", {
        "Runsheet": (
            ["Entry", "Instrument Date", "Recorded Date", "Doc Type",
             "Grantor", "Grantee", "Instrument Number", "Book", "Page",
             "Legal Description", "OGL", "Notes"],
            [
                ["1", "2023-03-15", "2023-03-20", "Oil & Gas Lease",
                 "John A. Rancher", "Apex Oil", "2023-000123", "512", "88",
                 "Northeast Quarter (NE/4)", "OGL-1001", "primary term 3 yrs"],
                ["2", "2023-05-01", "2023-05-05", "Oil & Gas Lease",
                 "Mary Beth Owner Trust", "Apex Oil", "2023-000145", "513",
                 "12", "Northwest Quarter", "OGL-1002", "1/8 royalty"],
                ["3", "2020-01-10", "2020-01-12", "Mineral Deed",
                 "H. Landman", "Estate of H. Landman", "2020-000009", "480",
                 "5", "South Half of the Southwest Quarter (S/2 SW/4)", "",
                 "unleased"],
            ],
        ),
    })
    print(f"Sample inputs written to {inbox}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
