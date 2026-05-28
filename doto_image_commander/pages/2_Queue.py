"""Page 2 – Review deduplicated queue, estimate costs, approve downloads."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from core.database import fetch_all, execute, get_stats
from core.config import config
from api.okcounty import client as ok_client

st.set_page_config(page_title="Queue — DOTO Image Commander", layout="wide")
st.title("📋 Review Download Queue")

# ── Filters ───────────────────────────────────────────────────────────────────
with st.expander("Filter queue", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        filter_status = st.multiselect(
            "Status", ["pending", "approved", "downloading", "downloaded",
                       "analyzed", "failed"],
            default=["pending"]
        )
    with col2:
        filter_county = st.selectbox("County", ["(all)"] + config.OK_COUNTIES)
    with col3:
        filter_itype = st.text_input("Instrument type")
    with col4:
        filter_county_str = st.text_input("Search (instrument #, book, page)")

# Build query
conditions = []
params = []
if filter_status:
    conditions.append(f"q.status IN ({','.join('?' for _ in filter_status)})")
    params.extend(filter_status)
if filter_county and filter_county != "(all)":
    conditions.append("q.county=?")
    params.append(filter_county)
if filter_itype:
    conditions.append("q.instrument_type LIKE ?")
    params.append(f"%{filter_itype}%")
if filter_county_str:
    conditions.append("(q.instrument_number LIKE ? OR q.book LIKE ? OR q.page LIKE ?)")
    params += [f"%{filter_county_str}%"] * 3

where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
sql = f"""
    SELECT q.id, q.county, q.book, q.page, q.instrument_number, q.image_number,
           q.instrument_type, q.section, q.township, q.range_val,
           q.recording_date, q.estimated_cost, q.status, q.approved_at
    FROM image_queue q {where}
    ORDER BY q.county, q.book, q.page
"""
rows = fetch_all(sql, tuple(params))
df = pd.DataFrame(rows)

# ── Cost estimate ─────────────────────────────────────────────────────────────
st.subheader("Cost Estimate")
pending_rows = fetch_all("SELECT COUNT(*) as n FROM image_queue WHERE status='pending'")
n_pending = pending_rows[0]["n"] if pending_rows else 0

if n_pending > 0:
    est = ok_client.estimate_batch_cost(n_images=n_pending, n_searches=n_pending)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Pending Items", est["images"])
    with col2:
        st.metric("Est. Image Cost", f"${est['image_cost']:.2f}")
    with col3:
        st.metric("Est. Search Cost", f"${est['search_cost']:.2f}")
    with col4:
        st.metric("Est. Total", f"${est['total']:.2f}")

    st.warning(
        f"Approving all pending items will trigger up to **${est['total']:.2f}** in API charges. "
        "You must explicitly approve before any charges are incurred."
    )
else:
    st.info("No pending items to estimate.")

st.divider()

# ── Queue table ───────────────────────────────────────────────────────────────
st.subheader(f"Queue ({len(df)} items shown)")

if df.empty:
    st.info("No items match the selected filters.")
else:
    # Color-coded status display
    def _color_status(val):
        colors = {
            "pending": "background-color: #FFF3CD",
            "approved": "background-color: #D1ECF1",
            "downloading": "background-color: #CCE5FF",
            "downloaded": "background-color: #D4EDDA",
            "analyzed": "background-color: #C6EFCE",
            "failed": "background-color: #F8D7DA",
        }
        return colors.get(val, "")

    st.dataframe(
        df.style.applymap(_color_status, subset=["status"]),
        use_container_width=True, height=400,
    )

st.divider()

# ── Approval actions ──────────────────────────────────────────────────────────
st.subheader("Approval Actions")

col_a, col_b, col_c = st.columns(3)

with col_a:
    if st.button("Approve ALL Pending", type="primary"):
        if n_pending == 0:
            st.warning("No pending items.")
        else:
            est = ok_client.estimate_batch_cost(n_images=n_pending, n_searches=n_pending)
            st.session_state["approval_pending"] = {
                "mode": "all",
                "count": n_pending,
                "cost": est["total"],
            }

with col_b:
    selected_ids_input = st.text_input(
        "Approve specific IDs (comma-separated)")
    if st.button("Approve Selected"):
        if selected_ids_input.strip():
            ids = [int(x.strip()) for x in selected_ids_input.split(",") if x.strip().isdigit()]
            cost_est = len(ids) * config.OKCOUNTY_COST_PER_IMAGE * 2
            st.session_state["approval_pending"] = {
                "mode": "selected",
                "ids": ids,
                "count": len(ids),
                "cost": cost_est,
            }
        else:
            st.warning("Enter at least one ID.")

with col_c:
    if st.button("Reset Failed → Pending"):
        execute("UPDATE image_queue SET status='pending' WHERE status='failed'")
        st.success("Failed items reset to pending.")
        st.rerun()

# Confirmation dialog
if "approval_pending" in st.session_state:
    ap = st.session_state["approval_pending"]
    st.warning(
        f"Confirm approval of **{ap['count']} item(s)** for download.\n\n"
        f"Estimated cost: **${ap['cost']:.2f}**\n\n"
        "This will authorize billable API calls. Proceed?"
    )
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("YES – Approve and Authorize", type="primary"):
            if ap["mode"] == "all":
                execute(
                    "UPDATE image_queue SET status='approved', approved_at=datetime('now') "
                    "WHERE status='pending'"
                )
            else:
                for qid in ap.get("ids", []):
                    execute(
                        "UPDATE image_queue SET status='approved', approved_at=datetime('now') WHERE id=?",
                        (qid,),
                    )
            del st.session_state["approval_pending"]
            st.success(f"Approved {ap['count']} item(s). Go to Download page.")
            st.rerun()
    with col_no:
        if st.button("Cancel"):
            del st.session_state["approval_pending"]
            st.rerun()
