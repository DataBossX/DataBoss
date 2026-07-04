"""Orchestrator: bounded iterations, always emits an output, logs transitions."""

from __future__ import annotations

from decimal import Decimal

from core.enums import State
from core.orchestrator import Orchestrator


def test_run_produces_output_and_is_bounded(settings, db, audit, valid_workbook):
    result = Orchestrator(settings, db, audit).run(valid_workbook, timestamp="20260704_020000")
    assert result.iterations <= settings.max_iterations
    # a final output was always generated
    assert result.export_files
    assert result.export_zip is not None
    # final state is terminal
    assert result.final_state in (State.CERTIFY, State.ESCALATE)


def test_state_transitions_are_logged(settings, db, audit, valid_workbook):
    result = Orchestrator(settings, db, audit).run(valid_workbook, timestamp="20260704_020001")
    transitions = db.query(
        "SELECT * FROM audit_events WHERE event_type='STATE_TRANSITION' AND run_id=?",
        (result.run_id,),
    )
    subjects = {t["subject"] for t in transitions}
    assert State.INGEST.value in subjects
    assert State.VALIDATE.value in subjects
    assert State.EVALUATE_GATES.value in subjects


def test_max_iterations_never_exceeded(settings, db, audit, valid_workbook, monkeypatch):
    # Force a tiny iteration budget and confirm the loop still terminates.
    object.__setattr__(settings, "max_iterations", 1)
    result = Orchestrator(settings, db, audit).run(valid_workbook, timestamp="20260704_020002")
    assert result.iterations <= 1
    assert result.final_state in (State.CERTIFY, State.ESCALATE)


def test_missing_sources_escalate(settings, db, audit, valid_workbook):
    # No source docs on disk -> workbook with book/page refs must escalate.
    result = Orchestrator(settings, db, audit).run(valid_workbook, timestamp="20260704_020003")
    assert result.final_state == State.ESCALATE
    assert result.certified is False
    assert result.escalations
    # every escalation is persisted for the examiner
    rows = db.query("SELECT * FROM escalations WHERE run_id=?", (result.run_id,))
    assert rows
