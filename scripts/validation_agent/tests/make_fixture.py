"""Synthetic test-workbook builder.

IMPORTANT: every value produced here is SYNTHETIC TEST DATA invented purely to
exercise the validation engine.  None of it represents a real tract, lease,
well, or chain of title.  The engine is data-driven; real runs operate on real
examiner-supplied workbooks.  This module exists so the test-suite has a
deterministic input without fabricating anything that could be mistaken for a
legal fact.

Two scenarios are provided:

    build_certifiable_workbook  -- clean data whose only defect is a hardcoded
        acreage total that *should* be a formula.  The loop should repair it at
        the XML level, recalculate, and certify.

    build_escalation_workbook   -- adds a probate/heirship transfer with no
        recorded instrument (a vesting gap).  The loop must halt and escalate
        without inventing the missing probate.
"""

from __future__ import annotations

from pathlib import Path

# Net-acre split across ten tracts that foots to exactly 637.42 (test figure).
_TRACT_ACRES = [63.74, 63.74, 63.74, 63.74, 63.74,
                63.74, 63.74, 63.74, 63.74, 63.76]
_WRONG_TOTAL = 600.00  # deliberately hardcoded wrong; components foot to 637.42
_DEPTH = "SURFACE TO 8000"


def _add_sheet(wb, title, rows):
    ws = wb.create_sheet(title=title)
    for r in rows:
        ws.append(r)
    return ws


def _base_workbook():
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)  # drop the default empty sheet

    # 10 detail tract tabs (satisfy the classification gate's tract count).
    for i in range(1, 11):
        _add_sheet(wb, f"Tract {i}",
                   [["Tract", "Legal Description"],
                    [i, f"TEST TRACT {i} (synthetic)"]])

    # Tract summary: the acreage footing lives here; TOTAL is hardcoded wrong.
    summary_rows = [["Tract", "Net Acres", "OGL"]]
    for i, acres in enumerate(_TRACT_ACRES, start=1):
        lease = "L-001" if i <= 5 else "L-002"
        summary_rows.append([i, acres, lease])
    summary_rows.append(["TOTAL", _WRONG_TOTAL, ""])
    _add_sheet(wb, "Tract Summary", summary_rows)

    # OGL register.
    _add_sheet(wb, "OGL Register",
               [["OGL", "Lessor", "Lessee", "Depth", "Book", "Page"],
                ["L-001", "ALICE", "OPERATOR X", _DEPTH, "5", "100"],
                ["L-002", "BOB", "OPERATOR Y", _DEPTH, "6", "110"]])

    # Working interest.
    _add_sheet(wb, "Working Interest",
               [["OGL", "Owner", "WI", "Depth"],
                ["L-001", "OPERATOR X", "0.75", _DEPTH],
                ["L-002", "OPERATOR Y", "0.75", _DEPTH]])

    # Wells (an active well to support any HBP claim).
    _add_sheet(wb, "Wells",
               [["Well", "Status"],
                ["TEST WELL 1-31", "Active"]])

    # Exceptions / curative (benign HBP claim, backed by the active well).
    _add_sheet(wb, "Exceptions",
               [["Requirement", "Note"],
                ["HBP verification",
                 "Lease held by production via active TEST WELL 1-31."]])
    return wb


def _clean_runsheet_rows():
    # Continuous chain, balanced interest, every row sourced.
    return [
        ["Grantor", "Grantee", "Conveyed", "Retained", "Grantor Interest",
         "Instrument Type", "Book", "Page"],
        ["US PATENT", "ALICE", "1", "0", "1", "Patent", "1", "1"],
        ["ALICE", "BOB", "1/2", "1/2", "1", "Warranty Deed", "2", "10"],
        ["BOB", "CAROL", "1/2", "0", "1/2", "Warranty Deed", "3", "20"],
    ]


def build_certifiable_workbook(path: str | Path) -> Path:
    wb = _base_workbook()
    _add_sheet(wb, "Runsheet", _clean_runsheet_rows())
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    wb.save(p)
    return p


def build_escalation_workbook(path: str | Path) -> Path:
    wb = _base_workbook()
    rows = _clean_runsheet_rows()
    # A probate/heirship transfer whose grantor was never vested and which has
    # NO recorded instrument -- a mandatory escalation the system must not repair.
    rows.append(["ESTATE OF ZED", "EVE", "1/2", "0", "1/2", "Probate", "", ""])
    _add_sheet(wb, "Runsheet", rows)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    wb.save(p)
    return p
