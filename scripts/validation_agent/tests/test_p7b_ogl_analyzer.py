"""P7b: the PhantomOGLRenumberAnalyzer repairs a seeded phantom citation.

Proves the repair framework generalises beyond footing: a Title cell citing a
non-existent OGL number, but carrying a book/page that the register maps
bijectively to the correct number, is auto-corrected (SAFE) and the loop
certifies. An ambiguous phantom (no book/page) escalates instead.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import openpyxl
import pytest

from validation_agent.ingestion.workbook_map import WorkbookMapper
from validation_agent.models import LoopState
from validation_agent.orchestrator import PerfectionLoop
from validation_agent.repair.analyzers import PhantomOGLRenumberAnalyzer
from validation_agent.repair.xml_surgery import XmlWorkbook
from validation_agent.validation import ValidatorSuite
from validation_agent.validation.ogl_register_audit import OGLRegisterAuditValidator

FIXTURE = Path(__file__).parent / "fixtures" / "workbook.xlsx"
_HAS_LO = shutil.which("soffice") or shutil.which("libreoffice")


def _seed_phantom(dst: Path, text: str) -> None:
    xw = XmlWorkbook.open(FIXTURE)
    # G8 is a Title comment cell; inject a phantom OGL citation.
    xw.set_cell("Title ", "G8", text)
    xw.drop_calc_chain()
    xw.force_full_calc()
    xw.save_as(dst)


def test_analyzer_maps_bookpage_to_correct_number(tmp_path: Path) -> None:
    seeded = tmp_path / "phantom.xlsx"
    _seed_phantom(seeded, "Top lease OGL 110 (Bk 2697/520) subordinate.")
    model = WorkbookMapper.load(seeded)
    results = OGLRegisterAuditValidator().validate(model, None)
    phantom = next(r for r in results if not r.passed and "cites OGL 110" in r.message)
    plan = PhantomOGLRenumberAnalyzer().analyze(phantom, model)
    assert plan is not None
    assert plan.risk.value == "SAFE"
    assert "OGL 67" in plan.after and "OGL 110" not in plan.after


def test_ambiguous_phantom_without_bookpage_escalates(tmp_path: Path) -> None:
    seeded = tmp_path / "phantom2.xlsx"
    _seed_phantom(seeded, "Top lease OGL 110 subordinate.")  # no book/page
    model = WorkbookMapper.load(seeded)
    results = OGLRegisterAuditValidator().validate(model, None)
    phantom = next(r for r in results if not r.passed and "cites OGL 110" in r.message)
    # No co-located book/page -> analyzer refuses to guess.
    assert PhantomOGLRenumberAnalyzer().analyze(phantom, model) is None


@pytest.mark.skipif(not _HAS_LO, reason="LibreOffice not installed")
def test_loop_repairs_phantom_and_certifies(tmp_path, monkeypatch) -> None:
    import validation_agent.config as cfg
    monkeypatch.setattr(cfg, "OUTPUT_DIR", tmp_path / "out")
    seeded = tmp_path / "phantom3.xlsx"
    _seed_phantom(seeded, "Top lease OGL 110 (Bk 2697/520) subordinate.")
    loop = PerfectionLoop(seeded, suite=ValidatorSuite([OGLRegisterAuditValidator()]))
    outcome = loop.run(max_iterations=4)
    assert outcome.state == LoopState.CERTIFIED, outcome.state
    wb = openpyxl.load_workbook(outcome.final_path)
    assert "OGL 67" in wb["Title "]["G8"].value
    assert "OGL 110" not in wb["Title "]["G8"].value
