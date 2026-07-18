"""End-to-end tests for the Section 32 runsheet red-team harness.

These build two small *synthetic* candidate workbooks with deliberately
planted defects (one per class the auditor must catch) and assert the harness
detects them, keeps unresolved conflicts visible, refuses unsupported
decimals, and never asserts a false current owner. No real title data is used.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from automation import section32_runsheet_red_team as rt  # noqa: E402


HEADERS = [
    "Instrument No", "Type", "Book", "Page", "Execution Date", "Record Date",
    "Grantor", "Grantee", "Interest", "Legal Description", "Section", "Tract",
    "Evidence Tier", "Source Citation",
]


def _wb(path: Path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HEADERS)
    for r in rows:
        ws.append(r)
    wb.save(path)


def _fixtures(tmp_path: Path):
    # Sheet A (Gemini master): the "cleaner" extraction, image-backed.
    a_rows = [
        ["1001", "Deed", "100", "10", "2000-01-01", "2000-01-05", "United States",
         "Alice Owner", "1/1", "SW/4 Section 32-11N-25W", "32", "SW4", "image", "img:scan_1001.tif"],
        ["1002", "Deed", "100", "20", "2001-02-01", "2001-02-10", "Alice Owner",
         "Bob Buyer", "1/2", "SW/4 Section 32-11N-25W", "32", "SW4", "image", "img:scan_1002.tif"],
        # Duplicate of 1002 within sheet A.
        ["1002", "Deed", "100", "20", "2001-02-01", "2001-02-10", "Alice Owner",
         "Bob Buyer", "1/2", "SW/4 Section 32-11N-25W", "32", "SW4", "image", "img:scan_1002.tif"],
        # Foreign section -> portfolio mixing.
        ["1003", "Deed", "100", "30", "2002-03-01", "2002-03-05", "Bob Buyer",
         "Carol Third", "1/2", "NE/4 Section 5-11N-25W", "5", "NE4", "image", "img:scan_1003.tif"],
        # Over-conveyance: Bob holds 1/2 but conveys 1/1.
        ["1004", "Assignment", "100", "40", "2003-04-01", "2003-04-10", "Bob Buyer",
         "Dan Fourth", "1/1", "SW/4 Section 32-11N-25W", "32", "SW4", "image", "img:scan_1004.tif"],
        # Unsupported decimal: interest present, no citation.
        ["1005", "Assignment", "100", "50", "2004-05-01", "2004-05-09", "Dan Fourth",
         "Eve Fifth", "0.25", "SW/4 Section 32-11N-25W", "32", "SW4", "index", ""],
        # Impossible chronology: exec after record.
        ["1006", "Deed", "100", "60", "2006-06-10", "2006-06-01", "Eve Fifth",
         "Frank Sixth", "1/4", "SW/4 Section 32-11N-25W", "32", "SW4", "image", "img:scan_1006.tif"],
    ]
    # Sheet B (Grok chained): missing 1006, party conflict on 1002, OCR-only 1004.
    b_rows = [
        ["1001", "Deed", "100", "10", "2000-01-01", "2000-01-05", "United States",
         "Alice Owner", "1/1", "SW/4 Section 32-11N-25W", "32", "SW4", "ocr", "ocr:1001"],
        # Party conflict: grantee differs and neither side is stronger here (both ocr).
        ["1002", "Deed", "100", "20", "2001-02-01", "2001-02-10", "Alice Owner",
         "Bobby Byer INCORRECT", "1/2", "SW/4 Section 32-11N-25W", "32", "SW4", "ocr", "ocr:1002"],
        ["1003", "Deed", "100", "30", "2002-03-01", "2002-03-05", "Bob Buyer",
         "Carol Third", "1/2", "NE/4 Section 5-11N-25W", "5", "NE4", "ocr", "ocr:1003"],
        ["1004", "Assignment", "100", "40", "2003-04-01", "2003-04-10", "Bob Buyer",
         "Dan Fourth", "1/1", "SW/4 Section 32-11N-25W", "32", "SW4", "ocr", "ocr:1004"],
        ["1005", "Assignment", "100", "50", "2004-05-01", "2004-05-09", "Dan Fourth",
         "Eve Fifth", "0.25", "SW/4 Section 32-11N-25W", "32", "SW4", "index", ""],
        # 1006 intentionally absent from B -> Missing Instrument.
    ]
    pa, pb = tmp_path / "gemini.xlsx", tmp_path / "grok.xlsx"
    _wb(pa, a_rows)
    _wb(pb, b_rows)
    return pa, pb


def test_end_to_end_detects_all_defect_classes(tmp_path):
    pa, pb = _fixtures(tmp_path)
    out = tmp_path / "out"
    result = rt.run(pa, pb, out, expected_section="32", expected_tract="SW4")

    cats = {d.category for d in result.defects}
    for expected in (
        "Duplicate Instrument", "Missing Instrument", "Portfolio Mixing",
        "Unsupported Interest", "Wrong Date", "Missing Source Image",
    ):
        assert expected in cats, f"missing detection: {expected} (got {sorted(cats)})"

    # Party conflict on 1002: sheet A is image-tier, sheet B is OCR-tier, so the
    # auditor corrects to the image-backed value (evidence-based correction).
    wrong_party = [d for d in result.defects if d.category == "Wrong Party"]
    assert wrong_party, "party conflict not flagged"
    assert any(d.resolution == "CORRECTED" for d in wrong_party)

    # Unresolved conflicts must stay visible somewhere (chain gap / over-conveyance).
    assert any(d.resolution == "OPEN" for d in result.defects)
    assert "Broken Chain" in cats or "Unsupported Interest" in cats


def test_outputs_written(tmp_path):
    pa, pb = _fixtures(tmp_path)
    out = tmp_path / "out"
    rt.run(pa, pb, out)
    for name in (
        "CLAUDE_SECTION32_RED_TEAM_RUNSHEET.xlsx",
        "CLAUDE_RUNSHEET_DEFECT_REGISTER.xlsx",
        "CLAUDE_CONFLICT_MATRIX.xlsx",
        "CLAUDE_COMPLETION_RECEIPT.json",
    ):
        assert (out / name).exists(), f"{name} not written"

    receipt = json.loads((out / "CLAUDE_COMPLETION_RECEIPT.json").read_text())
    assert receipt["release_status"] == "HOLD_NO_RELEASE"
    assert set(receipt["defects_by_category"]) == set(rt.DEFECTS)


def test_no_false_current_owner(tmp_path):
    pa, pb = _fixtures(tmp_path)
    out = tmp_path / "out"
    result = rt.run(pa, pb, out)
    # Chain has OPEN items / over-conveyance -> must not assert a real owner.
    assert result.current_owner.startswith("UNDETERMINED")
    assert result.acceptance["no_false_current_owner"] is True


def test_unsupported_decimal_is_dropped(tmp_path):
    pa, pb = _fixtures(tmp_path)
    out = tmp_path / "out"
    result = rt.run(pa, pb, out)
    row_1005 = next(r for r in result.retained if "1005" in r["key"])
    # The 0.25 with no citation must be refused, not carried forward.
    assert row_1005["interest"] == ""
    assert result.acceptance["no_unsupported_decimals"] is True


def test_clean_agreeing_chain_yields_owner(tmp_path):
    # A fully image-proven, non-conflicting, whole-interest chain -> named owner.
    rows = [
        ["2001", "Deed", "200", "1", "2010-01-01", "2010-01-05", "United States",
         "Pat Root", "1/1", "SW/4 Section 32-11N-25W", "32", "SW4", "image", "img:a"],
        ["2002", "Deed", "200", "2", "2011-01-01", "2011-01-05", "Pat Root",
         "Sam Final", "1/1", "SW/4 Section 32-11N-25W", "32", "SW4", "image", "img:b"],
    ]
    pa, pb = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    _wb(pa, rows)
    _wb(pb, rows)
    result = rt.run(pa, pb, tmp_path / "out", expected_section="32", expected_tract="SW4")
    assert result.current_owner == "Sam Final"
    assert all(result.acceptance.values())


def test_normalisers():
    assert rt.norm_party("Bob Buyer, LLC") == rt.norm_party("bob buyer llc")
    assert rt.parse_interest("1/2") == (0.5, True)
    assert rt.parse_interest("50%") == (0.5, True)
    assert rt.parse_interest("") == (None, False)
    assert rt.parse_interest("undivided interest") == (None, False)
    assert rt.has_section32("SW/4 Section 32-11N-25W") is True
    assert rt.has_section32("NE/4 Section 5-11N-25W") is False
