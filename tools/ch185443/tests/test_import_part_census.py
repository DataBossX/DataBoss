import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from import_part_census import apply_part_census, excel_serial


def test_excel_serial_matches_formatter():
    assert excel_serial("11/4/2024") == (datetime(2024, 11, 4) - datetime(1899, 12, 30)).days


def test_census_adds_named_section_and_fills_received_date():
    master = {
        "summary": [
            {
                "section": section,
                "substantive_display_qualified_unknown": 0,
                "administrative_rows_excluded": 0,
            }
            for section in (6, 7, 13, 18, 19, 24, 30, 31)
        ],
        "workbooks": [
            {
                "section": 13,
                "kind": "county",
                "file": "47N-77W-13_Johnson_Co_Penterra_Abstract_Index.xlsx",
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
                        "row_id": "c",
                        "values": ["Deed", "A", "B", "1", "1-1", None, None, "All of 13-47N-77W", ""],
                    }
                ],
                "row_count": 1,
            },
            {
                "section": 13,
                "kind": "federal",
                "file": "WYW-153681_Johnson_Co_Penterra_Abstract_Index.xlsx",
                "metadata": [["Lands:", "WYW-153681; T47N-R77W Section 13", ""]],
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
                        "row_id": "existing",
                        "values": [
                            "Transfer of Operating Rights (Sublease)",
                            "Kept Grantor",
                            "Kept Grantee",
                            None,
                            2,
                            excel_serial("9/1/2024"),
                            None,
                            None,
                            "Lots 5, 7 of 13-47N-77W, aol",
                            2,
                        ],
                    }
                ],
                "row_count": 1,
            },
        ],
    }
    occurrences = [
        {
            "id": "J001",
            "category": "JACKET",
            "client_index_disposition": "EXCLUDE_FROM_CLIENT_INDEX_RETAIN_IN_AUDIT",
            "start_page": 1,
            "part": 2,
            "target_legals": [],
        },
        {
            "id": "D002",
            "category": "SUBSTANTIVE_DOCUMENT",
            "client_index_disposition": "INCLUDE",
            "type": "Transfer of Operating Rights (Sublease)",
            "date_of_document": "9/1/2024",
            "received_date": "11/4/2024",
            "grantors": ["Should Not Replace"],
            "grantees": ["Should Not Replace"],
            "start_page": 2,
            "part": 2,
            "target_legals": [],
            "outside_lands": False,
        },
        {
            "id": "D019",
            "category": "SUBSTANTIVE_DOCUMENT",
            "client_index_disposition": "INCLUDE",
            "type": "Transfer of Operating Rights (Sublease)",
            "date_of_document": "3/11/2021",
            "received_date": "4/8/2021",
            "grantors": ["Example Energy, LLC", "Sample Resources Corporation"],
            "grantees": ["Beta, LLC"],
            "start_page": 19,
            "part": 2,
            "outside_lands": True,
            "target_legals": [
                {
                    "township": "47N",
                    "range": "77W",
                    "section": 13,
                    "lots_raw": "5,7,10,12",
                    "aliquot_raw": "E2SE,E2SW",
                    "depth_restriction": "Below base of the Ft Union",
                },
                {
                    "township": "47N",
                    "range": "76W",
                    "section": 6,
                    "lots_raw": "8-12,15-23",
                    "aliquot_raw": "SENW",
                    "depth_restriction": "Below base of the Ft Union",
                },
            ],
        },
        {
            "id": "D015",
            "category": "SUBSTANTIVE_DOCUMENT",
            "client_index_disposition": "INCLUDE",
            "type": "Notice",
            "date_of_document": "6/16/2022",
            "received_date": "",
            "grantors": ["Bureau of Land Management"],
            "grantees": [],
            "start_page": 15,
            "part": 2,
            "target_legals": [],
            "outside_lands": False,
        },
    ]
    receipt = apply_part_census(master, occurrences)
    assert receipt["added_count"] == 2
    assert receipt["filled_count"] == 1
    book = next(item for item in master["workbooks"] if item["section"] == 13 and item["kind"] == "federal")
    assert book["rows"][0]["values"][1] == "Kept Grantor"
    assert book["rows"][0]["values"][6] == excel_serial("11/4/2024")
    added = book["rows"][1]["values"]
    assert added[0] == "Transfer of Operating Rights (Sublease)"
    assert added[1] == "Example Energy, LLC,\nSample Resources Corporation"
    assert "Ft Union" not in added[8]
    assert added[8] == "Lots 5, 7, 10, 12; E2SE,E2SW of 13-47N-77W, aol"
    assert added[4] == 19
    assert added[9] == 2
    section6 = next(item for item in master["workbooks"] if item["section"] == 6)
    assert section6["rows"][0]["values"][8] == "Lots 8-12, 15-23; SENW of 6-47N-76W, aol"
    described = {
        "id": "D028",
        "category": "SUBSTANTIVE_DOCUMENT",
        "client_index_disposition": "INCLUDE",
        "type": "Transfer of Operating Rights (Sublease)",
        "date_of_document": "4/3/2018",
        "received_date": "5/11/2018",
        "grantors": ["John A. Example"],
        "grantees": ["Vladin, LLC"],
        "start_page": 28,
        "part": 2,
        "outside_lands": True,
        "target_legals": [
            {
                "township": "47N",
                "range": "76W",
                "section": 30,
                "description": "Lots 8,9,16,17 (W2W2)",
                "depth_restriction": "Surface to 2,500 feet",
            }
        ],
    }
    second = apply_part_census(master, [described])
    assert second["added_count"] == 1
    section30 = next(item for item in master["workbooks"] if item["section"] == 30)
    assert section30["rows"][0]["values"][8] == "Lots 8, 9, 16, 17 (W2W2) of 30-47N-76W, aol"
    assert "2,500" not in section30["rows"][0]["values"][8]
    assert "D015" in receipt["not_placed_on_a_project_section"]
    assert "J001" in receipt["not_placed_on_a_project_section"]
    summary6 = next(item for item in master["summary"] if item["section"] == 6)
    assert summary6["federal_rows"] == 1
    assert json.dumps(master["wyw153681_part2_import"])
