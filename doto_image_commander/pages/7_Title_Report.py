"""Page 7 – Cursory Title Report.

Builds a full cursory title report (Excel workbook + interactive HTML dashboard
+ CSV/MD deliverables, with QA gates) for a Section-Township-Range. The tract
data comes either from the DOTO-examined instruments in this database (real
feed) or from a bundled illustrative dataset for demonstration.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))          # doto_image_commander
sys.path.insert(0, str(Path(__file__).parent.parent.parent))   # repo root (title_report)

import streamlit as st
import streamlit.components.v1 as components

from core.config import config
from title_report.generate import generate, build_tract, TRACTS
from title_report.adapters.doto import available_tracts, build_report_from_db

st.set_page_config(page_title="Title Report — DOTO", layout="wide")
st.title("📜 Cursory Title Report")
st.caption("Excel workbook · interactive HTML dashboard · SOURCE_LOG / CURATIVE / "
           "MISSING CSVs · QA_RESULTS — all from one click.")

DB_PATH = str(config.DB_PATH)
OUT_DIR = config.REPORTS_DIR / "title_report"

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _download(path_str: str, label: str, mime: str = "text/plain") -> None:
    p = Path(path_str)
    if not p.exists():
        return
    with open(p, "rb") as fh:
        st.download_button(label, data=fh.read(), file_name=p.name, mime=mime, key=f"dl_{p.name}")


source = st.radio(
    "Tract data source",
    ["DOTO-examined instruments (this database)", "Bundled illustrative dataset"],
    horizontal=True,
)

report_date = st.date_input("Report date", value=date.today()).isoformat()

rpt = None
if source.startswith("DOTO"):
    tracts = available_tracts(DB_PATH)
    if not tracts:
        st.info("No analyzed instruments with a Section-Township-Range found in this "
                "database yet. Import, download, and analyze instruments first, or use "
                "the bundled illustrative dataset.")
    else:
        labels = [f"{t['slug']} — {t['county']} County ({t['count']} instruments)" for t in tracts]
        idx = st.selectbox("Tract", range(len(tracts)), format_func=lambda i: labels[i])
        t = tracts[idx]
        cutoff = st.text_input("Source cutoff date (YYYY-MM-DD)", value=report_date)
        if st.button("Build report from examined instruments", type="primary"):
            rpt = build_report_from_db(
                DB_PATH, t["section"], t["township"], t["range"],
                county=t["county"], report_date=report_date, source_cutoff_date=cutoff)
else:
    slug = st.selectbox("Bundled tract", list(TRACTS))
    st.caption("Illustrative/specimen data — not an examination of record title.")
    if st.button("Build illustrative report", type="primary"):
        rpt = build_tract(slug, report_date)

if rpt is not None:
    with st.spinner("Generating workbook, dashboard, and running QA gates…"):
        result = generate(rpt, out_dir=str(OUT_DIR), run_date=report_date)
    st.session_state["tr_result"] = result

result = st.session_state.get("tr_result")
if result:
    st.divider()
    status = "PASS" if result["qa_passed"] else "FAIL"
    final = (f"NOT FINAL ({result['data_status']} data)"
             if result["data_status"] != "EXAMINED" else
             ("FINAL-eligible" if result["qa_passed"] else "NOT FINAL (QA failed)"))
    c1, c2, c3 = st.columns(3)
    c1.metric("QA gates", status)
    c2.metric("Data status", result["data_status"])
    c3.metric("Finalization", final)

    counts = result.get("counts", {})
    st.write("**Schedule counts:** " + ", ".join(f"{k}: {v}" for k, v in counts.items()))

    st.subheader("Download deliverables")
    d1, d2, d3 = st.columns(3)
    with d1:
        _download(result["workbook"], "⬇️ Excel workbook", MIME_XLSX)
        _download(result["html"], "⬇️ HTML dashboard", "text/html")
    with d2:
        _download(result["source_log"], "⬇️ SOURCE_LOG.csv", "text/csv")
        _download(result["curative_list"], "⬇️ CURATIVE_LIST.csv", "text/csv")
    with d3:
        _download(result["missing"], "⬇️ MISSING.csv", "text/csv")
        _download(result["qa_results"], "⬇️ QA_RESULTS.md", "text/markdown")

    qa_path = Path(result["qa_results"])
    if qa_path.exists():
        with st.expander("QA results", expanded=not result["qa_passed"]):
            st.markdown(qa_path.read_text(encoding="utf-8"))

    html_path = Path(result["html"])
    if html_path.exists():
        with st.expander("Preview HTML dashboard"):
            components.html(html_path.read_text(encoding="utf-8"), height=700, scrolling=True)
