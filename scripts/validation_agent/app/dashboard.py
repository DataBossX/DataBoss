"""Streamlit dashboard for the DataBossX Validation Agent.

Imports cleanly with no side effects (so it can be imported in tests). The
Streamlit UI only renders when executed via ``streamlit run``. Long operations
log to the DB and the UI reflects current DB state rather than blocking forever.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the agent package importable when launched by Streamlit.
_AGENT_ROOT = Path(__file__).resolve().parent.parent
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))

from config.settings import get_settings
from db.db_client import DatabaseManager
from db.audit_logger import AuditLogger
from core.orchestrator import Orchestrator


def _open_db(settings):
    return DatabaseManager(settings.db_path, settings.schema_path)


def render() -> None:  # pragma: no cover - requires a running Streamlit server
    import pandas as pd
    import streamlit as st

    st.set_page_config(page_title="DataBossX Validation Agent", layout="wide")
    settings = get_settings(reload=True)
    st.title("DataBossX Validation Agent")
    st.caption("Append-only · dry-run by default · spend-capped at $100.00 · never fabricates facts")

    db = _open_db(settings)
    audit = AuditLogger(db)

    with st.sidebar:
        st.header("Configuration")
        cfg = settings.safe_dump()
        st.write({k: cfg[k] for k in ("dry_run", "live_source_mode", "api_cap_usd",
                                      "max_iterations", "credentials_present",
                                      "live_retrieval_allowed")})
        st.divider()
        workbook = st.text_input("Workbook path", value="")
        prospect = st.text_input("Prospect", value="")
        start = st.button("Start validation", type="primary")

    if start and workbook:
        if not Path(workbook).is_file():
            st.error(f"Workbook not found: {workbook}")
        else:
            with st.status("Running validation…", expanded=True) as status:
                orch = Orchestrator(settings, db, audit)
                result = orch.run(Path(workbook), prospect=prospect)
                status.update(label=f"Done — {result['final_status']}", state="complete")
            st.success(f"Run {result['run_id']} finished: {result['final_status']}")

    # Live DB views.
    runs = db.query("SELECT run_id, created_at, mode, workbook_path FROM runs ORDER BY id DESC LIMIT 20")
    st.subheader("Runs")
    if runs:
        st.dataframe(pd.DataFrame([dict(r) for r in runs]), use_container_width=True)
        latest = runs[0]["run_id"]
        final = audit.final_status(latest) or "PENDING"
        col1, col2, col3 = st.columns(3)
        col1.metric("Latest run", latest)
        col2.metric("Final status", final)
        spend = db.query("SELECT cumulative_usd FROM spend_ledger WHERE allowed=1 ORDER BY id DESC LIMIT 1")
        col3.metric("Spend (USD)", spend[0]["cumulative_usd"] if spend else "0.00")

        st.subheader("Gate scorecard (latest run)")
        gr = db.query("SELECT gate_name, status, severity, repairable, affected_subject, reason "
                      "FROM validation_results WHERE run_id=? ORDER BY id", (latest,))
        if gr:
            st.dataframe(pd.DataFrame([dict(r) for r in gr]), use_container_width=True)

        st.subheader("Escalation queue")
        esc = db.query("SELECT priority, failure_class, subject, needed_document, recommended_action "
                       "FROM escalations WHERE run_id=? ORDER BY id", (latest,))
        st.dataframe(pd.DataFrame([dict(r) for r in esc]) if esc else pd.DataFrame(),
                     use_container_width=True)

        st.subheader("Exports")
        ex = db.query("SELECT kind, path, sha256 FROM report_exports WHERE run_id=? ORDER BY id", (latest,))
        st.dataframe(pd.DataFrame([dict(r) for r in ex]) if ex else pd.DataFrame(),
                     use_container_width=True)
    else:
        st.info("No runs yet. Provide a workbook path and click Start validation.")

    db.close()


if __name__ == "__main__":  # pragma: no cover
    render()
