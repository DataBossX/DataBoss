"""Streamlit dashboard (Component 1) — the default interface.

Pure reader of the run DB + version tree. Enqueues a run; never mutates the
workbook directly. Launch: ``streamlit run app.py``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import config
from .models import GateId

try:
    import streamlit as st
except ImportError:  # allow import without streamlit for tests
    st = None  # type: ignore


_GATE_LABEL = {
    GateId.G1_CONSERVATION: "G1 Interest Conservation",
    GateId.G2_FOOTING: "G2 Pro-Rata Footing",
    GateId.G3_CHAIN: "G3 Chain Continuity",
    GateId.G4_INSTRUMENT: "G4 Instrument Audit",
    GateId.G5_OGL: "G5 OGL Register",
}


def _list_runs() -> list[Path]:
    out = config.OUTPUT_DIR
    if not out.exists():
        return []
    return sorted((p for p in out.glob("*/run.db")), key=lambda p: p.stat().st_mtime, reverse=True)


def _latest_scorecard(conn: sqlite3.Connection, run_id: str) -> dict[str, str]:
    cur = conn.execute(
        "SELECT gate, passed, severity FROM validation_results WHERE run_id=? "
        "AND version=(SELECT MAX(version) FROM validation_results WHERE run_id=?)",
        (run_id, run_id),
    )
    scores: dict[str, str] = {}
    for row in cur:
        prev = scores.get(row["gate"])
        mark = "PASS" if row["passed"] else row["severity"]
        if prev != "FAIL":
            scores[row["gate"]] = mark
    return scores


def render_dashboard() -> None:  # pragma: no cover - UI
    assert st is not None, "streamlit is required to render the dashboard"
    st.set_page_config(page_title="DataBossX — Validation & Repair Agent", layout="wide")
    st.title("DataBossX — Validation & Repair Agent")
    st.caption("Section 31-12N-24W, Roger Mills Co., OK · Prospect 25-004 · 637.42 ac")

    runs = _list_runs()
    if not runs:
        st.info("No runs yet. Start one from the CLI: `python -m validation_agent.cli run <workbook.xlsx>`")
        return

    labels = [p.parent.name for p in runs]
    choice = st.selectbox("Run", labels)
    db_path = next(p for p in runs if p.parent.name == choice)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (choice,)).fetchone()
    col1, col2, col3 = st.columns(3)
    col1.metric("Loop state", run["state"] if run else "—")
    col2.metric("Versions", conn.execute(
        "SELECT COUNT(*) n FROM versions WHERE run_id=?", (choice,)).fetchone()["n"])
    col3.metric("API spend", f"${_spend(conn, choice):.2f}")

    st.subheader("Quality-gate scorecard")
    scores = _latest_scorecard(conn, choice)
    cols = st.columns(len(_GATE_LABEL))
    for c, (gate, label) in zip(cols, _GATE_LABEL.items()):
        mark = scores.get(gate.value, "—")
        c.metric(label, mark, delta=("" if mark == "PASS" else mark))

    st.subheader("Validation results (latest version)")
    st.dataframe(_rows(conn,
        "SELECT version, gate, passed, severity, message, metric, expected "
        "FROM validation_results WHERE run_id=? ORDER BY id DESC LIMIT 200", (choice,)))

    st.subheader("Fixes applied")
    st.dataframe(_rows(conn,
        "SELECT version, strategy_id, risk, coord, before, after FROM fixes "
        "WHERE run_id=? ORDER BY id", (choice,)))

    st.subheader("Escalations")
    st.dataframe(_rows(conn,
        "SELECT version, gate, category, reason FROM escalations "
        "WHERE run_id=? ORDER BY id", (choice,)))


def _spend(conn, run_id) -> float:
    r = conn.execute(
        "SELECT COALESCE(SUM(CAST(cost_usd AS REAL)),0) s FROM spend_ledger WHERE run_id=?",
        (run_id,)).fetchone()
    return float(r["s"])


def _rows(conn, sql, params):
    return [dict(r) for r in conn.execute(sql, params)]


if __name__ == "__main__":  # pragma: no cover
    render_dashboard()
