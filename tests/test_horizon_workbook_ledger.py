"""Penterra workbook projection does not invent cells or complete a package."""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pytest

from horizon.package_finish import run_finish
from horizon.reextraction_gate import assess_ledger, parse_ledger_export
from horizon.workbook_ledger import (
    WorkbookLedgerError,
    workbook_to_occurrence_packet,
    workbook_to_tract_export,
)


PENTERRA_HEADERS = [
    "Document Type",
    "Grantor",
    "Grantee",
    "Doc No",
    "Book-Page",
    "Date of Doc",
    "Rec Date",
    "Legal Description",
    "Comments",
]


def _penterra(path: Path, *, bare: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Index"
    for _ in range(7):
        sheet.append(["SYNTH"])
    sheet.append(PENTERRA_HEADERS)
    sheet.append(
        [
            "Mineral Deed",
            "SYNTH ALPHA LLC" if not bare else "",
            "SYNTH BETA LLC" if not bare else "",
            "2026-09901",
            "",
            "1/1/2026",
            "1/2/2026" if not bare else "",
            "SYNTH TRACT 15-45N-76W",
            "",
        ]
    )
    workbook.save(path)
    workbook.close()


def test_workbook_projection_is_checkable_without_inventing_bookpage(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "index.xlsx"
    _penterra(workbook)
    export = workbook_to_tract_export(workbook, packet_id="SECTION15-WORKBOOK")
    assert export["rows"][0]["bookpage"] == ""
    assert export["rows"][0]["docno"] == "2026-09901"
    assert export["rows"][0]["page"] == 9
    packet_id, rows = parse_ledger_export(export)
    receipt = assess_ledger(packet_id, rows)
    assert receipt.technical_pass is True
    assert receipt.bare_docno_count == 0
    occ = workbook_to_occurrence_packet(workbook, packet_id="SECTION15-WORKBOOK")
    assert occ["occurrences"][0]["risk"] == "novel"
    assert occ["occurrences"][0]["fields"]["recorded_date"] == "1/2/2026"


def test_bare_docno_workbook_fails_reextraction(tmp_path: Path) -> None:
    workbook = tmp_path / "bare.xlsx"
    _penterra(workbook, bare=True)
    export = workbook_to_tract_export(workbook, packet_id="SECTION11-WORKBOOK")
    _packet_id, rows = parse_ledger_export(export)
    receipt = assess_ledger("SECTION11-WORKBOOK", rows)
    assert receipt.technical_pass is False
    assert receipt.bare_docno_count == 1
    occ = workbook_to_occurrence_packet(workbook, packet_id="SECTION11-WORKBOOK")
    assert occ["occurrences"][0]["risk"] == "high_risk"


def test_empty_workbook_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "empty.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.title = "Index"
    workbook.save(path)
    workbook.close()
    with pytest.raises(WorkbookLedgerError, match="no populated"):
        workbook_to_tract_export(path, packet_id="SECTION15-WORKBOOK")


def test_finish_projects_workbook_when_crops_are_absent(tmp_path: Path) -> None:
    workbook = tmp_path / "index.xlsx"
    _penterra(workbook)
    receipt = run_finish(sections=[15], workbook=workbook)
    assert receipt.packages_complete is False
    names = {gate.name: gate for gate in receipt.gates}
    assert names["reextraction"].technical_pass is True
    assert names["reextraction"].detail["built_from"] == "workbook"
    assert names["occurrence_ledger"].technical_pass is True
    assert names["occurrence_ledger"].detail["built_from"] == "workbook"
