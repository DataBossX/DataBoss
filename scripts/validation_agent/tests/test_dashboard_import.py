"""Dashboard must import cleanly and expose testable data collection."""

from __future__ import annotations

import importlib


def test_dashboard_imports():
    module = importlib.import_module("app.dashboard")
    assert hasattr(module, "main")
    assert hasattr(module, "gather_dashboard_state")
    assert hasattr(module, "list_workbooks")


def test_gather_dashboard_state_on_empty_db(db):
    from app.dashboard import gather_dashboard_state

    state = gather_dashboard_state(db)
    # keys present, all lists, no exceptions on an empty DB
    for key in ("latest_run", "scorecard", "spend", "sources",
                "missing_docs", "escalations", "exports", "versions"):
        assert key in state
        assert isinstance(state[key], list)
