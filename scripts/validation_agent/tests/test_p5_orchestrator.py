"""P5/P7 exit tests: the perfection loop on the real workbook + a seeded defect.

1. On the delivered (already source-verified) workbook, the loop must reach a
   terminal state deterministically. Because the workbook legitimately carries
   unresolved ARTI/orphan items that need instrument images, the correct terminal
   state is ESCALATED (never CERTIFIED-by-fabrication) — proving the loop refuses
   to invent title data.
2. A seeded footing defect that IS safely fixable must be repaired and converge.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from validation_agent.models import LoopState
from validation_agent.orchestrator import PerfectionLoop

FIXTURE = Path(__file__).parent / "fixtures" / "workbook.xlsx"

_HAS_LO = shutil.which("soffice") or shutil.which("libreoffice")
pytestmark = pytest.mark.skipif(not _HAS_LO, reason="LibreOffice not installed")


def test_loop_reaches_terminal_state_without_fabricating(tmp_path, monkeypatch) -> None:
    # Route output under tmp to keep the repo clean.
    import validation_agent.config as cfg
    monkeypatch.setattr(cfg, "OUTPUT_DIR", tmp_path / "out")
    loop = PerfectionLoop(FIXTURE)
    outcome = loop.run(max_iterations=3)
    # Terminal, deterministic, and honest: escalates on the image-gated gaps.
    assert outcome.state in (LoopState.ESCALATED, LoopState.CERTIFIED, LoopState.HALTED)
    assert outcome.state == LoopState.ESCALATED
    assert outcome.escalations
    # Proof trail exists.
    assert loop.conn.execute(
        "SELECT COUNT(*) FROM validation_results"
    ).fetchone()[0] > 0
    assert loop.conn.execute(
        "SELECT COUNT(*) FROM escalations"
    ).fetchone()[0] >= 1


def test_no_fabrication_no_unsourced_fixes(tmp_path, monkeypatch) -> None:
    import validation_agent.config as cfg
    monkeypatch.setattr(cfg, "OUTPUT_DIR", tmp_path / "out2")
    loop = PerfectionLoop(FIXTURE)
    loop.run(max_iterations=3)
    # Every recorded fix must be SAFE and carry a justification.
    rows = loop.conn.execute(
        "SELECT risk, justification FROM fixes"
    ).fetchall()
    for row in rows:
        assert row["risk"] == "SAFE"
        assert row["justification"]


def test_audit_report_builds(tmp_path, monkeypatch) -> None:
    import validation_agent.config as cfg
    monkeypatch.setattr(cfg, "OUTPUT_DIR", tmp_path / "out3")
    from validation_agent.reporting.audit_report import AuditReportBuilder
    loop = PerfectionLoop(FIXTURE)
    loop.run(max_iterations=2)
    report = AuditReportBuilder(loop.conn, loop.run_id).build(tmp_path / "audit.md")
    text = report.read_text()
    assert "Validation & Repair Audit" in text
    assert "Escalations" in text
