"""Streamlit dashboard — Phase 7, the Examiner's interface.

A thin view over ``DashboardData``: it renders the live Scorecard, the
append-only Audit Trail, and the three HITL escalation forms (Gap Resolver,
Factual Arbiter, Budget Override), and routes every form submission back
through the tested resolution methods. No business logic lives here.

Run with:  streamlit run scripts/title_agent/frontend/app.py
"""

from __future__ import annotations

import os

from ..core.config import config
from ..core.memory import SQLiteManager
from .dashboard_data import DashboardData

try:
    import streamlit as st
except ImportError as exc:  # pragma: no cover - only hit when streamlit absent
    raise SystemExit(
        "Streamlit is required for the dashboard: pip install streamlit"
    ) from exc


def _data() -> DashboardData:
    config.ensure_dirs()
    return DashboardData(SQLiteManager(config.DB_PATH))


def _examiner_id() -> str:
    return st.session_state.get("examiner_id") or os.getenv("EXAMINER_ID", "examiner")


def render_scorecard(data: DashboardData) -> None:
    sc = data.scorecard()
    st.title("DataBossX — Title Validation & Repair Agent")
    st.caption(
        f"Prospect {sc.prospect_id} · Section {sc.section} · {sc.county} County, "
        f"{sc.state} · {sc.well} · {sc.tract_count} tracts · "
        f"{sc.gross_acre_target:.2f} gross acres"
    )

    top = st.columns(4)
    top[0].metric("Loop state", sc.loop_state)
    top[1].metric("Certified", "YES" if sc.certified else "NO")
    top[2].metric(
        "Budget",
        f"${sc.budget.spent:.2f} / ${sc.budget.cap:.2f}",
        delta=f"${sc.budget.remaining:.2f} left",
    )
    version_label = sc.latest_version.version_label if sc.latest_version else "—"
    top[3].metric("Latest version", version_label)

    st.subheader("Quality Gates")
    cols = st.columns(len(sc.gates))
    for col, gate in zip(cols, sc.gates):
        icon = "✅" if gate.passed else "⚠️"
        col.markdown(f"**{icon} {gate.gate}**")
        if gate.open_escalations:
            col.caption(f"{gate.open_escalations} open")


def render_escalations(data: DashboardData) -> None:
    st.subheader("Escalation Queue (Human-in-the-Loop)")
    queue = data.open_queue()
    examiner = _examiner_id()

    if not any((queue.gap_resolver, queue.factual_arbiter, queue.budget_override, queue.other)):
        st.success("No open escalations. The agent has nothing waiting on you.")
        return

    for esc in queue.gap_resolver:
        with st.form(f"gap_{esc.id}"):
            st.markdown(f"**Gap Resolver — {esc.reference}**")
            st.caption(esc.proof.get("detail", ""))
            st.info(
                "AI cannot assume heirs or prior unrecorded deeds. Supply the "
                "missing Book/Page or approve a Title Defect Requirement."
            )
            book_page = st.text_input("Missing Book/Page", key=f"bp_{esc.id}")
            tdr = st.text_input("…or approve Title Defect Requirement", key=f"tdr_{esc.id}")
            if st.form_submit_button("Resolve gap"):
                data.resolve_gap(
                    esc.id, examiner,
                    book_page=book_page or None,
                    title_defect_requirement=tdr or None,
                )
                st.rerun()

    for esc in queue.factual_arbiter:
        with st.form(f"arb_{esc.id}"):
            st.markdown(f"**Factual Arbiter — {esc.reference}**")
            st.caption(esc.proof.get("detail", ""))
            st.warning("The API and the workbook disagree. Select the ground truth.")
            truth = st.text_input("Ground truth value", key=f"gt_{esc.id}")
            if st.form_submit_button("Set ground truth"):
                data.resolve_factual(esc.id, examiner, ground_truth=truth)
                st.rerun()

    for esc in queue.budget_override:
        with st.form(f"bud_{esc.id}"):
            st.markdown(f"**Budget Override — {esc.reference}**")
            st.caption(esc.proof.get("detail", ""))
            new_cap = st.number_input(
                "Authorize new cap ($)", min_value=0.0, step=25.0, key=f"cap_{esc.id}"
            )
            note = st.text_input("…or note manual document upload", key=f"note_{esc.id}")
            if st.form_submit_button("Apply budget decision"):
                data.resolve_budget(
                    esc.id, examiner,
                    authorize_increase_to=new_cap or None,
                    manual_document_note=note or None,
                )
                st.rerun()

    for esc in queue.other:
        st.write(f"{esc.category} — {esc.reference}: {esc.proof.get('detail', '')}")


def render_audit(data: DashboardData) -> None:
    st.subheader("Audit Trail (append-only)")
    rows = [
        {
            "time": r.timestamp,
            "action": r.action,
            "reference": r.reference,
            "result": r.result,
            "actor": r.actor,
        }
        for r in data.audit_trail(limit=200)
    ]
    st.dataframe(rows, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="DataBossX Title Agent", layout="wide")
    with st.sidebar:
        st.text_input("Examiner ID", key="examiner_id", value=_examiner_id())
    data = _data()
    render_scorecard(data)
    render_escalations(data)
    render_audit(data)


if __name__ == "__main__":
    main()
