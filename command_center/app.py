"""DataBossX Land Intelligence — Streamlit command center.

Run it from the repository root:

    streamlit run command_center/app.py

A military-grade, strict-dark console (neon blue ``#00D8FF``, Orbitron display
font) that drives the self-healing title-chaining swarm and streams every agent
thought into a live telemetry console. It runs fully in deterministic mode with
no API key; if ``crewai`` + an LLM key are present it also layers on the swarm's
narrative.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Make the repo root importable whether launched via `streamlit run` or `-m`.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st  # noqa: E402

from command_center import __version__  # noqa: E402
from command_center import agents as agents_mod  # noqa: E402
from command_center.engine import format_fraction  # noqa: E402
from command_center.interest_fmt import fmt_acres  # noqa: E402
from command_center.sample_data import ensure_sample_workspace  # noqa: E402
from command_center.tasks import run_pipeline  # noqa: E402

NEON = "#00D8FF"
ACCENT_LEVELS = {
    "success": "#00FFA3",
    "heal": "#00FFA3",
    "verify": "#00D8FF",
    "action": "#00D8FF",
    "thought": "#7FE9FF",
    "info": "#8894A0",
    "warn": "#FFC000",
    "escalate": "#FF4D6D",
}
AGENT_ICON = {
    "INGESTION": "📡",
    "TITLE_AUDITOR": "⚖️",
    "MATHEMATICIAN": "∑",
    "SYSTEM": "▨",
}

st.set_page_config(
    page_title="DataBossX · Land Intelligence Command Center",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Share+Tech+Mono&display=swap');

        :root {{ --neon: {NEON}; }}
        html, body, [class*="css"], .stApp {{
            background: radial-gradient(1200px 600px at 20% -10%, #06222e 0%, #020608 55%) fixed;
            color: #C7D3DB;
        }}
        h1, h2, h3, h4, .metric-label, .dbx-title, [data-testid="stMetricValue"] {{
            font-family: 'Orbitron', system-ui, sans-serif !important;
            letter-spacing: 0.06em;
        }}
        .dbx-title {{
            font-size: 2.1rem; font-weight: 900; color: var(--neon);
            text-shadow: 0 0 18px rgba(0,216,255,0.55); margin-bottom: 0;
        }}
        .dbx-sub {{ color: #6E7C86; font-family: 'Share Tech Mono', monospace; letter-spacing:0.12em; }}
        [data-testid="stMetric"] {{
            background: rgba(0,216,255,0.04); border: 1px solid rgba(0,216,255,0.22);
            border-radius: 10px; padding: 12px 14px;
            box-shadow: inset 0 0 22px rgba(0,216,255,0.05);
        }}
        [data-testid="stMetricValue"] {{ color: var(--neon) !important; }}
        .stButton>button {{
            font-family: 'Orbitron', sans-serif; font-weight: 700; letter-spacing: 0.1em;
            background: linear-gradient(90deg, rgba(0,216,255,0.15), rgba(0,216,255,0.03));
            color: var(--neon); border: 1px solid var(--neon); border-radius: 8px;
            box-shadow: 0 0 14px rgba(0,216,255,0.25);
        }}
        .stButton>button:hover {{ background: rgba(0,216,255,0.28); color: #001018; }}
        .dbx-console {{
            font-family: 'Share Tech Mono', monospace; font-size: 0.86rem; line-height: 1.5;
            background: #020a0e; border: 1px solid rgba(0,216,255,0.25); border-radius: 10px;
            padding: 14px 16px; height: 460px; overflow-y: auto;
            box-shadow: inset 0 0 40px rgba(0,216,255,0.06);
        }}
        .dbx-line {{ white-space: pre-wrap; margin: 0; }}
        .dbx-agent {{ font-weight: 700; }}
        section[data-testid="stSidebar"] {{ background: #04121a; border-right: 1px solid rgba(0,216,255,0.18); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_console(events) -> str:
    rows = []
    for e in events:
        color = ACCENT_LEVELS.get(e.level, "#8894A0")
        icon = AGENT_ICON.get(e.agent, "•")
        loop = f"L{e.loop} " if e.loop else "    "
        rows.append(
            f'<p class="dbx-line">'
            f'<span style="color:#3a4a54">{loop}</span>'
            f'<span class="dbx-agent" style="color:{color}">{icon} {e.agent:<13}</span>'
            f'<span style="color:{color}">{_esc(e.message)}</span></p>'
        )
    return '<div class="dbx-console" id="dbxc">' + "".join(rows) + "</div>"


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def status_pill(status: str) -> str:
    palette = {
        "balanced": ("#00FFA3", "BALANCED"),
        "healed": ("#00D8FF", "HEALED · ASSUMED"),
        "escalated": ("#FF4D6D", "EXAMINER REVIEW"),
        "undetermined": ("#FFC000", "UNDETERMINED"),
    }
    color, label = palette.get(status, ("#8894A0", status.upper()))
    return f'<span style="color:{color};font-weight:700;font-family:Orbitron">{label}</span>'


def main() -> None:
    inject_css()

    st.markdown('<div class="dbx-title">DATABOSSX · LAND INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="dbx-sub">SELF-HEALING TITLE-CHAINING COMMAND CENTER · v{__version__} · '
        f'EXACT-FRACTION ENGINE</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    # ---- sidebar controls ------------------------------------------------- #
    with st.sidebar:
        st.markdown("### ▚ MISSION PARAMETERS")
        section = st.text_input("Target section", value="31-12N-24W")
        st.caption("Roger Mills County, Oklahoma — the engine is section-agnostic.")

        source = st.radio("Source data", ["Synthetic sample", "Upload workbook"], index=0)
        uploaded = None
        if source == "Upload workbook":
            uploaded = st.file_uploader("OGL + Runsheet workbook (.xlsx)", type=["xlsx"])
        tpl_upload = st.file_uploader("Report template (.xlsx, optional)", type=["xlsx"])

        max_loops = st.slider("Max self-healing loops", 1, 10, 5)

        swarm_choice = st.selectbox(
            "LLM swarm (CrewAI)",
            ["Auto", "Off", "Force"],
            index=0,
            help="Deterministic engine always runs. The swarm only adds a narrative "
            "and requires crewai + an API key.",
        )
        st.caption(
            f"CrewAI installed: {'✅' if agents_mod.CREWAI_AVAILABLE else '❌'}  ·  "
            f"LLM key: {'✅' if agents_mod.llm_configured() else '❌'}"
        )
        run = st.button("▶  ENGAGE SWARM", use_container_width=True)

    # ---- run -------------------------------------------------------------- #
    if run:
        workspace = _REPO_ROOT / ".command_center_run"
        workspace.mkdir(exist_ok=True)
        if source == "Upload workbook" and uploaded is not None:
            wb = workspace / uploaded.name
            wb.write_bytes(uploaded.getbuffer())
            tpl = None
        else:
            wb, tpl = ensure_sample_workspace(workspace / "sample")
        if tpl_upload is not None:
            tpl = workspace / tpl_upload.name
            tpl.write_bytes(tpl_upload.getbuffer())

        out_path = workspace / f"{section.replace('/', '-')}_REPORT_v001.xlsx"

        console = st.empty()
        live_events = []

        def sink(evt):
            live_events.append(evt)
            console.markdown(render_console(live_events), unsafe_allow_html=True)
            time.sleep(0.02)  # let the neon scroll read as a live feed

        use_swarm = {"Auto": "auto", "Off": "off", "Force": "force"}[swarm_choice]
        st.markdown("#### ▚ LIVE TELEMETRY")
        try:
            outcome = run_pipeline(
                wb, section=section, out_path=out_path, template=tpl,
                max_loops=max_loops, use_swarm=use_swarm, sink=sink,
            )
        except Exception as exc:
            st.error(f"Pipeline error: {exc}")
            return

        st.session_state["outcome"] = outcome
        st.session_state["report_path"] = str(out_path)

    # ---- results ---------------------------------------------------------- #
    outcome = st.session_state.get("outcome")
    if outcome is not None:
        r = outcome.result
        st.write("")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("TRACTS", len(r.balances))
        c2.metric("BALANCED", r.tracts_balanced)
        c3.metric("EXAMINER REVIEW", r.tracts_escalated)
        c4.metric("HEAL LOOPS", r.loops_run)
        c5.metric("MODE", "SWARM" if outcome.mode.startswith("swarm") else "DETERM")

        conv = "✅ CONVERGED" if r.converged else "⚠ UNRESOLVED GAPS"
        st.markdown(f"**Loop status:** {conv}  ·  written to `{Path(st.session_state['report_path']).name}`")

        st.markdown("#### ▚ TRACT LEDGER")
        for b in r.balances:
            net = fmt_acres(b.net_acres_sum)
            gross = fmt_acres(b.gross_acres)
            cols = st.columns([3, 2, 2, 4])
            cols[0].markdown(f"**{b.tract_legal or b.tract}**")
            cols[1].markdown(status_pill(b.status), unsafe_allow_html=True)
            cols[2].markdown(f"Σwi `{format_fraction(b.outstanding_sum)}`  ·  {net}/{gross} ac")
            detail = "; ".join(b.assumptions + b.reasons) or "clean chain, ties to 8/8"
            cols[3].caption(detail)

        rp = Path(st.session_state["report_path"])
        if rp.exists():
            with open(rp, "rb") as fh:
                st.download_button(
                    "⬇  DOWNLOAD PERFECTED REPORT (.xlsx)",
                    fh.read(),
                    file_name=rp.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            st.caption("Yellow cells = ASSUMED (verify before use) · Amber rows = Needs Examiner Review.")

        if outcome.narrative:
            st.markdown("#### ▚ SWARM NARRATIVE")
            st.markdown(outcome.narrative)
    else:
        st.info("Configure the mission in the left panel and press **ENGAGE SWARM**.")


if __name__ == "__main__":
    main()
