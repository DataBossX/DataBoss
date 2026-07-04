#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end tests for automation/roger_mills_report_builder_v2.py.

These build a SYNTHETIC Horizon corpus (no real title data) and assert that the
v2 builder picks the best base, merges across folders, fills OGL numbers, fixes
the title sheet, standardizes legals, collapses book/page-typo near-duplicates,
and writes a valid workbook. openpyxl is required (it's in requirements.txt).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

AUTOMATION = Path(__file__).resolve().parent.parent / "automation"
sys.path.insert(0, str(AUTOMATION))

import make_roger_mills_sample as sample  # noqa: E402
import roger_mills_report_builder_v2 as v2  # noqa: E402


def _build_corpus(horizon: Path) -> None:
    sample.make_template(horizon / "Template(30).xlsx")
    sample.make_report(horizon / "Roger Mills" / "31-12N-24W_Cursory_Title_Report_v1.xlsx",
                       sample.BASE_ROWS[:4], note="Need recording info for Tract 1 lease.")
    r2 = [list(r) for r in sample.BASE_ROWS]
    r2[1][6] = "89"  # book typo -> exercises near-duplicate collapse
    sample.make_report(horizon / "Roger Mills 2" / "31-12N-24W_Cursory_Title_Report_FINAL.xlsx",
                       r2, title_date="6/27/2026", prepared="Horizon Minerals")
    sample.make_report(horizon / "Roger Mills 3" / "31-12N-24W_Cursory_Title_Report_updated_best.xlsx",
                       sample.BASE_ROWS, title_date="6/27/2026", prepared="Horizon Minerals",
                       note="Curative: obtain lessor affidavits for OGL-002.")
    (horizon / ".env").write_text("ANTHROPIC_API_KEY=\n", encoding="utf-8")


@pytest.fixture()
def built(tmp_path: Path):
    horizon = tmp_path / "Horizon"
    _build_corpus(horizon)
    rc = v2.main(["--horizon", str(horizon)])
    assert rc == 0
    out = horizon / "rogermillsfinalreports"
    wb_path = out / "31-12N-24W_Roger_Mills_Cursory_Title_Report_codexv2.xlsx"
    assert wb_path.exists()
    return {"horizon": horizon, "out": out, "wb": openpyxl.load_workbook(wb_path)}


def test_output_has_expected_sheets(built):
    names = built["wb"].sheetnames
    for s in ("Title Sheet", "Runsheet", "Tract Sheet", "OGL", "Notes"):
        assert s in names


def test_title_sheet_fixed(built):
    ts = built["wb"]["Title Sheet"]
    vals = {str(ts.cell(r, 1).value).lower().rstrip(":"): ts.cell(r, 2).value
            for r in range(1, 9)}
    assert vals.get("county") == "Roger Mills"
    assert vals.get("state") == "Oklahoma"
    assert str(vals.get("effective date")) == "6/27/2026"      # filled from source
    assert vals.get("prepared for") == "Horizon Minerals"       # filled from source


def test_near_duplicate_collapsed(built):
    rs = built["wb"]["Runsheet"]
    hdr = [c.value for c in rs[1]]
    gi, ti = hdr.index("Grantor"), hdr.index("Type")
    warranty = [row for row in rs.iter_rows(min_row=2, values_only=True)
                if row[ti] and "warranty" in str(row[ti]).lower()]
    assert len(warranty) == 1  # the 88-vs-89 book typo must not create two rows


def test_ogl_numbers_filled(built):
    rs = built["wb"]["Runsheet"]
    hdr = [c.value for c in rs[1]]
    ti, ii = hdr.index("Type"), hdr.index("Instrument No")
    lease_insts = {str(row[ii]) for row in rs.iter_rows(min_row=2, values_only=True)
                   if row[ti] and "lease" in str(row[ti]).lower()}
    assert "OGL-001" in lease_insts
    assert "OGL-002" in lease_insts


def test_legals_standardized(built):
    rs = built["wb"]["Runsheet"]
    hdr = [c.value for c in rs[1]]
    li = hdr.index("Legal Description")
    legals = [str(row[li]) for row in rs.iter_rows(min_row=2, values_only=True) if row[li]]
    # the verbose "Township 12 North, Range 24 West" form must be normalized away
    assert all("Township" not in l for l in legals)
    assert any("12N-24W" in l for l in legals)


def test_support_and_audit_files(built):
    files = built["out"] / "files"
    for name in ("source_inventory_codexv2.csv", "merge_audit_codexv2.csv",
                 "conflicts_review_codexv2.xlsx", "ogl_number_changes_codexv2.csv",
                 "legal_description_changes_codexv2.csv", "notes_collected_codexv2.csv",
                 "tournament_scores_codexv2.csv", "tract_sheet_fixed_codexv2.xlsx"):
        assert (files / name).exists(), name
    assert (built["out"] / "final_summary_codexv2.txt").exists()
    # originals backed up (nothing deleted)
    assert any((built["out"] / "_backups").rglob("*.xlsx"))


def test_conflict_recorded_for_book_typo(built):
    cw = openpyxl.load_workbook(built["out"] / "files" / "conflicts_review_codexv2.xlsx").active
    rows = [tuple(str(c) for c in row) for row in cw.iter_rows(values_only=True)]
    flat = " ".join(" ".join(r) for r in rows)
    assert "book" in flat and "89" in flat  # the typo alternative is preserved for review


def test_standardize_legal_is_lossless_on_calls():
    # formatting-only: section/township/range must survive verbatim
    out = v2.standardize_legal("NE/4 of Section 31, Township 12 North, Range 24 West")
    assert "31" in out and "12N" in out and "24W" in out and "NE/4" in out


def test_tournament_picks_updated_best(built):
    scores = (built["out"] / "files" / "tournament_scores_codexv2.csv").read_text()
    lines = [l for l in scores.splitlines() if l and not l.startswith("scope")]
    top = lines[0]
    assert "updated_best" in top  # the most complete + 'updated' workbook wins
