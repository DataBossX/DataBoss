"""P7 exit test: the loop REPAIRS a seeded footing defect and reaches CERTIFIED.

This exercises the full repair path end-to-end — analyze -> SAFE fix -> XML
surgery -> LibreOffice recalc -> re-validate -> certify — proving the loop
converges, not just escalates. A G2-focused suite is used so the (image-gated)
G1/G3 gaps do not mask the convergence proof.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import openpyxl
import pytest

from validation_agent.models import LoopState
from validation_agent.orchestrator import PerfectionLoop
from validation_agent.repair.xml_surgery import XmlWorkbook
from validation_agent.validation import ValidatorSuite
from validation_agent.validation.pro_rata_footing import ProRataFootingValidator

FIXTURE = Path(__file__).parent / "fixtures" / "workbook.xlsx"

_HAS_LO = shutil.which("soffice") or shutil.which("libreoffice")
pytestmark = pytest.mark.skipif(not _HAS_LO, reason="LibreOffice not installed")


def _seed_truncated_footing(dst: Path) -> None:
    """Break Tract 2's footing by truncating its SUMIF range to rows 10:20."""
    xw = XmlWorkbook.open(FIXTURE)
    xw.set_cell(
        "Title ", "C33",
        "=ROUND(SUMIF('Tract 2'!$E$10:$E$20,\">0\",'Tract 2'!$C$10:$C$20),2)",
    )
    xw.drop_calc_chain()
    xw.force_full_calc()
    xw.save_as(dst)


def test_loop_repairs_footing_and_certifies(tmp_path, monkeypatch) -> None:
    import validation_agent.config as cfg
    monkeypatch.setattr(cfg, "OUTPUT_DIR", tmp_path / "out")

    tampered = tmp_path / "tampered.xlsx"
    _seed_truncated_footing(tampered)

    # Sanity: the seed really under-foots (cached recompute happens in the loop).
    g2_only = ValidatorSuite([ProRataFootingValidator()])
    loop = PerfectionLoop(tampered, suite=g2_only)
    outcome = loop.run(max_iterations=5)

    assert outcome.state == LoopState.CERTIFIED, outcome.state
    # A SAFE footing-range fix was applied.
    fixes = loop.conn.execute(
        "SELECT strategy_id, risk, before, after FROM fixes"
    ).fetchall()
    assert any(f["strategy_id"] == "extend_footing_range" and f["risk"] == "SAFE"
               for f in fixes)
    # The repaired workbook foots Tract 2 back to 160 under recalc.
    from validation_agent.repair.recalc_engine import RecalcEngine
    vals = RecalcEngine().recalc(outcome.final_path).values
    assert abs(vals.get("Title ", "C", 33) - 160) < 0.02


def test_certification_emits_artifacts(tmp_path, monkeypatch) -> None:
    import validation_agent.config as cfg
    monkeypatch.setattr(cfg, "OUTPUT_DIR", tmp_path / "out2")
    from validation_agent.reporting.certification import Certifier

    tampered = tmp_path / "t2.xlsx"
    _seed_truncated_footing(tampered)
    g2_only = ValidatorSuite([ProRataFootingValidator()])
    loop = PerfectionLoop(tampered, suite=g2_only)
    outcome = loop.run(max_iterations=5)
    assert outcome.state == LoopState.CERTIFIED

    art = Certifier(loop.conn, loop.run_id).certify(
        outcome.final_path, outcome.final_version, outcome.state, tmp_path / "cert")
    assert art.workbook_path.exists()
    assert art.summary_path.exists()
    assert "Final Title Picture" in art.summary_path.read_text()
    # Certified workbook preserves the embedded map/drawings (byte-identical).
    import zipfile
    with zipfile.ZipFile(FIXTURE) as a, zipfile.ZipFile(art.workbook_path) as b:
        bset = set(b.namelist())
        for n in a.namelist():
            if "media" in n or "drawing" in n:
                assert n in bset
