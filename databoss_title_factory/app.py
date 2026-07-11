"""Streamlit interface for DataBoss Title Factory."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

import streamlit as st

from databoss_title_factory.core import (
    build_inventory,
    build_runsheet,
    export_safe_xlsx,
    extract_and_reconcile,
    latest_run,
    run_ocr,
    run_summary,
    start_run,
)

st.set_page_config(
    page_title="DataBoss Title Factory",
    page_icon="▦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Libre+Franklin:wght@400;600;800&display=swap');
    :root {
      --ink: #102a2d; --paper: #f3f0e7; --signal: #e15b38; --rule: #b5aa92;
    }
    .stApp {
      background-color: var(--paper);
      background-image: linear-gradient(rgba(16,42,45,.035) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(16,42,45,.035) 1px, transparent 1px);
      background-size: 24px 24px;
      color: var(--ink);
      font-family: "Libre Franklin", sans-serif;
    }
    h1, h2, h3 { font-family: "Libre Franklin", sans-serif !important; letter-spacing: -.035em; }
    h1 { font-weight: 800 !important; text-transform: uppercase; }
    code, [data-testid="stMetricValue"] { font-family: "DM Mono", monospace !important; }
    [data-testid="stSidebar"] { background: #163a3d; }
    [data-testid="stSidebar"] * { color: #f3f0e7 !important; }
    [data-testid="stMetric"] {
      background: rgba(255,255,255,.46); border: 1px solid var(--rule);
      border-radius: 0; padding: 14px;
    }
    .factory-kicker {
      font: 500 .76rem "DM Mono", monospace; letter-spacing: .16em;
      color: var(--signal); text-transform: uppercase; margin-bottom: .4rem;
    }
    .safety-strip {
      border-left: 5px solid var(--signal); padding: .8rem 1rem;
      background: rgba(255,255,255,.5); font: .86rem "DM Mono", monospace;
      margin: .8rem 0 1.4rem;
    }
    .stage-label {
      display:inline-block; padding:.2rem .45rem; background:#163a3d; color:#f3f0e7;
      font:500 .72rem "DM Mono", monospace; letter-spacing:.08em; margin-right:.5rem;
    }
    .stButton > button {
      border-radius: 0; border: 1px solid #163a3d; font-weight: 700;
      text-transform: uppercase; letter-spacing: .045em; min-height: 3rem;
    }
    .stButton > button[kind="primary"] { background: #e15b38; border-color: #e15b38; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _default_root() -> str:
    return os.environ.get("DATABOSS_PROJECT_ROOT", str(Path.cwd()))


def _context(root: str):
    try:
        return latest_run(root)
    except (FileNotFoundError, ValueError):
        return None


def _run_action(label: str, action):
    with st.status(label, expanded=True) as status:
        try:
            result = action()
            status.update(label=f"{label} — complete", state="complete", expanded=False)
            st.session_state["last_result"] = result
            return result
        except Exception as exc:
            status.update(label=f"{label} — stopped", state="error", expanded=True)
            st.exception(exc)
            return None


with st.sidebar:
    st.markdown("## CONTROL DESK")
    project_root = st.text_input(
        "Project folder",
        value=st.session_state.get("project_root", _default_root()),
        help="The folder is scanned read-only. Outputs go into a dedicated versioned subfolder.",
    )
    st.session_state["project_root"] = project_root
    template_path = st.text_input(
        "Excel template (.xlsx / .xlsm)",
        value=st.session_state.get("template_path", ""),
    )
    st.session_state["template_path"] = template_path
    section = st.text_input("Section / project label", value="31-12N-24W")
    weak_threshold = st.slider(
        "Quarantine below confidence",
        min_value=0.40,
        max_value=0.95,
        value=0.65,
        step=0.01,
    )
    with st.expander("Tournament inputs (optional)"):
        st.caption("Leave blank to use the two local deterministic candidate extractors.")
        cursor_json = st.text_input("Cursor output JSON", value="")
        codex_json = st.text_input("Codex output JSON", value="")
    st.markdown("---")
    st.caption("SOURCE POLICY")
    st.markdown("Read-only inputs  \nVersioned outputs  \nNo deletion")

st.markdown('<div class="factory-kicker">Evidence in. Auditable title work out.</div>', unsafe_allow_html=True)
st.title("DataBoss Title Factory")
st.markdown(
    '<div class="safety-strip">ZERO-DESTRUCTION LINE — originals are never moved, '
    "overwritten, or deleted. Every extracted fact carries a source citation. "
    "Weak results remain visible in quarantine.</div>",
    unsafe_allow_html=True,
)

ctx = _context(project_root)
summary = run_summary(ctx) if ctx else {
    "files": 0, "ocr_citations": 0, "instruments": 0, "quarantined": 0,
    "runsheet_rows": 0, "run_id": "NO RUN",
}
metrics = st.columns(5)
for column, (label, key) in zip(
    metrics,
    (
        ("Files", "files"),
        ("Citations", "ocr_citations"),
        ("Instruments", "instruments"),
        ("Quarantined", "quarantined"),
        ("Runsheet", "runsheet_rows"),
    ),
):
    column.metric(label, summary[key])
st.caption(f"RUN ID / {summary['run_id']}")

st.markdown("### Production line")
buttons = st.columns(5)

with buttons[0]:
    st.markdown('<span class="stage-label">01</span>DISCOVER', unsafe_allow_html=True)
    if st.button("Run Inventory", type="primary", use_container_width=True):
        def inventory_action():
            new_ctx = start_run(project_root)
            return build_inventory(new_ctx)

        rows = _run_action("Scanning project folders", inventory_action)
        if rows is not None:
            st.success(f"Inventoried {len(rows):,} files.")
            st.rerun()

with buttons[1]:
    st.markdown('<span class="stage-label">02</span>READ', unsafe_allow_html=True)
    if st.button("Run OCR", use_container_width=True):
        if not ctx:
            st.error("Run Inventory first.")
        else:
            rows = _run_action(
                "Pre-processing images and running cited OCR",
                lambda: run_ocr(ctx, weak_threshold=weak_threshold),
            )
            if rows is not None:
                st.success(f"Created {len(rows):,} cited text records.")
                st.rerun()

with buttons[2]:
    st.markdown('<span class="stage-label">03</span>EXTRACT', unsafe_allow_html=True)
    if st.button("Extract", use_container_width=True):
        if not ctx:
            st.error("Run Inventory and OCR first.")
        else:
            rows = _run_action(
                "Running Cursor–Codex tournament reconciler",
                lambda: extract_and_reconcile(
                    ctx,
                    weak_threshold=weak_threshold,
                    cursor_json=cursor_json or None,
                    codex_json=codex_json or None,
                ),
            )
            if rows is not None:
                st.success(f"Reconciled {len(rows):,} instrument records.")
                st.rerun()

with buttons[3]:
    st.markdown('<span class="stage-label">04</span>ASSEMBLE', unsafe_allow_html=True)
    if st.button("Build Runsheet", use_container_width=True):
        if not ctx:
            st.error("Run extraction first.")
        else:
            bundle = _run_action("Building draft schedules", lambda: build_runsheet(ctx))
            if bundle is not None:
                st.success(f"Built runsheet with {len(bundle['runsheet']):,} rows.")
                st.rerun()

with buttons[4]:
    st.markdown('<span class="stage-label">05</span>DELIVER', unsafe_allow_html=True)
    if st.button("Export", use_container_width=True):
        if not ctx:
            st.error("Build a run first.")
        elif not template_path:
            st.error("Choose an Excel template in the control desk.")
        else:
            output = _run_action(
                "Copying template and creating safe draft sheets",
                lambda: export_safe_xlsx(ctx, template_path, section),
            )
            if output:
                st.session_state["export_path"] = str(output)
                st.success(f"Export created: {output}")

st.markdown("---")
left, right = st.columns([1.45, 1])
with left:
    st.subheader("Current evidence ledger")
    if ctx and (ctx.run_dir / "instruments.json").exists():
        import pandas as pd

        rows = __import__("json").loads(
            (ctx.run_dir / "instruments.json").read_text(encoding="utf-8")
        )
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_order=[
                "status", "confidence", "instrument_number", "instrument_type",
                "grantor", "grantee", "legal_description", "citation",
            ],
        )
    elif ctx and (ctx.run_dir / "file_inventory.csv").exists():
        import pandas as pd

        st.dataframe(
            pd.read_csv(ctx.run_dir / "file_inventory.csv"),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Start at Run Inventory. The current run's evidence will appear here.")

with right:
    st.subheader("Artifacts")
    if ctx:
        st.code(str(ctx.run_dir), language=None)
        artifacts = sorted(
            path for path in ctx.run_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in {".csv", ".json", ".jsonl", ".xlsx", ".xlsm"}
        )
        for artifact in artifacts[-12:]:
            st.caption(artifact.relative_to(ctx.run_dir).as_posix())
        export_path = Path(st.session_state.get("export_path", ""))
        if export_path.is_file():
            st.download_button(
                "Download latest workbook",
                data=export_path.read_bytes(),
                file_name=export_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    else:
        st.write("No versioned artifacts yet.")
