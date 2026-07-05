"""DataBossX Land Intelligence -- Streamlit command center.

A local, dark-mode control panel for chaining mineral/title ownership on
Section 31-12N-24W, Roger Mills County, Oklahoma. Upload a runsheet (and,
optionally, a template), run the self-healing title chain, watch live
telemetry, and download the corrected workbook.

Nothing leaves the machine: uploads are written under ``data/`` and the export
is saved locally. API keys are read from ``.env`` and never displayed.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from agents import describe_model_config
from excel_writer import write_corrected_workbook
from make_template import main as build_template
from tasks import run_pipeline

load_dotenv()

APP_DIR = Path(__file__).parent
INPUT_DIR = APP_DIR / "data" / "input"
TEMPLATE_DIR = APP_DIR / "data" / "template"
OUTPUT_DIR = APP_DIR / "data" / "output"
DEFAULT_TEMPLATE = TEMPLATE_DIR / "template.xlsx"
OUTPUT_FILE = OUTPUT_DIR / "SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx"

ACCENT = "#00D8FF"
for d in (INPUT_DIR, TEMPLATE_DIR, OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="DataBossX Land Intelligence",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Strict dark theme + neon accent + Orbitron headers --------------------
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Share+Tech+Mono&display=swap');
    :root {{ --accent: {ACCENT}; }}
    .stApp {{ background: #05080F; color: #C9D6E5; }}
    section[data-testid="stSidebar"] {{ background: #070C16; border-right: 1px solid #12263b; }}
    h1, h2, h3, h4, .metric-label {{ font-family: 'Orbitron', sans-serif !important; letter-spacing: 1px; }}
    h1 {{ color: {ACCENT}; text-shadow: 0 0 14px rgba(0,216,255,0.45); }}
    .db-banner {{
        border: 1px solid #12384f; border-left: 4px solid {ACCENT};
        background: linear-gradient(90deg, rgba(0,216,255,0.08), rgba(5,8,15,0));
        padding: 14px 20px; border-radius: 8px; margin-bottom: 8px;
    }}
    .db-sub {{ font-family: 'Share Tech Mono', monospace; color: #6f8aa6; }}
    .metric-card {{
        background: #0A1220; border: 1px solid #12263b; border-radius: 10px;
        padding: 16px 18px; box-shadow: inset 0 0 24px rgba(0,216,255,0.05);
    }}
    .metric-value {{ font-family: 'Orbitron', sans-serif; font-size: 30px; font-weight: 900; color: {ACCENT}; }}
    .metric-label {{ font-size: 11px; color: #7f97b0; text-transform: uppercase; }}
    .metric-path {{ font-family: 'Share Tech Mono', monospace; font-size: 12px; color: #9fd8e6; word-break: break-all; }}
    .stButton>button {{
        font-family: 'Orbitron', sans-serif; font-weight: 700; letter-spacing: 1px;
        background: {ACCENT}; color: #04121a; border: none; border-radius: 8px; padding: 10px 18px;
        box-shadow: 0 0 18px rgba(0,216,255,0.4);
    }}
    .stButton>button:hover {{ background: #4fe8ff; color: #001; }}
    .stCode, code {{ font-family: 'Share Tech Mono', monospace !important; }}
    [data-testid="stFileUploaderDropzone"] {{ background: #0A1220; border: 1px dashed #1c4863; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="db-banner">
      <h1 style="margin:0;">🛰️ DATABOSSX · LAND INTELLIGENCE</h1>
      <div class="db-sub">SECTION 31-12N-24W · ROGER MILLS COUNTY · OKLAHOMA — FINAL OWNERSHIP TITLE ENGINE</div>
    </div>
    """,
    unsafe_allow_html=True,
)


def _metric_card(col, label: str, value, is_path: bool = False) -> None:
    inner = (
        f'<div class="metric-path">{value}</div>'
        if is_path
        else f'<div class="metric-value">{value}</div>'
    )
    col.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>{inner}</div>',
        unsafe_allow_html=True,
    )


# --- Sidebar: model + rules -------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ ENGINE STATUS")
    st.markdown(f'<div class="db-sub">Model: {describe_model_config()}</div>', unsafe_allow_html=True)
    st.markdown('<div class="db-sub">Verifier: deterministic Decimal (0.000001)</div>', unsafe_allow_html=True)
    st.markdown('<div class="db-sub">Self-healing: up to 5 retries / tract</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown("### 🔒 HARD RULES")
    st.caption(
        "Template is the write destination · Overview stays first · Title Sheet "
        "shows final owners only · OGL fields hold OGL numbers only · ASSN for "
        "assignments · no over-conveyance · no negative ownership · each tract "
        "totals exactly · assumptions noted · only review cells highlighted."
    )
    st.divider()
    use_llm = st.toggle("Use LLM agents (if configured)", value=True)

# --- Inputs -----------------------------------------------------------------
left, right = st.columns([1, 1.3], gap="large")
with left:
    st.markdown("#### 📥 INPUTS")
    runsheet_file = st.file_uploader("Runsheet (XLSX / PDF)", type=["xlsx", "xlsm", "pdf"])
    template_file = st.file_uploader("Template (XLSX) — optional", type=["xlsx"])
    st.caption(
        "No runsheet handy? A sample lives at `data/input/sample_runsheet.xlsx` "
        "(run `python make_sample_runsheet.py`)."
    )
    acres_text = st.text_input(
        "Tract acreage overrides (optional JSON)",
        value="",
        placeholder='{"1": 160, "2": 160, "3": 160}',
        help="Leave blank to auto-resolve each tract's acreage from the runsheet.",
    )
    run_clicked = st.button("🚀 RUN TITLE CHAIN", type="primary", use_container_width=True)

with right:
    st.markdown("#### 📡 LIVE TELEMETRY")
    telemetry = st.empty()
    if "log_buffer" not in st.session_state:
        st.session_state.log_buffer = []
    telemetry.code("\n".join(st.session_state.log_buffer[-400:]) or "// awaiting run…", language="text")


def _resolve_runsheet_path() -> Path | None:
    if runsheet_file is not None:
        dest = INPUT_DIR / runsheet_file.name
        dest.write_bytes(runsheet_file.getbuffer())
        return dest
    sample = INPUT_DIR / "sample_runsheet.xlsx"
    return sample if sample.exists() else None


def _resolve_template_path() -> Path:
    if template_file is not None:
        dest = TEMPLATE_DIR / "template.xlsx"
        dest.write_bytes(template_file.getbuffer())
        return dest
    if not DEFAULT_TEMPLATE.exists():
        build_template(str(DEFAULT_TEMPLATE))
    return DEFAULT_TEMPLATE


def _parse_acres(text: str) -> dict:
    import json

    text = text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        st.warning("Could not parse tract acreage JSON; auto-resolving instead.")
        return {}


# --- Run --------------------------------------------------------------------
if run_clicked:
    runsheet_path = _resolve_runsheet_path()
    if runsheet_path is None:
        st.error("Upload a runsheet (or generate the sample) before running.")
        st.stop()
    template_path = _resolve_template_path()
    acres_map = _parse_acres(acres_text)

    buffer: list[str] = []

    def log(msg: str) -> None:
        buffer.append(msg)
        telemetry.code("\n".join(buffer[-400:]), language="text")

    try:
        with st.status("Running self-healing title chain…", expanded=False):
            outcome = run_pipeline(
                runsheet_path,
                tract_acres_map=acres_map,
                log=log,
                use_llm=use_llm,
            )
            out_path = write_corrected_workbook(
                template_path,
                outcome["results"],
                OUTPUT_FILE,
                instruments=outcome["instruments"],
            )
    except Exception as exc:  # surface real errors, never a fake success
        log(f"ERROR: {type(exc).__name__}: {exc}")
        st.session_state.log_buffer = buffer
        st.error(f"Pipeline failed: {exc}")
        st.stop()

    st.session_state.log_buffer = buffer
    summary = outcome["summary"]

    st.markdown("#### 📊 STATUS")
    c1, c2, c3, c4 = st.columns(4)
    _metric_card(c1, "Tracts Processed", summary["tracts_processed"])
    _metric_card(c2, "Balanced Tracts", f'{summary["balanced_tracts"]}/{summary["tracts_processed"]}')
    _metric_card(c3, "Review Flags", summary["review_flags"])
    _metric_card(c4, "Output File", Path(out_path).name, is_path=True)

    # Per-tract detail
    with st.expander("Per-tract results", expanded=True):
        for tract, res in outcome["results"].items():
            ver = outcome["verifications"][tract]
            badge = "🟢 BALANCED" if res.balanced else "🟡 REVIEW"
            st.markdown(
                f"**Tract {tract}** — {badge} · total "
                f"`{res.total_acres}` / `{res.tract_acres}` ac · delta `{ver.delta}`"
            )
            rows = [
                {
                    "Owner": o.owner,
                    "Net Acres": str(o.acres),
                    "WI": str(o.wi),
                    "OGL": o.ogl or "",
                    "Review": o.assumption_note or "",
                }
                for o in res.final_owners
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
            for flag in res.review_flags:
                st.warning(flag)

    with open(out_path, "rb") as fh:
        st.download_button(
            "📥 DOWNLOAD CORRECTED XLSX",
            data=fh.read(),
            file_name=Path(out_path).name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    st.success(f"Saved locally → {out_path}")
