"""Page 4 – OCR analysis via OpenAI and structured result review."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from core.database import fetch_all, fetch_one, execute
from api.openai_client import analyzer
from processors.ocr_analyzer import analyze_download, run_analysis_batch

st.set_page_config(page_title="Analysis — DOTO Image Commander", layout="wide")
st.title("🔍 OCR / AI Analysis")

# ── API status ────────────────────────────────────────────────────────────────
if not analyzer.is_configured():
    st.error(
        "OpenAI API key is not configured. Go to **Settings** to add your key before analyzing."
    )
else:
    st.success("OpenAI API key is configured.")

# ── Batch analysis ────────────────────────────────────────────────────────────
st.header("Run Analysis")

ready = fetch_all(
    """SELECT d.id AS download_id, d.queue_item_id
       FROM downloads d
       LEFT JOIN analyses a ON a.download_id = d.id
       WHERE d.status = 'success' AND a.id IS NULL"""
)
st.metric("Documents ready to analyze", len(ready))

if ready and analyzer.is_configured():
    if st.button("Analyze ALL Ready Documents", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        completed = 0
        for i, dl in enumerate(ready):
            status_text.text(f"Analyzing {i + 1}/{len(ready)}...")
            analyze_download(dl["download_id"], dl["queue_item_id"])
            completed += 1
            progress_bar.progress((i + 1) / len(ready))

        progress_bar.empty()
        status_text.empty()
        st.success(f"Analyzed {completed} document(s).")
        st.rerun()

    if st.button("Analyze Single Document (by Download ID)"):
        st.session_state["show_single_analyze"] = True

    if st.session_state.get("show_single_analyze"):
        dl_id = st.number_input("Download ID", min_value=1, step=1)
        qi_id = st.number_input("Queue Item ID", min_value=1, step=1)
        if st.button("Run Analysis", type="primary"):
            with st.spinner("Analyzing..."):
                result = analyze_download(int(dl_id), int(qi_id))
            st.json(result)
else:
    if not ready:
        st.info("No documents ready for analysis. Download documents first.")

st.divider()

# ── Analysis results ──────────────────────────────────────────────────────────
st.header("Analysis Results")

show_review_only = st.checkbox("Show needs-review only", value=False)
where = "WHERE a.needs_review=1" if show_review_only else ""

results = fetch_all(f"""
    SELECT a.id, a.queue_item_id, a.instrument_type, a.instrument_number,
           a.book, a.page, a.recording_date, a.instrument_date,
           a.grantors, a.grantees, a.legal_description, a.section, a.township, a.range_val,
           a.interest_conveyed, a.confidence_score, a.needs_review, a.openai_cost,
           q.county
    FROM analyses a JOIN image_queue q ON q.id=a.queue_item_id
    {where}
    ORDER BY a.needs_review DESC, a.confidence_score ASC
""")

st.metric("Total analyses", len(results))

if results:
    df = pd.DataFrame(results)

    def _pl(v):
        if not v:
            return ""
        try:
            lst = json.loads(v)
            return "; ".join(lst) if isinstance(lst, list) else str(v)
        except Exception:
            return str(v)

    df["grantors"] = df["grantors"].apply(_pl)
    df["grantees"] = df["grantees"].apply(_pl)
    df["needs_review"] = df["needs_review"].apply(lambda x: "YES" if x else "")

    def _row_color(row):
        if row["needs_review"] == "YES":
            return ["background-color: #FFE699"] * len(row)
        if isinstance(row["confidence_score"], (int, float)) and row["confidence_score"] < 0.5:
            return ["background-color: #FFCCCC"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df.style.apply(_row_color, axis=1),
        use_container_width=True, height=500,
    )

    st.divider()

    # Detail view
    st.subheader("Detail View")
    sel_id = st.selectbox("Select Analysis ID", [r["id"] for r in results])
    if sel_id:
        detail = fetch_one("SELECT * FROM analyses WHERE id=?", (sel_id,))
        if detail:
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Instrument Type:**", detail["instrument_type"] or "—")
                st.write("**Instrument #:**", detail["instrument_number"] or "—")
                st.write("**Book/Page:**", f"{detail['book']}/{detail['page']}")
                st.write("**Recording Date:**", detail["recording_date"] or "—")
                st.write("**Instrument Date:**", detail["instrument_date"] or "—")
                st.write("**Section/Township/Range:**",
                         "/".join(filter(None, [detail["section"], detail["township"], detail["range_val"]])))
            with col2:
                def _pl2(v):
                    try:
                        return json.loads(v) if v else []
                    except Exception:
                        return [str(v)] if v else []

                st.write("**Grantors:**")
                for g in _pl2(detail["grantors"]):
                    st.write(f"  - {g}")
                st.write("**Grantees:**")
                for g in _pl2(detail["grantees"]):
                    st.write(f"  - {g}")
                st.write("**Interest Conveyed:**", detail["interest_conveyed"] or "—")
                st.write("**Confidence:**", f"{detail['confidence_score']:.0%}")
                if detail["needs_review"]:
                    st.warning("Flagged for human review")

            st.write("**Legal Description:**")
            st.text_area("", value=detail["legal_description"] or "", height=80,
                         disabled=True, key=f"ld_{sel_id}")

            if detail.get("lease_royalty_terms"):
                st.write("**Lease/Royalty Terms:**", detail["lease_royalty_terms"])
            if detail.get("title_requirement_affected"):
                st.write("**Title Req Affected:**", detail["title_requirement_affected"])

            # Mark reviewed
            if detail["needs_review"]:
                if st.button("Mark as Reviewed (clear flag)", key=f"rev_{sel_id}"):
                    execute("UPDATE analyses SET needs_review=0 WHERE id=?", (sel_id,))
                    st.success("Cleared review flag.")
                    st.rerun()
else:
    st.info("No analysis results yet.")
