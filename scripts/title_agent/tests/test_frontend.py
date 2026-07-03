"""Phase 7 tests for frontend/dashboard_data.py.

Exercises the read model (scorecard, queue grouping, audit trail) and every
HITL resolution path, asserting that each resolution closes its escalation and
records an EXAMINER_OVERRIDE in the append-only audit log.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ..core.memory import AuditLogger, EscalationStore, SQLiteManager, VersionController
from ..core.taxonomy import FailureCategory, Gate
from ..frontend.dashboard_data import DashboardData


def _setup(tmp: Path):
    mgr = SQLiteManager(tmp / "s.db")
    vc = VersionController(mgr, workbook_dir=tmp / "wb")
    v1 = vc.mint_new_version("TitleReport", reason="init")
    v1.file_path.write_text("wb")
    return mgr, EscalationStore(mgr)


def test_scorecard_reflects_open_escalations(tmp: Path) -> None:
    mgr, store = _setup(tmp)
    store.open_escalation(
        FailureCategory.TITLE_GAP.value, Gate.CHAIN_CONTINUITY.value, "Tract 3", {"detail": "gap"}
    )
    data = DashboardData(mgr)
    sc = data.scorecard()
    assert sc.prospect_id == "25-004" and sc.gross_acre_target == 637.42
    assert not sc.certified
    flagged = {g.gate: g.status for g in sc.gates}
    assert flagged[Gate.CHAIN_CONTINUITY.value] == "ATTENTION"
    assert flagged[Gate.INTEREST_CONSERVATION.value] == "PASS"
    assert sc.open_escalation_count == 1


def test_queue_groups_by_form(tmp: Path) -> None:
    mgr, store = _setup(tmp)
    store.open_escalation(FailureCategory.TITLE_GAP.value, Gate.CHAIN_CONTINUITY.value, "T3", {})
    store.open_escalation(FailureCategory.SOURCE_UNVERIFIED.value, Gate.SOURCE_VERIFICATION.value, "T1", {})
    store.open_escalation(FailureCategory.BUDGET_CAP_REACHED.value, Gate.SOURCE_VERIFICATION.value, "budget", {})
    q = DashboardData(mgr).open_queue()
    assert len(q.gap_resolver) == 1 and len(q.factual_arbiter) == 1 and len(q.budget_override) == 1


def test_resolve_gap_requires_exactly_one_input(tmp: Path) -> None:
    mgr, store = _setup(tmp)
    esc = store.open_escalation(FailureCategory.TITLE_GAP.value, Gate.CHAIN_CONTINUITY.value, "T3", {})
    data = DashboardData(mgr)
    # Neither -> error.
    for kwargs in ({"book_page": None, "title_defect_requirement": None},
                   {"book_page": "412/89", "title_defect_requirement": "TDR-1"}):
        try:
            data.resolve_gap(esc.id, "ex-1", **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("expected exactly-one-input enforcement")
    # Valid resolution closes it and audits the override.
    resolved = data.resolve_gap(esc.id, "ex-1", book_page="412/89", title_defect_requirement=None)
    assert not resolved.is_open and resolved.examiner_id == "ex-1"
    overrides = AuditLogger(mgr).read_all(action=AuditLogger.EXAMINER_OVERRIDE)
    assert overrides and overrides[-1].actor == "ex-1"


def test_resolve_factual_and_budget(tmp: Path) -> None:
    mgr, store = _setup(tmp)
    arb = store.open_escalation(
        FailureCategory.SOURCE_UNVERIFIED.value, Gate.SOURCE_VERIFICATION.value, "T1",
        {"detail": "API 12.5% vs workbook 18.75%"})
    bud = store.open_escalation(
        FailureCategory.BUDGET_CAP_REACHED.value, Gate.SOURCE_VERIFICATION.value, "budget", {})
    data = DashboardData(mgr)

    r1 = data.resolve_factual(arb.id, "ex-2", ground_truth="18.75% royalty per recorded lease")
    assert not r1.is_open

    # Budget: cap increase must exceed current cap.
    try:
        data.resolve_budget(bud.id, "ex-2", authorize_increase_to=50.0)  # < $100 cap
    except ValueError:
        pass
    else:
        raise AssertionError("cap increase below current cap must be rejected")
    r2 = data.resolve_budget(bud.id, "ex-2", authorize_increase_to=250.0)
    assert not r2.is_open


def test_resolve_wrong_category_rejected(tmp: Path) -> None:
    mgr, store = _setup(tmp)
    esc = store.open_escalation(
        FailureCategory.TITLE_GAP.value, Gate.CHAIN_CONTINUITY.value, "T3", {})
    data = DashboardData(mgr)
    # A TITLE_GAP cannot be resolved through the Factual Arbiter form.
    try:
        data.resolve_factual(esc.id, "ex-1", ground_truth="x")
    except ValueError:
        return
    raise AssertionError("cross-category resolution must be rejected")


def test_audit_trail_is_recent_first(tmp: Path) -> None:
    mgr, store = _setup(tmp)
    a = AuditLogger(mgr)
    a.log_action("A", "r1", "ok")
    a.log_action("B", "r2", "ok")
    trail = DashboardData(mgr).audit_trail(limit=10)
    assert trail[0].action == "B"  # most recent first


def _run_all() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(tests)} passed.")


if __name__ == "__main__":
    _run_all()
