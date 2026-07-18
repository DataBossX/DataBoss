"""Tests for chain_graph, runsheet, workbook_diff, intake, and needs_me."""

import csv
import json
from pathlib import Path

from core.land_title_os.assets import AssetInventory
from core.land_title_os.chain_graph import ChainGraph, InstrumentNode, normalize_name
from core.land_title_os.intake import ingest_inventory_csv
from core.land_title_os.manifest import ProjectManifest
from core.land_title_os.needs_me import collect, render
from core.land_title_os.runsheet import generate_runsheet, write_runsheet_csv
from core.land_title_os.workbook_diff import diff_sheets, summarize

REPO_ROOT = Path(__file__).resolve().parent.parent


def _clean_chain() -> ChainGraph:
    g = ChainGraph()
    g.add(InstrumentNode("P-1", "1907-06-08", ["United States"], ["Cornelius B. Cornelius"],
                         kind="patent", book_page="3/469", tracts=["NE/4"]))
    g.add(InstrumentNode("D-1", "1950-01-01", ["Cornelius B. Cornelius"], ["Alice Kirk"],
                         kind="warranty deed", book_page="100/1", tracts=["NE/4"]))
    g.add(InstrumentNode("D-2", "1960-01-01", ["Alice Kirk"], ["Bob Ray"],
                         kind="mineral deed", book_page="200/2", tracts=["NE/4"]))
    return g


# -- chain graph -------------------------------------------------------------

def test_clean_chain_has_no_breaks():
    findings = _clean_chain().analyze(gap_years=50)
    assert [f for f in findings if f.rule == "chain_break"] == []


def test_chain_break_detected():
    g = _clean_chain()
    g.add(InstrumentNode("D-3", "1970-01-01", ["Carol Stranger"], ["Dan Deal"],
                         kind="quitclaim deed", book_page="300/3", tracts=["NE/4"]))
    breaks = [f for f in g.analyze() if f.rule == "chain_break"]
    assert len(breaks) == 1
    assert "Carol Stranger" in breaks[0].message
    assert breaks[0].severity == "critical"


def test_release_does_not_create_holder_or_break():
    g = _clean_chain()
    # a release from a bank (never a grantee) is not a title conveyance
    g.add(InstrumentNode("R-1", "1965-01-01", ["First Bank"], ["Bob Ray"],
                         kind="release", book_page="250/9"))
    assert [f for f in g.analyze(gap_years=50) if f.rule == "chain_break"] == []


def test_coverage_gap_detected():
    g = _clean_chain()  # 1907 -> 1950 is a 43-year gap
    gaps = [f for f in g.analyze(gap_years=40) if f.rule == "coverage_gap"]
    assert gaps and "43-year" in gaps[0].message


def test_repeated_conveyance_detected():
    g = _clean_chain()
    g.add(InstrumentNode("D-4", "1971-01-01", ["Alice Kirk"], ["Eve New"],
                         kind="warranty deed", book_page="310/5", tracts=["NE/4"]))
    repeats = [f for f in g.analyze() if f.rule == "repeated_conveyance"]
    assert len(repeats) == 1 and "Alice Kirk" in repeats[0].message


def test_name_near_miss_reported_not_merged():
    g = ChainGraph()
    g.add(InstrumentNode("D-1", "1950-01-01", ["United States"], ["Ella Kirk"], kind="patent"))
    g.add(InstrumentNode("D-2", "1960-01-01", ["Ella Pearl Kirk"], ["Zed Q"], kind="deed"))
    findings = g.analyze()
    assert any(f.rule == "name_near_miss" for f in findings)
    # the subset name is NOT treated as the same holder -> also a chain break
    assert any(f.rule == "chain_break" for f in findings)
    assert normalize_name("Ella  Pearl KIRK.") == "ella pearl kirk"


# -- runsheet ---------------------------------------------------------------

def test_runsheet_generation_and_csv(tmp_path):
    g = _clean_chain()
    g.add(InstrumentNode("D-9", "1980-01-01", ["Nobody Known"], ["X Y"],
                         kind="deed", book_page="400/4"))
    rows = generate_runsheet(g)
    assert [r["Recorded_Date"] for r in rows] == sorted(r["Recorded_Date"] for r in rows)
    flagged = [r for r in rows if r["Instrument_Number"] == "D-9"]
    assert flagged and "chain_break" in flagged[0]["Open_Issues"]

    out = write_runsheet_csv(rows, tmp_path / "runsheet.csv")
    with open(out, newline="", encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == len(rows)


# -- workbook diff ----------------------------------------------------------

def test_workbook_diff_detects_changes():
    before = {"Title": [{"Owner": "A", "Interest": "1/2"}, {"Owner": "B", "Interest": "1/2"}],
              "Notes": [{"Text": "keep"}]}
    after = {"Title": [{"Owner": "A", "Interest": "1/3"}, {"Owner": "B", "Interest": "1/2"},
                       {"Owner": "C", "Interest": "1/6"}],
             "Extra": []}
    diffs = diff_sheets(before, after)
    kinds = {d.kind for d in diffs}
    assert kinds == {"sheet_removed", "sheet_added", "cell_changed", "row_added"}
    changed = [d for d in diffs if d.kind == "cell_changed"]
    assert changed[0].before == "1/2" and changed[0].after == "1/3"
    assert "1/2" in changed[0].describe()
    assert summarize(diffs)["total"] == len(diffs)
    assert diff_sheets(before, before) == []


# -- intake ------------------------------------------------------------------

def test_ingest_inventory_csv(tmp_path):
    csv_path = tmp_path / "file_inventory.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "rel_path", "name", "ext", "size_bytes", "modified", "sha256",
            "likely_type", "processing_status", "abs_path"])
        writer.writeheader()
        writer.writerow({"rel_path": "a/deed.pdf", "name": "deed.pdf", "ext": ".pdf",
                         "size_bytes": "100", "modified": "2026-07-01 10:00:00",
                         "sha256": "aa" * 32, "likely_type": "instrument",
                         "processing_status": "", "abs_path": "D:/docs/a/deed.pdf"})
        writer.writerow({"rel_path": "b/deed_copy.pdf", "name": "deed_copy.pdf", "ext": ".pdf",
                         "size_bytes": "100", "modified": "2026-07-01 10:00:00",
                         "sha256": "aa" * 32, "likely_type": "instrument",
                         "processing_status": "", "abs_path": "D:/docs/b/deed_copy.pdf"})
    inv = AssetInventory(tmp_path / "assets.db")
    assert ingest_inventory_csv(inv, csv_path, project_id="OK-TEST-1") == 2
    assert inv.count() == 2
    assert len(inv.duplicate_groups()) == 1   # same sha256 -> one duplicate group
    inv.close()


# -- needs_me ----------------------------------------------------------------

def test_needs_me_aggregates(tmp_path):
    proj = tmp_path / "OK-TEST-1"
    m = ProjectManifest(project_id="OK-TEST-1", client="Acme", jurisdiction="OK",
                        county="X", section="1", township="1N", range="1W",
                        open_issues=[{"severity": "critical", "description": "authorize pull"}])
    m.save(proj / "manifest.json")
    (proj / "promotion_state.json").write_text(json.dumps(
        {"C:/x/report.xlsx": {"stage": "QA", "sha256": "ff", "history": []}}))

    items = collect(tmp_path)
    sources = {i.source for i in items}
    assert sources == {"manifest", "promotion"}
    assert items[0].severity == "critical"          # sorted most severe first
    text = render(items)
    assert "authorize pull" in text and "awaiting human APPROVED" in text
    assert "Nothing needs you" in render([])


def test_needs_me_on_real_beckham_project():
    items = collect(REPO_ROOT / "projects")
    assert any(i.project == "OK-BECKHAM-32-11N-25W" and i.source == "manifest"
               for i in items)
    assert any(i.source == "issues" for i in items)   # backfilled register items
