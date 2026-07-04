"""
Streamlit dashboard for the DataBossX Validation Agent.

Shows run state, gate scorecard, spend tracker, source status, missing docs,
escalation queue, latest exports, and workbook versions — all read from the
append-only DB. Long operations run in the orchestrator; the dashboard reflects
current DB state and never blocks the core logic forever.

Run:  streamlit run app/dashboard.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the module root is importable when Streamlit runs this file directly.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st  # noqa: E402

from config.settings import load_settings  # noqa: E402
from db.db_client import DatabaseManager  # noqa: E402
from core.orchestrator import Orchestrator  # noqa: E402


def _db(settings) -> DatabaseManager:
    settings.ensure_dirs()
    return DatabaseManager(settings.db_path)


def main() -> None:
    st.set_page_config(page_title="DataBossX Validation Agent", layout="wide")
    settings = load_settings()
    db = _db(settings)

    st.title("DataBossX Validation Agent")
    st.caption(f"Mode: **{'LIVE' if settings.live_enabled() else 'DRY-RUN'}** · "
               f"Spend cap: **${settings.api_cap_usd}** · Max iterations: **{settings.max_iterations}**")

    with st.sidebar:
        st.header("Run a validation")
        wb = st.text_input("Workbook path (.xlsx/.xlsm)", value="")
        start = st.button("Start validation", type="primary")
        st.divider()
        st.subheader("Config (secrets redacted)")
        st.json(settings.safe_dump())

    if start:
        if not wb or not Path(wb).exists():
            st.error("Workbook path is empty or does not exist.")
        else:
            with st.spinner("Running orchestrator…"):
                try:
                    res = Orchestrator(db, settings).run(wb)
                    st.session_state["last_run"] = res.run_id
                    st.success(f"Run {res.run_id} finished: {res.final_state} "
                               f"({res.iterations} iteration(s))")
                except Exception as e:
                    st.exception(e)

    # Choose a run to inspect.
    runs = db.query("SELECT run_id, workbook_name, mode, created_at FROM runs ORDER BY id DESC")
    if not runs:
        st.info("No runs yet. Enter a workbook path and click **Start validation**.")
        return
    run_ids = [r["run_id"] for r in runs]
    default = st.session_state.get("last_run", run_ids[0])
    sel = st.selectbox("Run", run_ids, index=run_ids.index(default) if default in run_ids else 0)

    # Final state from audit events.
    fin = db.query_one("SELECT message, payload_json FROM audit_events "
                       "WHERE run_id=? AND event_type='run_final' ORDER BY id DESC", (sel,))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Run", sel.replace("validation_run_", ""))
    c2.metric("Final State", (fin["message"].split("=")[-1] if fin else "running"))
    charged = db.scalar("SELECT amount_usd FROM spend_ledger WHERE run_id=? AND kind='charge' "
                        "ORDER BY id DESC", (sel,), "0.00")
    c3.metric("Spend (charged)", f"${charged}")
    c4.metric("Escalations", db.count("escalations", "run_id=?", (sel,)))

    st.subheader("Gate Scorecard")
    gates = db.query("SELECT gate_name, status, severity, repairable, reason "
                     "FROM validation_results WHERE run_id=? ORDER BY id", (sel,))
    st.dataframe([dict(g) for g in gates], use_container_width=True, hide_index=True)

    colA, colB = st.columns(2)
    with colA:
        st.subheader("Missing Documents")
        miss = db.query("SELECT reference, doc_kind, status FROM source_documents "
                        "WHERE run_id=? AND status='missing'", (sel,))
        st.dataframe([dict(m) for m in miss], use_container_width=True, hide_index=True)
        st.subheader("Workbook Versions")
        vers = db.query("SELECT version_label, origin, sha256 FROM workbook_versions "
                        "WHERE run_id=? ORDER BY id", (sel,))
        st.dataframe([dict(v) for v in vers], use_container_width=True, hide_index=True)
    with colB:
        st.subheader("Human Escalation Queue")
        esc = db.query("SELECT category, subject, recommended_action FROM escalations "
                       "WHERE run_id=? ORDER BY id", (sel,))
        st.dataframe([dict(e) for e in esc], use_container_width=True, hide_index=True)
        st.subheader("Latest Report Exports")
        exp = db.query("SELECT report_type, file_path FROM report_exports "
                       "WHERE run_id=? ORDER BY id DESC", (sel,))
        st.dataframe([dict(e) for e in exp], use_container_width=True, hide_index=True)

    run_row = db.query_one("SELECT run_folder FROM runs WHERE run_id=?", (sel,))
    if run_row:
        st.caption(f"Outputs folder: `{run_row['run_folder']}`")


if __name__ == "__main__":
    main()
