"""Tests for the title report: interest chain-out, OGL tie-out, gap flagging."""

from __future__ import annotations

from fractions import Fraction

import pytest

pytest.importorskip("openpyxl")

from validation_agent.ingestion.manifest_builder import WorkbookManifestBuilder  # noqa: E402
from validation_agent.reports.title_report import TitleReportGenerator  # noqa: E402
from validation_agent.tests.make_fixture import (build_certifiable_workbook,  # noqa: E402
                                                 build_escalation_workbook)


def _manifest(path):
    return WorkbookManifestBuilder().build("r", 0, path, "sha")


def test_interest_chains_out_and_reconciles(tmp_path):
    m = _manifest(build_certifiable_workbook(tmp_path / "c.xlsx"))
    chain = TitleReportGenerator()._chain_out(m)
    # US PATENT -> ALICE (1), ALICE -> BOB (1/2), BOB -> CAROL (1/2)
    assert chain.ownership.get("ALICE") == Fraction(1, 2)
    assert chain.ownership.get("CAROL") == Fraction(1, 2)
    assert "BOB" not in chain.ownership          # fully conveyed out
    assert chain.total_owned == Fraction(1)      # reconciles to 100%
    assert not chain.warnings


def test_ogl_tieout_links_numbers_to_tracts(tmp_path):
    m = _manifest(build_certifiable_workbook(tmp_path / "c.xlsx"))
    ogl = TitleReportGenerator()._ogl_tieout(m)
    numbers = {o["ogl_number"] for o in ogl}
    assert {"L-001", "L-002"} <= numbers
    assert all(o["tie_status"] == "tied" for o in ogl)


def test_vesting_gap_is_flagged_not_invented(tmp_path):
    m = _manifest(build_escalation_workbook(tmp_path / "e.xlsx"))
    chain = TitleReportGenerator()._chain_out(m)
    # The ESTATE OF ZED grantor was never vested -> a warning, not a fabricated
    # holding.
    assert any("not previously vested" in w for w in chain.warnings)


def test_report_files_written(tmp_path):
    m = _manifest(build_certifiable_workbook(tmp_path / "c.xlsx"))
    out = tmp_path / "reports"
    TitleReportGenerator().generate(m, out, prospect="Demo")
    assert (out / "title_report.md").is_file()
    assert (out / "title_report.json").is_file()
    text = (out / "title_report.md").read_text()
    assert "Chained-Out Interest" in text
    assert "reconciles to 100%" in text


def test_net_mineral_acres_computed(tmp_path):
    import json
    m = _manifest(build_certifiable_workbook(tmp_path / "c.xlsx"))
    out = tmp_path / "r"
    TitleReportGenerator().generate(m, out, prospect="Demo")
    data = json.loads((out / "title_report.json").read_text())
    assert data["net_acres"] == 637.42
    # 1/2 of 637.42 each for ALICE and CAROL.
    assert data["ownership_net_acres"]["ALICE"] == pytest.approx(318.71)
    assert data["ownership_net_acres"]["CAROL"] == pytest.approx(318.71)


def test_completeness_full_on_clean_and_partial_on_gap(tmp_path):
    import json
    clean = _manifest(build_certifiable_workbook(tmp_path / "c.xlsx"))
    out = tmp_path / "clean"
    TitleReportGenerator().generate(clean, out, prospect="Demo")
    c = json.loads((out / "title_report.json").read_text())["completeness"]
    assert c["passed"] == c["total"]  # clean workbook is fully complete

    gap = _manifest(build_escalation_workbook(tmp_path / "e.xlsx"))
    out2 = tmp_path / "gap"
    TitleReportGenerator().generate(gap, out2, prospect="Demo")
    g = json.loads((out2 / "title_report.json").read_text())["completeness"]
    assert g["passed"] < g["total"]  # a vesting gap is not examiner-ready
