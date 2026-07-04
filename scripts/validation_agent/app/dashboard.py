"""Streamlit dashboard for the DataBossX Validation Agent.

Shows run controls, live state from the append-only DB, gate scorecard, spend
tracker, source/escalation status, and export links. Long operations run
synchronously but log progress to the DB, which the dashboard reflects on
refresh. The dashboard never blocks core logic permanently.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the agent root importable when launched via `streamlit run`.
AGENT_ROOT = Path(__file__).resolve().parent.parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import streamlit as st

from config.settings import get_settings
from db.db_client import DatabaseManager
from core.orchestrator import Orchestrator


def _db(settings) -> DatabaseManager:
    return DatabaseManager(settings.db_path)


def main() -> None:
    st.set_page_config(page_title="DataBossX Validation Agent", layout="wide")
    settings = get_settings(refresh=True)
    settings.ensure_dirs()

    st.title("DataBossX — Automated Validation & Escalation Agent")
    mode = "DRY-RUN" if settings.dry_run else "LIVE"
    st.caption(f"Mode: **{mode}** · Spend cap: **${settings.api_cap_usd}** · "
               f"Max iterations: **{settings.max_iterations}**")

    with st.sidebar:
        st.header("Run controls")
        wb_path = st.text_input("Workbook path (.xlsx/.xlsm)", value="")
        examiner_ok = st.checkbox("Examiner pre-approves paid retrieval", False)
        start = st.button("Start validation", type="primary")
        st.divider()
        st.subheader("Config (secrets redacted)")
        st.json(settings.safe_dump())
        st.divider()
        st.write(f"Outputs: `{settings.outputs_dir}`")
        st.write(f"OKCounty configured: **{settings.okcounty_configured()}**")

    if start:
        if not wb_path or not Path(wb_path).exists():
            st.error("Provide a valid workbook path.")
        else:
            with st.spinner("Running validation pipeline…"):
                orch = Orchestrator(settings)
                try:
                    result = orch.run(
                        wb_path, examiner_approved_spend=examiner_ok)
                finally:
                    orch.close()
            st.session_state["last_run_id"] = result.run_id
            st.success(f"Run {result.run_id} finished: **{result.status}** "
                       f"after {result.iterations} iteration(s).")

    db = _db(settings)
    runs = db.get_runs(limit=25)
    if not runs:
        st.info("No runs yet. Start one from the sidebar.")
        db.close()
        return

    run_ids = [r["run_id"] for r in runs]
    default = st.session_state.get("last_run_id", run_ids[0])
    idx = run_ids.index(default) if default in run_ids else 0
    run_id = st.selectbox("Select run", run_ids, index=idx)

    run = next(r for r in runs if r["run_id"] == run_id)
    terminal = db.get_terminal_status(run_id) or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Run ID", run_id.replace("validation_run_", ""))
    c2.metric("Mode", run["mode"])
    c3.metric("Status", terminal.get("status", run["status"]))
    c4.metric("Final state", terminal.get("final_state", "-"))

    # Gate scorecard
    st.subheader("Gate scorecard")
    results = db.get_validation_results(run_id)
    if results:
        latest_iter = max(r["iteration"] for r in results)
        latest = [r for r in results if r["iteration"] == latest_iter]
        st.dataframe(
            [{"Gate": r["gate_name"], "Status": r["status"],
              "Severity": r["severity"], "Repairable": bool(r["repairable"]),
              "Subject": r["affected_subject"], "Reason": r["reason"]}
             for r in latest],
            use_container_width=True, hide_index=True,
        )

    # Spend tracker
    st.subheader("Spend tracker")
    spent = db.cumulative_spend(run_id)
    cap = float(settings.api_cap_usd)
    st.progress(min(spent / cap, 1.0) if cap else 0.0)
    st.write(f"Cumulative **${spent:.2f}** of **${cap:.2f}** "
             f"(remaining ${cap - spent:.2f})")

    colA, colB = st.columns(2)
    with colA:
        st.subheader("Source documents / missing")
        docs = db.get_source_documents(run_id)
        st.dataframe(
            [{"Reference": d["reference_key"], "Type": d["doc_type"],
              "Status": d["status"], "Origin": d["source_origin"]}
             for d in docs] or [{"Reference": "(none)"}],
            use_container_width=True, hide_index=True)
    with colB:
        st.subheader("Human escalation queue")
        escs = db.get_escalations(run_id)
        st.dataframe(
            [{"Category": e["category"], "Severity": e["severity"],
              "Subject": e["subject"], "Reason": e["reason"]}
             for e in escs] or [{"Category": "(none)"}],
            use_container_width=True, hide_index=True)

    st.subheader("Workbook versions")
    versions = db.get_workbook_versions(run_id)
    st.dataframe(
        [{"Version": v["version_label"], "Origin": v["origin"],
          "File": v["file_name"], "SHA-256": (v["sha256"] or "")[:16] + "…"}
         for v in versions] or [{"Version": "(none)"}],
        use_container_width=True, hide_index=True)

    st.subheader("Latest report exports")
    exports = db.get_report_exports(run_id)
    for e in exports:
        st.write(f"- **{e['export_type']}** · `{e['file_path']}`")

    # Download buttons for the examiner package and the improved report so the
    # examiner can retrieve exports directly from the dashboard (cross-platform,
    # unlike a server-side "open folder"). Plus an explicit open-folder helper.
    dl_cols = st.columns(3)
    _download_button(dl_cols[0], exports, ("zip",), "⬇ Examiner package (zip)",
                     "application/zip")
    _download_button(dl_cols[1], exports, ("markdown",), "⬇ Improved report (md)",
                     "text/markdown")
    _download_button(dl_cols[2], exports, ("pdf", "docx"),
                     "⬇ Certification packet", "application/octet-stream")

    run_dir = run["run_dir"]
    if dl_cols[0].button("Open run folder", key="open_folder"):
        _open_path(run_dir)
    st.caption(f"Run folder: `{run_dir}`  ·  exports in `{run_dir}/exports`")

    db.close()


def _download_button(col, exports, types, label, mime) -> None:
    """Render a download button for the newest export whose type is in ``types``.

    Never fabricates: if the file is missing the button is simply not shown."""
    match = None
    for e in exports:
        if e["export_type"] in types and Path(e["file_path"]).exists():
            match = e  # exports are ordered oldest->newest; keep the last match
    if not match:
        return
    p = Path(match["file_path"])
    try:
        data = p.read_bytes()
    except OSError:
        return
    col.download_button(label, data=data, file_name=p.name, mime=mime,
                        key=f"dl_{match['id']}")


def _open_path(path: str) -> None:
    """Best-effort open the run folder on the host running Streamlit."""
    import os
    import subprocess
    import sys
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as exc:  # never crash the dashboard over a UI convenience
        import streamlit as st
        st.warning(f"Could not open folder automatically: {exc}")


if __name__ == "__main__":
    main()
