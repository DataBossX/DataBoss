"""Tests for the DataBossX Land Intelligence command center.

Covers the self-healing loop's three branches (clean / heal / escalate), the
exact-math verification, the yellow-highlight writer, the pipeline driver, and
the no-fabrication guarantee. Everything runs deterministically — no LLM, no key.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from command_center import agents as agents_mod
from command_center.engine import (
    FULL,
    SelfHealingEngine,
    infer_conveyed_from_notes,
    run_self_healing,
)
from command_center.sample_data import ensure_sample_workspace
from command_center.tasks import run_pipeline
from command_center.tools import verify_chain_tool, write_report_tool
from command_center.xlsx_writer import summarise_fills, write_highlighted_report


@pytest.fixture
def workspace(tmp_path) -> tuple[Path, Path]:
    return ensure_sample_workspace(tmp_path)


# --------------------------------------------------------------------------- #
# infer_conveyed_from_notes — the healing inference (unit)
# --------------------------------------------------------------------------- #
def test_infer_all_interest_maps_to_holder_before():
    holder = Fraction(3, 4)
    out = infer_conveyed_from_notes(["Assignment of all right, title and interest."], holder)
    assert out is not None and out[0] == holder


def test_infer_eighths_whole_maps_to_holder_before():
    holder = Fraction(1, 2)
    out = infer_conveyed_from_notes(["Conveys 8/8 of grantor's holding."], holder)
    assert out is not None and out[0] == holder  # 8/8 == whole holding, not the estate


def test_infer_proper_fraction_is_literal():
    out = infer_conveyed_from_notes(["Note: conveys an undivided 1/2 interest."], FULL)
    assert out is not None and out[0] == Fraction(1, 2)


def test_infer_percent_is_literal():
    out = infer_conveyed_from_notes(["Lease covers 12.5% royalty."], FULL)
    assert out is not None and out[0] == Fraction(1, 8)


def test_infer_blank_note_returns_none():
    assert infer_conveyed_from_notes([""], FULL) is None
    assert infer_conveyed_from_notes(["nothing quantitative here"], FULL) is None


# --------------------------------------------------------------------------- #
# The self-healing loop — three branches on the synthetic corpus
# --------------------------------------------------------------------------- #
def test_clean_tract_balances(workspace):
    wb, _ = workspace
    res = run_self_healing(wb)
    sw = _tract(res, "SW/4")
    assert sw.status == "balanced"
    assert sw.outstanding_sum == FULL
    assert sw.delta == 0
    assert sw.net_acres_sum == sw.gross_acres  # Σ working interest ties to gross


def test_heals_undetermined_from_runsheet(workspace):
    wb, _ = workspace
    res = run_self_healing(wb)
    ne = _tract(res, "NE/4")
    assert ne.status == "healed"
    assert ne.assumptions, "the heal must record a documented assumption"
    assert ne.outstanding_sum == FULL and ne.delta == 0
    assert res.loops_run >= 2  # it took a second pass to heal
    # the assumption must be surfaced as highlightable cells
    assert res.assumed_cells


def test_escalates_over_conveyance_without_fabrication(workspace):
    wb, _ = workspace
    res = run_self_healing(wb)
    se = _tract(res, "SE/4")
    assert se.status == "escalated"
    assert any("over-conveyance" in r.lower() for r in se.reasons)
    # the over-conveyed row must NOT carry an invented (negative) retained interest
    for row in res.report.rows:
        if row.retained_interest:
            assert not row.retained_interest.startswith("-")


def test_bounded_loops(workspace):
    wb, _ = workspace
    res = SelfHealingEngine(max_loops=1).run(wb)
    assert res.loops_run <= 1  # never spins past the cap


def test_review_rows_tagged(workspace):
    wb, _ = workspace
    res = run_self_healing(wb)
    escalated_rows = [r for r in res.report.rows if r.needs_review]
    assert escalated_rows, "escalated tracts must produce Needs Examiner Review rows"


# --------------------------------------------------------------------------- #
# Writer — yellow highlighting
# --------------------------------------------------------------------------- #
def test_writer_highlights_assumed_yellow(workspace, tmp_path):
    wb, tpl = workspace
    res = run_self_healing(wb)
    out = write_highlighted_report(res.report, tmp_path / "R_v001.xlsx", res.assumed_cells, template=tpl)
    fills = summarise_fills(out)
    assert fills["assumed"] >= 1  # NE/4 heal must paint at least one yellow cell
    assert fills["review"] >= 1  # SE/4 escalation must paint amber


def test_writer_runs_without_template(workspace, tmp_path):
    wb, _ = workspace
    res = run_self_healing(wb)
    out = write_highlighted_report(res.report, tmp_path / "R.xlsx", res.assumed_cells)
    assert out.exists()


# --------------------------------------------------------------------------- #
# Pipeline driver + tools
# --------------------------------------------------------------------------- #
def test_pipeline_deterministic_mode(workspace, tmp_path):
    wb, tpl = workspace
    events = []
    out = run_pipeline(
        wb, out_path=tmp_path / "REPORT.xlsx", template=tpl,
        use_swarm="off", sink=events.append,
    )
    assert out.mode == "deterministic"
    assert out.report_path and out.report_path.exists()
    assert out.result.converged
    assert len(events) > 5  # telemetry actually streamed


def test_pipeline_force_swarm_raises_without_key(workspace):
    wb, _ = workspace
    if agents_mod.swarm_available():
        pytest.skip("swarm is actually available in this environment")
    with pytest.raises(RuntimeError):
        run_pipeline(wb, use_swarm="force")


def test_verify_tool_reports_all_three_states(workspace):
    wb, _ = workspace
    txt = verify_chain_tool(str(wb))
    assert "balanced" in txt and "healed" in txt and "escalated" in txt


def test_write_report_tool(workspace, tmp_path):
    wb, _ = workspace
    msg = write_report_tool(str(wb), str(tmp_path / "T.xlsx"))
    assert "ASSUMED cells highlighted yellow" in msg


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _tract(result, quarter: str):
    for b in result.balances:
        if quarter in b.tract_legal:
            return b
    raise AssertionError(f"tract {quarter} not found in {[b.tract_legal for b in result.balances]}")
