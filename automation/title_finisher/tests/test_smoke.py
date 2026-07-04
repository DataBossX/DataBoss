"""Offline smoke tests — no network. Run: python -m pytest automation/title_finisher/tests"""
import os, glob
from titlefinisher.workbook.reader import build_worklist, worklist_summary
from titlefinisher.workbook.auditor import audit
from titlefinisher.ocr.instrument_parser import parse_index_page, parse_instrument
from titlefinisher.resolve.gap_resolver import find_source_in, toks


def test_parse_index_page():
    text = ("31 007065 R MICHAEL LORTZ LARIAT PETROLEUM INC ASGT ne nw se sw 001608\n"
            "03/15/2000 Legal S31T12N R24W E2 NW 0038")
    recs = parse_index_page(text)
    assert recs and recs[0]["doc"] == "007065"
    assert recs[0]["type"] == "ASGT"


def test_parse_instrument_fraction():
    r = parse_instrument("does hereby grant an undivided 1/2 interest in the minerals, "
                         "reserving unto grantor a 1/16 royalty")
    assert abs(r["fraction"] - 0.5) < 1e-9
    assert r["reserved"] is True


def test_source_in_match():
    rows = [(71, "1978-002585", "Mineral Deed", "237/376", "1978-04-03",
             "someone", "Billy W. Bain")]
    hit = find_source_in("Billy W. Bain (a/k/a Billy Wayne Bain)", rows, [], convey_year=1983)
    assert hit and hit["instrument"] == "1978-002585"


def test_source_in_rejects_later_acquisition():
    rows = [(466, "2014-003089", "Mineral Deed", "2251/529", "2014",
             "x", "Luther Ervin Thurman and Veronica Gentry Thurman")]
    # conveyance in 1974 cannot be sourced by a 2014 acquisition
    hit = find_source_in("L. E. Thurman and Veronica Thurman, HW", rows, [], convey_year=1974)
    assert hit is None


def test_toks_stopwords():
    assert "llc" not in toks("Payday Holdings, LLC")
    assert "payday" in toks("Payday Holdings, LLC")


def test_worklist_and_audit_if_workbook_present():
    wb = (glob.glob("data/*NHE*.xlsx") or glob.glob("data/*.xlsx"))
    if not wb:
        return  # optional: only runs when a workbook is dropped in ./data
    items = build_worklist(wb[0])
    summ = worklist_summary(items)
    assert isinstance(summ, dict) and sum(summ.values()) > 0
    # self-comparison: structure + parts checks must pass (footing may not, on a raw base)
    ok, issues, notes = audit(wb[0], wb[0])
    assert any("19-sheet structure identical" in n for n in notes)
    assert any("zip parts identical" in n for n in notes)


def test_source_in_rejects_false_positives():
    # single shared given-name / generic word must NOT match
    assert find_source_in("Hazel A. Hamilton",
        [(1,"1953-000498","Warranty Deed","D67/159","1953","x","W. L. Ayers and Hazel Ayers")],
        [], convey_year=1990) is None
    assert find_source_in("John W. Bain",
        [(1,"1907-000709","Deed","D9/303","1907","x","John G. Lancaster")],
        [], convey_year=2005) is None
    assert find_source_in("Koala Production Company",
        [(1,"1991-004456","Conveyance","1240/115","1991","x","El Paso Production Company")],
        [], convey_year=2005) is None
    # exact/surname match still accepted
    assert find_source_in("Hazel A. Hamilton",
        [(1,"1978-002576","Mineral Deed","237/367","1978","x","Hazel A. Hamilton")],
        [], convey_year=1990) is not None
