"""End-to-end tests for the Section 31 QA auditor."""
import datetime as dt
import hashlib
import sys
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "section31_qa"))
import section31_qa as qa  # noqa: E402


def build_tree(base: Path) -> Path:
    best_dir = base / "Roger Mills 2_All Best 7-7-26"
    best_dir.mkdir(parents=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ownership"
    ws["A1"] = "Section 31-12N-24W Roger Mills County"
    ws.append([])
    ws.append(["Tract", "Owner", "WI", "NRI", "Net Acres", "Book/Page", "Date"])
    ws.append(["1", "Alpha Minerals LLC", 0.5, 0.4375, 320, "1234/567", dt.datetime(2019, 3, 4)])
    ws.append(["1", "  Alpha Minerals LLC", "0.25", 0.30, -10, "bad", dt.datetime(2099, 1, 1)])
    ws.append(["1", "", 0.25, 0.21875, 160, "1250/12", dt.datetime(2020, 5, 1)])
    ws.append(["", "TOTAL", 0.90, 0.95, 470, "", ""])
    ogl = wb.create_sheet("OGL")
    ogl.append(["Tract", "Lessor", "WI", "Expiration", "Notes"])
    ogl.append(["1", "Alpha Minerals LLC", 0.5, dt.datetime(2020, 1, 1), "HBP confirmed"])
    hidden = wb.create_sheet("Hidden")
    hidden["A1"] = "#REF!"
    hidden.sheet_state = "hidden"
    path = best_dir / "31-12N-24W Roger Mills BEST 7-8-26.xlsx"
    wb.save(path)

    decoy = openpyxl.Workbook()
    w = decoy.active
    w.title = "Ownership"
    w["A1"] = "Section 32-12N-24W"
    w.append([])
    w.append(["Owner", "WI"])
    w.append(["Zeta Oil", 1.0])
    decoy.save(base / "32-12N-24W OLD copy.xlsx")
    return path


def sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def run_main(base, out, *extra):
    return qa.main(["--roots", str(base), "--out", str(out), *extra])


def test_full_run_picks_best_and_finds_defects(tmp_path):
    best = build_tree(tmp_path / "Horizon")
    out = tmp_path / "out"
    original_hash = sha1(best)
    assert run_main(tmp_path / "Horizon", out) == 0
    assert sha1(best) == original_hash, "original workbook must not change"
    for name in ["file_index.xlsx", "workbook_candidates.xlsx",
                 "workbook_comparison.xlsx", "qa_defects.xlsx",
                 "suggested_corrections.xlsx", "run_log.txt",
                 "SECTION31_QA_SUMMARY.txt"]:
        assert (out / name).exists(), f"missing output {name}"

    cand = openpyxl.load_workbook(out / "workbook_candidates.xlsx")["Candidates"]
    assert "BEST 7-8-26" in str(cand.cell(row=2, column=3).value)

    defects = openpyxl.load_workbook(out / "qa_defects.xlsx")["QA Defects"]
    categories = {defects.cell(row=r, column=2).value
                  for r in range(2, defects.max_row + 1)}
    for expected in ["BAD_NEGATIVE", "NON_FOOTING_TOTAL", "BLANK_REQUIRED",
                     "DUPLICATE_OWNER", "INTEREST_BOUNDS", "HIDDEN_SHEET",
                     "FORMULA_ERROR", "HBP_UNSUPPORTED", "DATE_ISSUE",
                     "BOOK_PAGE_ISSUE", "TEXT_NUMBER", "MISSING_ASSUMPTIONS"]:
        assert expected in categories, f"{expected} not detected"


def test_dry_run_writes_nothing(tmp_path):
    build_tree(tmp_path / "Horizon")
    out = tmp_path / "out"
    assert run_main(tmp_path / "Horizon", out, "--dry-run") == 0
    assert not out.exists() or not any(out.iterdir())


def test_apply_corrections_edits_copy_only(tmp_path):
    best = build_tree(tmp_path / "Horizon")
    out = tmp_path / "out"
    original_hash = sha1(best)
    assert run_main(tmp_path / "Horizon", out, "--apply-corrections") == 0
    assert sha1(best) == original_hash
    copies = list(out.glob("*__SAFE_WORKING_COPY.xlsx"))
    assert len(copies) == 1
    fixed = openpyxl.load_workbook(copies[0])["Ownership"]
    assert fixed["C5"].value == 0.25            # text number converted
    assert fixed["B5"].value == "Alpha Minerals LLC"  # whitespace trimmed


def test_missing_roots_fail_loudly(tmp_path):
    assert qa.main(["--roots", str(tmp_path / "nope"), "--out", str(tmp_path / "o")]) == 1
