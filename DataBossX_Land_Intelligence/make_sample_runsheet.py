"""Generate a realistic sample runsheet for Section 31-12N-24W.

Writes ``data/input/sample_runsheet.xlsx`` so the pipeline can be exercised
end to end without a proprietary runsheet. The sample deliberately includes:

* Tract 1 -- a clean lease-and-convey chain where the OGL number carries down
  beside both leased owners (the "Tract 1 pattern", rule 10).
* Tract 2 -- an assignment (ASSN) of the lease between operators, exercising
  rule 9 (conveyance type ASSN) and rule 8 (no book/page in the OGL field).
* Tract 3 -- an intentional shortfall (an unaccounted interest) so the
  self-healing loop must close it with a NOTED assumption and a yellow flag.

Tract acreage is 160 ac per tract (a quarter section).
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

HEADERS = [
    "Tract", "Instrument No.", "Date", "Doc Type", "Grantor", "Grantee",
    "Book", "Page", "Legal Description", "Gross Acres", "Interest",
    "OGL No.", "Notes",
]

ROWS = [
    # --- Tract 1: root -> two grantees, both leased under OGL-101 ----------
    ["1", "2018-000101", "01/10/2018", "MD", "STATE OF OKLAHOMA",
     "A. HOLLIS", "1201", "045", "NE/4 Sec 31-12N-24W", "160", "ALL",
     "", "Patent / root ownership of NE/4."],
    ["1", "2019-000210", "03/05/2019", "OGL", "A. HOLLIS",
     "HORIZON OPERATING LLC", "1240", "112", "NE/4 Sec 31-12N-24W", "", "",
     "OGL-101", "Oil & gas lease covering all of Tract 1."],
    ["1", "2020-000330", "06/12/2020", "WD", "A. HOLLIS",
     "B. CALLAHAN", "1288", "201", "N/2 NE/4 Sec 31-12N-24W", "80", "1/2",
     "", "Conveys undivided 80 ac; OGL-101 follows the acreage."],

    # --- Tract 2: root -> grantee leased, then lease ASSIGNED to new op ----
    ["2", "2017-000090", "02/02/2017", "MD", "STATE OF OKLAHOMA",
     "C. REYNOLDS", "1150", "010", "NW/4 Sec 31-12N-24W", "160", "ALL",
     "", "Patent / root ownership of NW/4."],
    ["2", "2019-000455", "04/18/2019", "OGL", "C. REYNOLDS",
     "APEX ENERGY INC", "1255", "088", "NW/4 Sec 31-12N-24W", "", "",
     "OGL-207", "Oil & gas lease covering all of Tract 2."],
    ["2", "2021-000512", "09/01/2021", "ASSN", "APEX ENERGY INC",
     "HORIZON OPERATING LLC", "1330", "410", "NW/4 Sec 31-12N-24W", "", "",
     "OGL-207", "Assignment of OGL-207; operator change only (bk 1330/410)."],

    # --- Tract 3: lease with a MISSING OGL number -> examiner-review flag ---
    ["3", "2016-000075", "05/20/2016", "MD", "STATE OF OKLAHOMA",
     "D. WHITFIELD", "1090", "300", "SE/4 Sec 31-12N-24W", "160", "ALL",
     "", "Patent / root ownership of SE/4."],
    ["3", "2019-000610", "08/14/2019", "OGL", "D. WHITFIELD",
     "SUMMIT RESOURCES LLC", "1291", "022", "SE/4 Sec 31-12N-24W", "", "",
     "", "Lease recorded but OGL number missing from runsheet -> review."],
    ["3", "2020-000640", "07/07/2020", "WD", "D. WHITFIELD",
     "E. MORGAN", "1300", "150", "S/2 SE/4 Sec 31-12N-24W", "120", "3/4",
     "", "Conveys 120 ac; D. WHITFIELD retains 40 ac. Lease burden follows."],
]


def main(out_path: str | Path = None) -> str:
    out_path = Path(out_path) if out_path else Path(__file__).parent / "data" / "input" / "sample_runsheet.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Runsheet"
    ws.append(HEADERS)
    for r in ROWS:
        ws.append(r)
    wb.save(out_path)
    return str(out_path)


if __name__ == "__main__":
    p = main()
    print(f"Wrote sample runsheet: {p}")
