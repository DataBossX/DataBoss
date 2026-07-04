"""OGL/title reconciler + tournament: fills from register, no overwrite, no fabrication."""
from pathlib import Path

import openpyxl

from reports.title_ogl_reconciler import reconcile, parse_tract_set
from reports.report_tournament import (find_best_report, run_tournament, pick_winner,
                                       build_for_folder)


def test_parse_tract_set():
    assert parse_tract_set("All (1-8)") == set(range(1, 9))
    assert parse_tract_set("1, 3, 5") == {1, 3, 5}
    assert parse_tract_set("1-3, 5") == {1, 2, 3, 5}


def test_reconcile_fills_ogl_and_fixes_totals(sample_wb, tmp_path):
    out = tmp_path / "reconciled.xlsx"
    rep = reconcile(sample_wb, str(out), match_threshold=0.9)
    # 'Fixture Lessor' owner should be matched to the register grantor 'Fixture Lessor'
    assert rep.summary()["filled"] >= 1
    assert rep.summary()["totals_fixed"] >= 1
    wb = openpyxl.load_workbook(out)
    t = wb["Title "]
    # OGL No. filled on the matching owner row (B8), total converted to a formula
    assert t["D8"].value is not None
    assert str(t["C10"].value).startswith("=SUM")
    wb.close()


def test_reconcile_never_overwrites_source_or_dest(sample_wb, tmp_path):
    import hashlib
    before = hashlib.sha256(Path(sample_wb).read_bytes()).hexdigest()
    out = tmp_path / "r1.xlsx"
    reconcile(sample_wb, str(out))
    after = hashlib.sha256(Path(sample_wb).read_bytes()).hexdigest()
    assert before == after  # source untouched
    import pytest
    with pytest.raises(FileExistsError):
        reconcile(sample_wb, str(out))  # refuses to overwrite an existing dest


def test_reconcile_reports_unmatched_and_does_not_invent(sample_wb, tmp_path):
    out = tmp_path / "r2.xlsx"
    rep = reconcile(sample_wb, str(out), match_threshold=0.99)
    # 'Fixture Owner B' and Tract 2 owners have no register grantor -> reported, not filled
    assert len(rep.unmatched) >= 1
    wb = openpyxl.load_workbook(out)
    t = wb["Title "]
    # Owner B stays without an invented OGL number
    assert t["D9"].value in (None, "")
    wb.close()


def test_tournament_picks_winner_and_writes_final(sample_wb, tmp_path):
    folder = tmp_path / "Roger Mills"
    folder.mkdir()
    # place the fixture as the source report in the folder
    (folder / "cursory title report final.xlsx").write_bytes(Path(sample_wb).read_bytes())
    best = find_best_report(folder)
    assert best is not None
    cands = run_tournament(str(best), tmp_path / "work")
    assert len(cands) >= 1
    winner = pick_winner(cands)
    assert winner is not None
    out = tmp_path / "out"
    res = build_for_folder(str(folder), str(out), str(tmp_path / "work2"))
    assert res.final_path is not None
    assert Path(res.final_path).exists()
    assert (out / f"{folder.name}_reconciliation.md").exists()
    # source report unchanged
    assert best.exists()
