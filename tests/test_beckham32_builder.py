"""End-to-end tests for the Beckham 32 report builder."""
import hashlib
import sys
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "beckham32"))
import beckham32_report_builder as builder  # noqa: E402


def build_sources(base: Path):
    base.mkdir(parents=True)
    wb = openpyxl.Workbook()
    ov = wb.active
    ov.title = "Overview"
    ov["A1"] = "Section 32-11N-25W Beckham County cursory - NHE"
    ov["A2"] = "Last entry Bk 2490/P471."
    rs = wb.create_sheet("Runsheet")
    rs.append(["Instrument", "Date", "Grantor", "Grantee", "Book/Page", "Legal", "Notes"])
    rs.append(["Assignment", "3/4/1962", "Union Oil", "Leede Oil", "502/267",
               "NE/4 Crook wellbore", "L-001 direct image"])
    rs.append(["Assignment", "5/1/1965", "Leede Oil", "Cities Service", "509/220",
               "E/2 SE/4 Pearl", "L-002 direct image"])
    rs.append(["Conveyance", "6/1/2021", "", "", "2340/403",
               "all of Section 32-11N-25W", "INDEX ONLY - schedule absent"])
    nhe = base / "32-11N-25W_Beckham_NHE.xlsx"
    wb.save(nhe)

    wb2 = openpyxl.Workbook()
    r = wb2.active
    r.title = "Runsheet"
    r.append(["Instrument", "Date", "Grantor", "Grantee", "Book/Page", "Legal"])
    r.append(["Assignment", "5/1/1965", "Leede Oil", "Cities Service", "509/220", "Pearl"])
    r.append(["Merger", "8/1/2021", "", "", "2371/470", "Section 32 entire section"])
    orig = base / "32-11N-25W_Beckham_Cursory_Title_Report_2026-07-10.xlsx"
    wb2.save(orig)
    return nhe, orig


def sha1(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()


def test_merge_dedup_chain_and_priority(tmp_path):
    nhe, orig = build_sources(tmp_path / "src")
    hashes = (sha1(nhe), sha1(orig))
    out = tmp_path / "out"
    assert builder.main(["--search", str(tmp_path / "src"),
                         "--out", str(out)]) == 0
    assert (sha1(nhe), sha1(orig)) == hashes, "sources must be untouched"
    merged = list(out.glob("*MERGED_BEST*.xlsx"))
    assert len(merged) == 1
    wb = openpyxl.load_workbook(merged[0])
    for sheet in ["Overview", "Runsheet", "Tract1", "Tract5", "Unrouted",
                  "Priority Pulls", "Open Requirements"]:
        assert sheet in wb.sheetnames

    rs_rows = list(wb["Runsheet"].iter_rows(min_row=2, values_only=True))
    keys = [(r[0], r[1]) for r in rs_rows]
    assert keys.count(("509", "220")) == 1, "duplicate instrument must merge"
    # 2490/471 harvested from Overview free text
    assert ("2490", "471") in keys
    tiers = {(r[0], r[1]): r[7] for r in rs_rows}
    assert tiers[("502", "267")] == builder.TIER_DIRECT
    assert tiers[("2340", "403")] == builder.TIER_INDEX
    # index-only rows carry OPEN ITEM parties, never invented names
    row_2340 = next(r for r in rs_rows if (r[0], r[1]) == ("2340", "403"))
    assert row_2340[4] == builder.OPEN_ITEM and row_2340[5] == builder.OPEN_ITEM

    # tract routing: Crook instrument lands on Tract 1, section-wide on Tract 5
    t1 = [r for r in wb["Tract1"].iter_rows(min_row=5, values_only=True) if r[0]]
    assert any((r[0], r[1]) == ("502", "267") for r in t1)
    t5 = [r for r in wb["Tract5"].iter_rows(min_row=5, values_only=True) if r[0]]
    assert any((r[0], r[1]) == ("2340", "403") for r in t5)
    # un-abstracted instruments carry an OPEN ITEM chain status
    row = next(r for r in t5 if (r[0], r[1]) == ("2340", "403"))
    assert row[11].startswith(builder.OPEN_ITEM)

    pp = {(r[0], r[1]): r[2] for r in
          wb["Priority Pulls"].iter_rows(min_row=2, values_only=True)}
    assert pp[("2340", "403")] == "YES"
    assert pp[("2400", "551")] == "NO"


def test_dry_run_and_missing_sources(tmp_path):
    nhe, _ = build_sources(tmp_path / "src")
    out = tmp_path / "out"
    assert builder.main(["--search", str(tmp_path / "src"), "--out", str(out),
                         "--dry-run"]) == 0
    assert not list(out.glob("*.xlsx"))
    assert builder.main(["--search", str(tmp_path / "empty")]) == 1
