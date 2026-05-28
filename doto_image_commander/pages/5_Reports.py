"""Page 5 – Generate and download all reports."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from core.database import fetch_all, get_stats
from core.config import config
from reports.generator import generate_full_report, write_results_to_input_excel

st.set_page_config(page_title="Reports — DOTO Image Commander", layout="wide")
st.title("📊 Reports")

stats = get_stats()

# ── Summary stats ─────────────────────────────────────────────────────────────
st.subheader("Current Session Summary")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Queue", stats["queue_total"])
with col2:
    st.metric("Downloaded", stats["downloaded"])
with col3:
    st.metric("Analyzed", stats["analyzed"])
with col4:
    st.metric("Needs Review", stats["needs_review"])

col5, col6 = st.columns(2)
with col5:
    st.metric("OKCounty Spend", f"${stats['okcounty_cost']:.2f}")
with col6:
    st.metric("OpenAI Spend", f"${stats['openai_cost']:.2f}")

st.divider()

# ── Full report ────────────────────────────────────────────────────────────────
st.header("Full Report Workbook")
st.write(
    "Generates one Excel workbook containing all report sheets:\n"
    "- Image Index\n- Analysis Results\n- Missing Images\n"
    "- Failed Downloads\n- Cost Report\n- DOTO Update Summary\n- Needs Human Review"
)

if st.button("Generate Full Report", type="primary"):
    with st.spinner("Building report..."):
        out_path = generate_full_report()
    st.success(f"Report saved: `{out_path}`")
    with open(out_path, "rb") as f:
        st.download_button(
            label="Download Report Excel",
            data=f.read(),
            file_name=Path(out_path).name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

st.divider()

# ── Write results back to input file ─────────────────────────────────────────
st.header("Write Results Back to Original Pull List")
uploaded = st.file_uploader(
    "Upload original Pull List XLSX to enrich with analysis results",
    type=["xlsx", "xls"],
    key="source_xlsx_report",
)
if uploaded:
    if st.button("Generate Enriched Output"):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(uploaded.getvalue())
            tmp_path = tmp.name
        with st.spinner("Writing results..."):
            out_path = write_results_to_input_excel(tmp_path)
        st.success(f"Saved: `{out_path}`")
        with open(out_path, "rb") as f:
            st.download_button(
                label="Download Enriched Excel",
                data=f.read(),
                file_name=Path(out_path).name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

st.divider()

# ── Individual report previews ─────────────────────────────────────────────────
st.header("Quick Previews")

tab1, tab2, tab3, tab4 = st.tabs([
    "Missing Images", "Failed Downloads", "Needs Review", "Cost Detail"
])

with tab1:
    missing = fetch_all(
        "SELECT id, county, book, page, instrument_number, image_number, status "
        "FROM image_queue WHERE status NOT IN ('downloaded','analyzed') ORDER BY county"
    )
    st.metric("Missing / Not Downloaded", len(missing))
    if missing:
        st.dataframe(pd.DataFrame(missing), use_container_width=True)

with tab2:
    failed = fetch_all(
        """SELECT d.id, d.queue_item_id, q.county, q.book, q.page,
                  q.instrument_number, d.error_message, d.downloaded_at
           FROM downloads d JOIN image_queue q ON q.id=d.queue_item_id
           WHERE d.status='failed' ORDER BY d.downloaded_at DESC"""
    )
    st.metric("Failed Downloads", len(failed))
    if failed:
        st.dataframe(pd.DataFrame(failed), use_container_width=True)

with tab3:
    review = fetch_all(
        """SELECT a.id, q.county, a.book, a.page, a.instrument_number,
                  a.instrument_type, a.confidence_score, a.analyzed_at
           FROM analyses a JOIN image_queue q ON q.id=a.queue_item_id
           WHERE a.needs_review=1 ORDER BY a.confidence_score ASC"""
    )
    st.metric("Needs Human Review", len(review))
    if review:
        st.dataframe(pd.DataFrame(review), use_container_width=True)

with tab4:
    costs = fetch_all(
        "SELECT created_at, api_type, amount, description FROM cost_tracking ORDER BY created_at DESC LIMIT 500"
    )
    if costs:
        df_cost = pd.DataFrame(costs)
        st.dataframe(df_cost, use_container_width=True)
        st.write(f"**OKCounty total:** ${stats['okcounty_cost']:.2f} | "
                 f"**OpenAI total:** ${stats['openai_cost']:.2f} | "
                 f"**Grand total:** ${stats['total_cost']:.2f}")

# ── Audit log ─────────────────────────────────────────────────────────────────
st.divider()
st.header("Audit Log (last 100 entries)")
audit = fetch_all(
    "SELECT created_at, event_type, description, api_called, cost "
    "FROM audit_log ORDER BY created_at DESC LIMIT 100"
)
if audit:
    st.dataframe(pd.DataFrame(audit), use_container_width=True, height=300)
else:
    st.info("No audit events recorded yet.")
