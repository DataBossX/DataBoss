"""End-to-end and unit tests for the title report generator."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest
from openpyxl import load_workbook

from title_report import fractions as fr
from title_report.models import UNKNOWN, OwnershipEntry, ProjectConfig, TitleReport
from title_report.sample_data import build_sample_report
from title_report.deliverables import compute_missing
from title_report.generate import generate

REQUIRED_SHEETS = {
    "Cover", "Source Log", "Runsheet", "Abstractions",
    "Chain — Mineral-Surface", "Chain — Leasehold-WI", "Wells & HBP",
    "Curative", "NRI-WI Matrix", "QA Dashboard", "Missing-Unverified",
}


# ── fraction math ────────────────────────────────────────────────────────────

def test_royalty_nri_exact():
    assert fr.net_revenue_interest(Fraction(1), Fraction(3, 16)) == Fraction(3, 16)
    assert fr.net_revenue_interest(Fraction(1, 2), Fraction(3, 16)) == Fraction(3, 32)


def test_wi_nri_exact():
    assert fr.wi_net_revenue_interest(Fraction(1), Fraction(3, 16)) == Fraction(13, 16)


def test_unknown_inputs_stay_unknown():
    assert fr.net_revenue_interest(UNKNOWN, Fraction(3, 16)) == UNKNOWN
    assert fr.wi_net_revenue_interest(Fraction(1), UNKNOWN) == UNKNOWN
    assert fr.net_mineral_acres(UNKNOWN, Fraction(640)) == UNKNOWN


def test_parse_and_render():
    assert fr.parse_fraction("3/16") == Fraction(3, 16)
    assert fr.parse_fraction("0.1875") == Fraction(3, 16)
    assert fr.parse_fraction("") is None
    assert fr.frac_str(Fraction(3, 16)) == "3/16"
    assert fr.frac_str(UNKNOWN) == UNKNOWN


# ── pipeline ─────────────────────────────────────────────────────────────────

def test_generate_writes_all_deliverables(tmp_path):
    result = generate(out_dir=str(tmp_path))
    for key in ("workbook", "source_log", "curative_list", "missing",
                "change_summary", "qa_results"):
        assert Path(result[key]).exists(), f"missing deliverable: {key}"


def test_workbook_has_all_sheets(tmp_path):
    result = generate(out_dir=str(tmp_path))
    wb = load_workbook(result["workbook"])
    assert REQUIRED_SHEETS.issubset(set(wb.sheetnames))


def test_nri_matrix_uses_live_formulas(tmp_path):
    result = generate(out_dir=str(tmp_path))
    wb = load_workbook(result["workbook"])
    ws = wb["NRI-WI Matrix"]
    formulas = [c.value for row in ws.iter_rows() for c in row
                if isinstance(c.value, str) and c.value.startswith("=")]
    assert formulas, "expected at least one live Excel formula in NRI-WI matrix"


def test_row_reconciliation_passes_on_sample(tmp_path):
    result = generate(out_dir=str(tmp_path))
    counts = result["counts"]
    rpt = build_sample_report()
    assert counts["Runsheet"] == len(rpt.instruments)
    assert counts["Curative"] == len(rpt.curative)
    assert counts["NRI-WI Matrix"] == len(rpt.ownership)


def test_qa_runs_and_reports(tmp_path):
    result = generate(out_dir=str(tmp_path))
    qa_text = Path(result["qa_results"]).read_text()
    assert "Citation coverage" in qa_text
    assert "Fraction math" in qa_text
    assert "Secrets scan" in qa_text


def test_placeholder_blocks_final(tmp_path):
    result = generate(out_dir=str(tmp_path))
    assert result["is_placeholder"] is True
    qa_text = Path(result["qa_results"]).read_text()
    assert "NOT FINAL" in qa_text


def test_computed_nri_requires_basis_language():
    """A computed interest without basis language must be caught by QA."""
    cfg = ProjectConfig(section="1", township="1N", range_="1W", county="Test")
    bad = OwnershipEntry(owner="X", role="royalty",
                         mineral_interest=Fraction(1), lease_royalty=Fraction(1, 8),
                         basis_language=UNKNOWN, citation="SRC-1")
    rpt = TitleReport(config=cfg, ownership=[bad])
    from title_report.qa import _fraction_math
    chk = _fraction_math(rpt)
    assert chk["status"] == "FAIL"
    assert "basis language" in chk["detail"]


def test_secrets_scan_flags_key(tmp_path):
    from title_report.qa import _secrets_scan
    p = tmp_path / "leak.txt"
    p.write_text("api_key = sk-ABCDEFGHIJKLMNOPQRSTUVWX")
    chk = _secrets_scan([p])
    assert chk["status"] == "FAIL"


def test_missing_flags_uncited_and_placeholder():
    rpt = build_sample_report()
    missing = compute_missing(rpt)
    types = {m["type"] for m in missing}
    assert "Placeholder run" in types
