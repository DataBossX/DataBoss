"""Page 1 – Import pull list and image index."""

import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from core.config import config
from processors.pull_list import import_pull_list
from processors.image_index import import_image_index

st.set_page_config(page_title="Import — DOTO Image Commander", layout="wide")
st.title("📥 Import Data")

# ── Pull List ─────────────────────────────────────────────────────────────────
st.header("1. Import Pull List (XLSX)")

with st.expander("Filter options (optional)", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        f_county = st.selectbox("County filter", ["(all)"] + config.OK_COUNTIES)
    with col2:
        f_itype = st.text_input("Instrument type filter")
    with col3:
        f_section = st.text_input("Section")
    with col4:
        col4a, col4b = st.columns(2)
        with col4a:
            f_township = st.text_input("Township")
        with col4b:
            f_range = st.text_input("Range")

xlsx_file = st.file_uploader("Upload Pull List (.xlsx)", type=["xlsx", "xls"],
                              key="pull_list_upload")

if xlsx_file:
    df_preview = pd.read_excel(xlsx_file, dtype=str, nrows=5)
    st.write("**Preview (first 5 rows):**")
    st.dataframe(df_preview, use_container_width=True)

    if st.button("Import Pull List", type="primary"):
        filters = {}
        if f_county and f_county != "(all)":
            filters["county"] = f_county
        if f_itype:
            filters["instrument_type"] = f_itype
        if f_section:
            filters["section"] = f_section
        if f_township:
            filters["township"] = f_township
        if f_range:
            filters["range_val"] = f_range

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(xlsx_file.getvalue())
            tmp_path = tmp.name

        with st.spinner("Importing and normalizing pull list..."):
            result = import_pull_list(tmp_path, filters)

        st.success(
            f"Imported **{result['total_rows']}** rows from `{result['file']}`.\n\n"
            f"- Queued for download: **{result['queued']}**\n"
            f"- Skipped (duplicates): **{result['skipped_duplicates']}**\n"
            f"- Batch ID: `{result['batch_id']}`"
        )

st.divider()

# ── Image Index ───────────────────────────────────────────────────────────────
st.header("2. Import Image Index (CSV)")

csv_file = st.file_uploader("Upload Image Index (.csv)", type=["csv"],
                             key="image_index_upload")

if csv_file:
    df_csv_preview = pd.read_csv(csv_file, nrows=5, dtype=str)
    st.write("**Preview (first 5 rows):**")
    st.dataframe(df_csv_preview, use_container_width=True)

    if st.button("Import Image Index", type="primary"):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(csv_file.getvalue())
            tmp_path = tmp.name

        with st.spinner("Importing image index..."):
            result = import_image_index(tmp_path)

        st.success(
            f"Imported **{result['total_rows']}** index rows from `{result['file']}`.\n\n"
            f"- Matched existing queue items: **{result['matched_in_queue']}**\n"
            f"- Batch ID: `{result['batch_id']}`"
        )

st.divider()
st.info(
    "After importing, go to **Review Queue** to review the deduplicated download queue, "
    "estimate costs, and approve downloads."
)
