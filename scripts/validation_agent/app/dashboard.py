"""Streamlit control dashboard for the DataBossX validation agent.

Importing this module must never launch the server or require a running
Streamlit context (the test suite imports it). All Streamlit rendering lives in
``main()``, guarded by ``__main__``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import Settings, load_settings  # noqa: E402
from db.audit_logger import AuditLogger  # noqa: E402
from db.db_client import DatabaseManager  # noqa: E402


def _open_db(settings: Settings) -> DatabaseManager:
    db = DatabaseManager(settings.db_path)
    db.initialize_schema()
    return db


def list_workbooks(settings: Settings) -> List[Path]:
    """Discover candidate workbooks under the DataBossX tree."""
    seen: Dict[str, Path] = {}
    for base in [settings.databossx_root, settings.databossx_root / "workbooks",
                 settings.outputs_dir]:
        if base.exists():
            for p in base.rglob("*.xls[xm]"):
                seen[str(p)] = p
    return sorted(seen.values(), key=lambda p: p.name)


def gather_dashboard_state(db: DatabaseManager) -> Dict[str, Any]:
    """Pure data-collection (no Streamlit) so it is unit-testable."""
    def q(sql: str) -> List[Dict[str, Any]]:
        try:
            return db.query(sql)
        except Exception:  # noqa: BLE001
            return []

    return {
        "latest_run": q("SELECT * FROM latest_run_status ORDER BY created_at DESC LIMIT 1"),
        "scorecard": q("SELECT * FROM validation_scorecard ORDER BY gate_name"),
        "spend": q("SELECT * FROM spend_summary"),
        "sources": q("SELECT status, COUNT(*) AS n FROM source_documents GROUP BY status"),
        "missing_docs": q(
            "SELECT reference_key, detail FROM source_documents "
            "WHERE status IN ('missing','blocked','failed') ORDER BY created_at DESC LIMIT 100"
        ),
        "escalations": q("SELECT * FROM open_escalations LIMIT 100"),
        "exports": q("SELECT * FROM report_exports ORDER BY created_at DESC LIMIT 50"),
        "versions": q("SELECT * FROM workbook_versions ORDER BY created_at DESC LIMIT 50"),
    }


def main() -> None:  # pragma: no cover - requires streamlit runtime
    import pandas as pd
    import streamlit as st

    st.set_page_config(page_title="DataBossX Validation Agent", layout="wide")
    settings = load_settings()
    db = _open_db(settings)
    audit = AuditLogger(db)

    st.title("DataBossX Validation Agent")
    st.caption("High-integrity title validation • append-only • dry-run by default")

    with st.sidebar:
        st.header("Configuration")
        st.json(settings.as_safe_dict())
        st.metric("API cap (USD)", str(settings.api_cap_usd))
        st.metric("Max iterations", settings.max_iterations)

    # 1. workbook selector + 2. start button
    workbooks = list_workbooks(settings)
    labels = [str(p) for p in workbooks]
    col1, col2 = st.columns([3, 1])
    with col1:
        chosen = st.selectbox("Workbook", labels) if labels else None
        uploaded = st.text_input("…or path to workbook", value=chosen or "")
    with col2:
        start = st.button("Start Validation", type="primary")

    if start and uploaded:
        from core.orchestrator import Orchestrator

        audit.log_launcher_event("dashboard_run_start", uploaded)
        with st.spinner("Running validation…"):
            result = Orchestrator(settings, db, audit).run(Path(uploaded))
        st.success(f"Run {result.run_id} → {result.final_state.value} "
                   f"(certified={result.certified})")

    state = gather_dashboard_state(db)

    # 3/4/5. active run id, state, iteration
    if state["latest_run"]:
        lr = state["latest_run"][0]
        c = st.columns(4)
        c[0].metric("Active Run", lr.get("run_id", "—"))
        c[1].metric("State", lr.get("state", "—"))
        c[2].metric("Iteration", lr.get("iteration", 0))
        c[3].metric("Status", lr.get("status", "—"))

    # 6. validation scorecard
    st.subheader("Validation Scorecard")
    if state["scorecard"]:
        st.dataframe(pd.DataFrame(state["scorecard"]), use_container_width=True)

    # 7. spend tracker
    st.subheader("Spend Tracker")
    st.dataframe(pd.DataFrame(state["spend"]) if state["spend"] else pd.DataFrame(),
                 use_container_width=True)

    # 8/9. source retrieval status + missing docs
    left, right = st.columns(2)
    with left:
        st.subheader("Source Retrieval")
        st.dataframe(pd.DataFrame(state["sources"]) if state["sources"] else pd.DataFrame())
    with right:
        st.subheader("Missing / Blocked Documents")
        st.dataframe(pd.DataFrame(state["missing_docs"]) if state["missing_docs"] else pd.DataFrame())

    # 10. escalation queue
    st.subheader("Human Escalation Queue")
    st.dataframe(pd.DataFrame(state["escalations"]) if state["escalations"] else pd.DataFrame(),
                 use_container_width=True)

    # 11/12. exports + versions
    left2, right2 = st.columns(2)
    with left2:
        st.subheader("Latest Exports")
        st.dataframe(pd.DataFrame(state["exports"]) if state["exports"] else pd.DataFrame())
    with right2:
        st.subheader("Workbook Versions")
        st.dataframe(pd.DataFrame(state["versions"]) if state["versions"] else pd.DataFrame())

    # 13/14. certification/escalation status + output path
    if state["latest_run"]:
        lr = state["latest_run"][0]
        st.subheader("Result")
        st.info(f"Status: {lr.get('status')} — output folder: {lr.get('run_folder')}")


if __name__ == "__main__":  # pragma: no cover
    main()
