import json
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_package import build
from format_indexes import excel_serial_to_date, format_date_text


def test_known_recording_date():
    assert format_date_text(24558) == "3/27/1967"
    assert excel_serial_to_date(24524) == datetime(1967, 2, 21)


def test_package_hides_unproved_search_dates_and_keeps_blm_columns(tmp_path):
    master = {
        "summary": [
            {
                "section": 24,
                "county_rows": 1,
                "federal_rows": 1,
                "federal_workbooks": 1,
                "substantive_display_blanks": 1,
                "substantive_display_unknown": 1,
                "substantive_display_qualified_unknown": 0,
                "unresolved_evidence_cells": 2,
            }
        ],
        "workbooks": [
            {
                "section": 24,
                "kind": "county",
                "file": "47N-77W-24_Johnson_Co_Penterra_Abstract_Index.xlsx",
                "metadata": [
                    ["County:", "Johnson"],
                    ["Lands:", "T47N-R77W Section 24: All"],
                    ["Date:", "2026-10-19T00:00:00.000Z"],
                    ["Starting Date:", "Available records"],
                    ["Date Posted Thru:", "Unknown"],
                    ["Indexed By:", "Ryan Gille"],
                    ["Project:", "Combine-Harvest CH185443 / AFE210275"],
                ],
                "headers": [
                    "Document Type",
                    "Grantor",
                    "Grantee",
                    "Doc No",
                    "Book-Page",
                    "Date of Doc",
                    "Rec Date",
                    "Legal Description",
                    "Comments",
                ],
                "rows": [
                    {
                        "row_id": "c1",
                        "values": [
                            "Deed",
                            "Example Energy, LLC,\nSample Resources Corporation",
                            "Unknown",
                            "100",
                            "1-1",
                            24524,
                            24558,
                            "All of 24-47N-77W, aol",
                            "",
                        ],
                    }
                ],
                "row_count": 1,
            },
            {
                "section": 24,
                "kind": "federal",
                "file": "WYW-145618_Johnson_Co_Penterra_Abstract_Index.xlsx",
                "metadata": [
                    ["County:", "Johnson"],
                    ["Lands:", "WYW-145618; T47N-R77W Section 24"],
                    ["Starting Date:", "Available records"],
                    ["Date Posted Thru:", "Unknown"],
                ],
                "headers": [
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
                ],
                "rows": [
                    {
                        "row_id": "f2",
                        "values": ["Transfer", "Alpha, LLC", "Beta, LLC", "SHOULD-CLEAR", 13, None, None, "note", "outside lands only", 10],
                    },
                    {
                        "row_id": "f1",
                        "values": [
                            "Transfer",
                            "Alpha, LLC,\nBeta, LLC",
                            "Gamma Inc.",
                            "",
                            2,
                            24558,
                            None,
                            "",
                            "Lots 2, 4 of 24-47N-77W,\nLots 1, 2 of 19-47N-76W, aol",
                            2,
                        ],
                    },
                ],
                "row_count": 2,
            },
        ],
    }
    master_path = tmp_path / "master.json"
    master_path.write_text(json.dumps(master))
    out = tmp_path / "out"
    build(master_path, out)
    folder = out / "Section 24 package 47N-77W"
    federal = folder / "WYW-145618_Johnson_Co_Penterra_Abstract_Index.xlsx"
    from openpyxl import load_workbook

    book = load_workbook(federal)
    sheet = book.active
    assert sheet["B3"].value == datetime(2026, 10, 19)
    assert sheet["B3"].number_format == "m/d/yyyy"
    assert sheet["B4"].value is None
    assert sheet["B5"].value is None
    assert sheet["J9"].value == "Part"
    assert sheet["D10"].value is None
    assert sheet["H10"].value is None
    assert sheet["E10"].value == 2
    assert sheet["J10"].value == 2
    assert sheet["E11"].value == 13
    assert sheet["J11"].value == 10
    assert "\n" in sheet["I10"].value
    ods = zipfile.ZipFile(folder / "47N-77W-24_Johnson_Co_Penterra_Abstract_Index.ods")
    root = ET.fromstring(ods.read("content.xml"))
    text = "".join(root.itertext())
    assert "2/21/1967" in text
    assert "3/27/1967" in text
    assert "Available records" not in text
    connection = sqlite3.connect(out / "CH185443_inventory_20261019.sqlite")
    documents, parts, blanks, unknowns = connection.execute(
        "SELECT documents, parts, blank_cells, unknown_cells FROM blm_files"
    ).fetchone()
    assert documents == 2
    assert parts == "2, 10"
    assert unknowns == 0
    assert blanks >= 1
