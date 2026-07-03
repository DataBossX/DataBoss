"""StreamlitDashboardController -- the human examiner interface.

Renders live run state, the validation scorecard, API spend against the $100
cap, the human escalation queue, and the final certification status -- all read
directly from the append-only SQLite memory layer.  The dashboard is strictly a
*reader*: it never mutates the DB and never blocks the core loop.

Launch:
    streamlit run scripts/validation_agent/app/dashboard.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow ``streamlit run path/to/dashboard.py`` (no package context) to import
# the validation_agent package.
_PKG_PARENT = Path(__file__).resolve().parents[2]
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from validation_agent.config.settings import config          # noqa: E402
from validation_agent.db.db_client import DatabaseManager     # noqa: E402


class StreamlitDashboardController:
    def __init__(self, database: DatabaseManager | None = None) -> None:
        self.db = database or DatabaseManager()

    def runs(self) -> list[dict]:
        try:
            return self.db.query(
                "SELECT id, source_path, created_at FROM runs "
                "ORDER BY created_at DESC")
        except Exception:
            return []

    def latest_state(self, run_id: str) -> dict | None:
        return self.db.query_one(
            "SELECT iteration, state, detail, created_at FROM run_events "
            "WHERE run_id=? ORDER BY id DESC LIMIT 1", (run_id,))

    def scorecard(self, run_id: str) -> list[dict]:
        return self.db.query(
            "SELECT gate_id, gate_name, status, detail FROM validation_results "
            "WHERE run_id=? AND iteration=(SELECT MAX(iteration) FROM "
            "validation_results WHERE run_id=?) ORDER BY gate_id",
            (run_id, run_id))

    def escalations(self, run_id: str) -> list[dict]:
        return self.db.query(
            "SELECT gate_name, category, severity, payload FROM escalations "
            "WHERE run_id=? ORDER BY id", (run_id,))

    def total_spend(self) -> float:
        return float(self.db.scalar(
            "SELECT COALESCE(SUM(amount),0) FROM spend_ledger") or 0.0)


def render() -> None:
    import streamlit as st

    st.set_page_config(page_title="DataBossX Validation Agent", layout="wide")
    st.title("DataBossX -- Automated Validation & Repair Agent")

    controller = StreamlitDashboardController()
    runs = controller.runs()
    if not runs:
        st.info("No runs yet. Execute `python -m validation_agent.main <workbook>`.")
        return

    run_ids = [r["id"] for r in runs]
    run_id = st.sidebar.selectbox("Active run", run_ids)

    spend = controller.total_spend()
    col1, col2, col3 = st.columns(3)
    state = controller.latest_state(run_id) or {}
    col1.metric("Loop state", state.get("state", "-"))
    col1.caption(f"iteration {state.get('iteration', '-')}")
    col2.metric("API spend", f"${spend:.2f}", help="Hard cap $100.00")
    col2.progress(min(spend / config.api_hard_cap_usd, 1.0))
    esc = controller.escalations(run_id)
    col3.metric("Escalations", len(esc))

    st.subheader("Validation Scorecard")
    scorecard = controller.scorecard(run_id)
    if scorecard:
        st.table(scorecard)
    else:
        st.write("No gate results recorded yet.")

    st.subheader("Human Escalation Queue")
    if not esc:
        st.success("No open escalations.")
    for row in esc:
        with st.expander(f"[{row['severity']}] {row['gate_name']} -- {row['category']}"):
            try:
                st.json(json.loads(row["payload"]))
            except (json.JSONDecodeError, TypeError):
                st.write(row["payload"])

    certified = any(g["gate_id"] == 12 and g["status"] == "pass" for g in scorecard) \
        and not esc
    st.subheader("Certification Status")
    if certified:
        st.success("Workbook certified (pending examiner approval).")
    else:
        st.warning("Not certified -- see escalation queue.")


if __name__ == "__main__":
    render()
