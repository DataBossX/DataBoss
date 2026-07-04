"""End-to-end orchestrator loop: certify, safe-repair-then-certify, escalate.

These exercise the full state machine wiring (ingest → validate → triage →
repair → recalc → iterate → certify/escalate) that unit tests only touch in
isolation.
"""

from __future__ import annotations

from pathlib import Path

from core.enums import GateStatus, State
from core.orchestrator import Orchestrator
from tests.fixtures.make_workbook import (
    build_certifiable_workbook,
    materialize_sources,
)


def _run(settings, db, audit, workbook: Path, docs: Path, ts: str):
    object.__setattr__(settings, "extra_source_dirs", [docs])
    return Orchestrator(settings, db, audit).run(workbook, timestamp=ts)


def test_clean_workbook_certifies_without_repair(settings, db, audit, tmp_path):
    wb = build_certifiable_workbook(tmp_path / "clean.xlsx", defect="none")
    docs = materialize_sources(wb, tmp_path / "docs")
    result = _run(settings, db, audit, wb, docs, "20260704_100000")

    assert result.final_state == State.CERTIFY
    assert result.certified is True
    # no repair was needed
    repairs = db.query("SELECT * FROM automated_repairs WHERE run_id=?", (result.run_id,))
    assert repairs == []
    # a certified workbook copy was exported
    exports = {e["export_type"] for e in result.export_files}
    assert "certified_workbook" in exports


def test_acreage_total_override_is_repaired_then_certifies(settings, db, audit, tmp_path):
    wb = build_certifiable_workbook(tmp_path / "override.xlsx", defect="acreage_total")
    docs = materialize_sources(wb, tmp_path / "docs")
    result = _run(settings, db, audit, wb, docs, "20260704_100001")

    assert result.final_state == State.CERTIFY, [
        (r.gate_name, r.status.value, r.reason) for r in result.results
        if r.status in (GateStatus.FAIL, GateStatus.ESCALATE)
    ]
    assert result.certified is True
    assert result.iterations >= 1
    repairs = db.query(
        "SELECT * FROM automated_repairs WHERE run_id=? AND status='applied'",
        (result.run_id,),
    )
    assert repairs, "expected an applied repair for the acreage total"
    assert "SUM(" in (repairs[0]["detail"] or "")
    # a new version was produced (v001) and never overwrote v000
    versions = db.query(
        "SELECT version_index, origin FROM workbook_versions WHERE run_id=? "
        "ORDER BY version_index", (result.run_id,)
    )
    assert versions[0]["origin"] == "source_copy"
    assert any(v["origin"] == "repair" for v in versions)


def test_formula_column_defect_is_repaired_then_certifies(settings, db, audit, tmp_path):
    wb = build_certifiable_workbook(tmp_path / "fcol.xlsx", defect="formula_column")
    docs = materialize_sources(wb, tmp_path / "docs")
    result = _run(settings, db, audit, wb, docs, "20260704_100002")

    assert result.final_state == State.CERTIFY
    assert result.certified is True
    repairs = db.query(
        "SELECT * FROM automated_repairs WHERE run_id=? AND status='applied'",
        (result.run_id,),
    )
    assert repairs


def test_missing_sources_escalate_never_certify(settings, db, audit, tmp_path):
    # Same workbook, but sources are NOT materialized -> must escalate.
    wb = build_certifiable_workbook(tmp_path / "nosrc.xlsx", defect="none")
    empty = tmp_path / "empty"
    empty.mkdir()
    result = _run(settings, db, audit, wb, empty, "20260704_100003")

    assert result.final_state == State.ESCALATE
    assert result.certified is False
    assert result.escalations
    # no certified workbook export in an escalation
    assert "certified_workbook" not in {e["export_type"] for e in result.export_files}


def test_unsafe_failure_blocks_repair_even_with_safe_defect(settings, db, audit, tmp_path):
    # A repairable acreage-total defect AND missing sources: the unsafe
    # escalation must halt the repair path (no repair attempted).
    wb = build_certifiable_workbook(tmp_path / "mixed.xlsx", defect="acreage_total")
    empty = tmp_path / "empty2"
    empty.mkdir()
    result = _run(settings, db, audit, wb, empty, "20260704_100004")

    assert result.final_state == State.ESCALATE
    repairs = db.query(
        "SELECT * FROM automated_repairs WHERE run_id=? AND status='applied'",
        (result.run_id,),
    )
    assert repairs == [], "safe repair must not run while unsafe escalations are open"
