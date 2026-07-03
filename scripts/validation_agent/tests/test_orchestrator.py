"""Orchestrator: terminates cleanly (CERTIFY / ESCALATE / MAX_ITERATIONS),
never exceeds the iteration cap, and always writes an output bundle."""

import pytest

from config.settings import Settings
from core import orchestrator as orch_mod
from core.orchestrator import (Orchestrator, CERTIFIED, ESCALATED,
                               MAX_ITERATIONS)
from recalc.libreoffice_runner import LibreOfficeResult
from tests.fixtures.make_fixtures import make_basic_workbook


def _settings(tmp_path, **env):
    import os
    for k, v in env.items():
        os.environ[k] = v
    s = Settings()
    s.outputs_dir = tmp_path / "outputs"
    s.db_path = tmp_path / "outputs" / "audit.db"
    s.audit_log_path = tmp_path / "outputs" / "audit.log"
    s.outputs_dir.mkdir(parents=True, exist_ok=True)
    return s


def _passing_context():
    return {
        "tract_acreages": ["63.742"] * 10,
        "expected_acreage": "637.42",
        "interest_rows": [{"subject": "T1", "grantor_interest": "1/2",
                           "conveyed": "3/8", "retained": "1/8"}],
        "chain_links": [
            {"grantor": "US", "grantee": "Alice", "vested_root": True},
            {"grantor": "Alice", "grantee": "Bob"}],
        "instrument_references": [],
        "ogl_records": [{"lessor": "A", "lessee": "B", "date": "2020",
                         "book_page": "bk 1/pg 1", "royalty": "1/8"}],
        "wi_assignments": [{"wi": "1.0", "depth_top": "0", "depth_base": "9999"}],
        "hbp_claims": None,
        "source_documents": [],
    }


def test_certifies_when_all_gates_pass(tmp_path):
    s = _settings(tmp_path)
    src = make_basic_workbook(tmp_path / "wb.xlsx")
    orch = Orchestrator(s, timestamp="20260101_120000")
    result = orch.run(src, extra_context=_passing_context())
    orch.close()
    assert result.status == CERTIFIED
    assert result.iterations == 1
    assert result.exports
    # A certified workbook copy exists in exports.
    assert any("certified_workbook" in e for e in result.exports)


def test_escalates_on_missing_core_sheet(tmp_path):
    import openpyxl
    s = _settings(tmp_path)
    wb = openpyxl.Workbook()
    wb.active.title = "Random"
    wb.active.append(["x"])
    p = tmp_path / "bad.xlsx"
    wb.save(p)
    orch = Orchestrator(s, timestamp="20260101_120100")
    result = orch.run(p)
    orch.close()
    assert result.status == ESCALATED
    assert result.escalations


def test_stops_at_max_iterations(tmp_path, monkeypatch):
    s = _settings(tmp_path, DATABOSSX_MAX_ITERATIONS="3")
    src = make_basic_workbook(tmp_path / "wb.xlsx", with_hardcoded_total=True)

    # Skip real LibreOffice for speed/determinism.
    monkeypatch.setattr(orch_mod, "recalculate",
                        lambda *a, **k: LibreOfficeResult(False, available=False,
                                                          error="test-skip"))
    orch = Orchestrator(s, timestamp="20260101_120200")
    # Keep the repairable formula defect alive every iteration so the loop is
    # forced to run to the cap (proves the bound holds).
    monkeypatch.setattr(orch, "_refresh_context", lambda ctx, ver: ctx)

    ctx = _passing_context()
    ctx.update({
        "formula_sheet": "Tracts",
        "expected_formula_cells": ["C13"],
        "formula_map": {"C12": "=SUM(C2:C11)"},
        "value_map": {"C13": 600.0},
    })
    result = orch.run(src, extra_context=ctx)
    orch.close()
    assert result.status == MAX_ITERATIONS
    assert result.iterations == 3  # capped, never exceeded
    assert result.exports


def test_missing_workbook_terminates_error(tmp_path):
    s = _settings(tmp_path)
    orch = Orchestrator(s, timestamp="20260101_120300")
    result = orch.run(tmp_path / "does_not_exist.xlsx")
    orch.close()
    assert result.status == "ERROR"
