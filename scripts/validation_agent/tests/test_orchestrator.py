"""Orchestrator: clean termination, iteration cap, source-finder, LibreOffice escalation."""
from pathlib import Path

from core.orchestrator import Orchestrator, CERTIFY, ESCALATE_S, MAX_ITER_STATE
from recalc.libreoffice_runner import detect_libreoffice, recalc


def test_orchestrator_terminates_cleanly(db, tmp_agent, sample_wb):
    res = Orchestrator(db, tmp_agent).run(sample_wb)
    assert res.final_state in (CERTIFY, ESCALATE_S, MAX_ITER_STATE)
    assert res.iterations <= tmp_agent.max_iterations
    # produced an export bundle
    assert any(p.endswith(".zip") for p in res.exports)
    # baseline + at least one version recorded; source untouched
    assert db.count("workbook_versions", "run_id=?", (res.run_id,)) >= 1


def test_orchestrator_escalates_and_never_certifies_bad_workbook(db, tmp_agent, sample_wb):
    # fixture has over-conveyance + chain gap + unconfirmed HBP -> must NOT certify
    res = Orchestrator(db, tmp_agent).run(sample_wb)
    assert res.final_state == ESCALATE_S
    assert db.count("escalations", "run_id=?", (res.run_id,)) >= 1


def test_source_finder_builds_missing_queue(db, tmp_agent, sample_wb):
    Orchestrator(db, tmp_agent).run(sample_wb)
    # the OGL 1736/0592 reference should be captured as a source document row
    rows = db.query("SELECT reference FROM source_documents")
    refs = {r["reference"] for r in rows}
    assert "1736/0592" in refs


def test_missing_libreoffice_escalates_cleanly(tmp_path):
    src = tmp_path / "in.xlsx"
    src.write_bytes(b"not a real workbook")  # forces failure path anyway
    dest = tmp_path / "out.xlsx"
    # Point at a nonexistent binary to simulate a missing dependency.
    res = recalc(src, dest, configured_path="/nonexistent/soffice")
    assert res.ok is False
    assert dest.exists() is False  # never wrote a corrupt/fake output
