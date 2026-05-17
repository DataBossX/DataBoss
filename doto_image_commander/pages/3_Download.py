"""Page 3 – Execute approved downloads and PDF-to-image conversion."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from core.database import fetch_all, execute
from api.okcounty import client as ok_client
from processors.pdf_processor import download_approved_item

st.set_page_config(page_title="Download — DOTO Image Commander", layout="wide")
st.title("⬇️ Download Approved Images")

# ── Status summary ────────────────────────────────────────────────────────────
approved = fetch_all(
    """SELECT q.id, q.county, q.book, q.page, q.instrument_number,
              q.image_number, q.instrument_type, q.estimated_cost, q.approved_at
       FROM image_queue q WHERE q.status='approved' ORDER BY q.county, q.book"""
)

st.subheader(f"Approved and Ready: {len(approved)} item(s)")

if not ok_client.is_configured():
    st.error(
        "OKCountyRecords API key is not configured. Go to **Settings** to add your API key "
        "before downloading."
    )
else:
    st.success("OKCountyRecords API key is configured.")

if approved:
    total_est = sum(r["estimated_cost"] for r in approved)
    st.info(f"Estimated download cost: **${total_est:.2f}** for {len(approved)} document(s).")
    df_approved = pd.DataFrame(approved)
    st.dataframe(df_approved, use_container_width=True, height=300)

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Download ALL Approved", type="primary",
                     disabled=not ok_client.is_configured()):
            st.session_state["run_download"] = "all"
    with col2:
        single_id = st.number_input("Download single item ID", min_value=1, step=1, value=1)
        if st.button("Download This Item", disabled=not ok_client.is_configured()):
            st.session_state["run_download"] = single_id
else:
    st.info("No approved items. Go to **Review Queue** to approve downloads.")
    st.session_state.pop("run_download", None)

# ── Execute downloads ─────────────────────────────────────────────────────────
if "run_download" in st.session_state and ok_client.is_configured():
    run = st.session_state.pop("run_download")

    if run == "all":
        targets = approved
    else:
        targets = [r for r in approved if r["id"] == run]

    if not targets:
        st.warning("No matching items to download.")
    else:
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, item in enumerate(targets):
            status_text.text(
                f"[{i + 1}/{len(targets)}] {item['county']} | "
                f"Book {item['book']} Pg {item['page']} | {item['instrument_number']}"
            )

            def _cb(msg, _i=i, _n=len(targets)):
                status_text.text(f"[{_i + 1}/{_n}] {msg}")

            result = download_approved_item(item, progress_cb=_cb)
            results.append(result)
            progress_bar.progress((i + 1) / len(targets))

        succeeded = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        status_text.empty()
        progress_bar.empty()

        if succeeded:
            st.success(
                f"Downloaded **{len(succeeded)}/{len(targets)}** document(s). "
                f"Total charged: **${sum(r['charge'] for r in succeeded):.2f}**"
            )
        if failed:
            st.error(f"**{len(failed)} failed:**")
            for r in failed:
                st.write(f"- Queue item #{r['queue_item_id']}: {r.get('error', 'Unknown error')}")

st.divider()

# ── Download history ──────────────────────────────────────────────────────────
st.subheader("Download History")
history = fetch_all(
    """SELECT d.id, d.queue_item_id, q.county, q.book, q.page, q.instrument_number,
              d.status, d.file_size_bytes, d.api_charge, d.error_message, d.downloaded_at
       FROM downloads d JOIN image_queue q ON q.id=d.queue_item_id
       ORDER BY d.downloaded_at DESC LIMIT 200"""
)
if history:
    st.dataframe(pd.DataFrame(history), use_container_width=True, height=300)
else:
    st.info("No download history yet.")
