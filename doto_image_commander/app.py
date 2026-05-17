"""DOTO Image Commander – Main Streamlit entry point (dashboard)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from core.database import init_database, get_stats
from core.config import ensure_dirs

st.set_page_config(
    page_title="DOTO Image Commander",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_database()
ensure_dirs()


def _metric(label, value, fmt=None):
    if fmt:
        st.metric(label, fmt.format(value))
    else:
        st.metric(label, value)


st.title("DOTO Image Commander")
st.caption("Oklahoma County Land Records — Image Collection & Document Indexing")

st.divider()
stats = get_stats()

col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
with col1:
    st.metric("Queue Total", stats["queue_total"])
with col2:
    st.metric("Pending Approval", stats["pending"])
with col3:
    st.metric("Approved", stats["approved"])
with col4:
    st.metric("Downloaded", stats["downloaded"])
with col5:
    st.metric("Analyzed", stats["analyzed"])
with col6:
    st.metric("Needs Review", stats["needs_review"])
with col7:
    st.metric("Total Spend", f"${stats['total_cost']:.2f}")

st.divider()

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Cost Breakdown")
    st.write(f"- OKCountyRecords API: **${stats['okcounty_cost']:.2f}**")
    st.write(f"- OpenAI API: **${stats['openai_cost']:.2f}**")

with col_b:
    st.subheader("Workflow Status")
    total = max(stats["queue_total"], 1)
    st.progress(stats["downloaded"] / total, text=f"Downloads: {stats['downloaded']}/{stats['queue_total']}")
    st.progress(stats["analyzed"] / total, text=f"Analyses: {stats['analyzed']}/{stats['queue_total']}")
    if stats["failed_downloads"]:
        st.warning(f"{stats['failed_downloads']} failed download(s) — see Reports.")

st.divider()
st.subheader("Quick Navigation")
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.page_link("pages/1_Import.py", label="Import Data", icon="📥")
with c2:
    st.page_link("pages/2_Queue.py", label="Review Queue", icon="📋")
with c3:
    st.page_link("pages/3_Download.py", label="Download", icon="⬇️")
with c4:
    st.page_link("pages/4_Analysis.py", label="Analysis", icon="🔍")
with c5:
    st.page_link("pages/5_Reports.py", label="Reports", icon="📊")
with c6:
    st.page_link("pages/6_Settings.py", label="Settings", icon="⚙️")
