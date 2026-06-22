"""Local Streamlit UI for the Cursory Title App (Section 31 first).

Run:  streamlit run cursory_title_app/ui/app.py
Local-first. No data leaves the machine except calls to the configured vision
model API (which you control via .env).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from cursory_title_app import config
from cursory_title_app.db import store
from cursory_title_app.index import render, extract
from cursory_title_app.runsheet import analyzer
from cursory_title_app.excel import writer as xlwriter, verify as xlverify

st.set_page_config(page_title="Cursory Title App — Section 31", layout="wide")
config.ensure_dirs()
store.init()

st.title("Cursory Title App — 31-12N-24W (Roger Mills, OK)")
st.caption("Research/drafting assistant. NOT a title opinion. Human review required.")

# ---- Project loader ----------------------------------------------------------
with st.sidebar:
    st.header("Project")
    wb_path = st.text_input("Target workbook (.xlsx)", "")
    ref_path = st.text_input("Reference/format workbook (.xlsx)", "")
    pdf_path = st.text_input("Index PDF", "")
    st.text_input("Output folder", str(config.OUTPUT_DIR), disabled=True)
    st.divider()
    st.header("Browser (your session)")
    st.code("chrome.exe --remote-debugging-port=9222", language="bat")
    st.write(f"CDP URL: `{config.CDP_URL}`")
    st.caption("Start Chrome yourself, log in, then connect. Manual takeover = "
               "just use the window.")

s = store.stats()
c = st.columns(7)
c[0].metric("Index rows", s["index_rows"])
c[1].metric("Queue", s["queue_total"])
c[2].metric("Missing", s["missing"])
c[3].metric("Conflicts", s["conflict"])
c[4].metric("Review", s["review"])
c[5].metric("Done", s["done"])
c[6].metric("Pending", s["pending"])

tab_idx, tab_an, tab_q, tab_write, tab_qa = st.tabs(
    ["1. Read index", "2. Analyze runsheet", "3. Work queue", "4. Write", "5. QA"])

with tab_idx:
    st.subheader("Read the handwritten index PDF")
    st.info("This index is cursive handwriting — every read is low-confidence and "
            "flagged for human verification.")
    if st.button("Render + extract index", disabled=not pdf_path):
        with st.spinner("Rendering pages…"):
            pages = render.render_pdf(Path(pdf_path))
        st.success(f"Rendered {len(pages)} pages.")
        prog = st.progress(0.0)
        for i, p in enumerate(pages):
            try:
                rows = extract.extract_page(p, i + 1)
                st.write(f"Page {i+1}: {len(rows)} rows")
            except Exception as e:
                st.error(f"Page {i+1} failed: {e}")
            prog.progress((i + 1) / len(pages))
        st.success("Index extraction complete. See SQLite store.")

with tab_an:
    st.subheader("Diff existing Runsheet vs index")
    if st.button("Analyze", disabled=not wb_path):
        rep = analyzer.analyze(Path(wb_path))
        st.json(rep)

with tab_q:
    st.subheader("Work queue")
    rows = store.fetch_all(
        "SELECT id,diff_kind,status,book_page,doc_type,grantor,grantee,runsheet_row "
        "FROM work_queue ORDER BY (diff_kind='missing') DESC, id LIMIT 500")
    st.dataframe(rows, use_container_width=True)

with tab_write:
    st.subheader("Write to workbook (new copy + backup)")
    st.warning("Writes only to existing cells A–N, T, U. Never touches formula "
               "columns O–S. Never overwrites your source file.")
    st.caption("Wire approved RunsheetWrite objects from the queue here, then:")
    st.code("from cursory_title_app.excel import writer\n"
            "report = writer.write_runsheet(Path(wb_path), writes)", language="python")

with tab_qa:
    st.subheader("Verify produced workbook")
    out_file = st.text_input("Produced .xlsx to verify", "")
    if st.button("Verify", disabled=not (out_file and wb_path)):
        res = xlverify.verify_workbook(Path(out_file), Path(wb_path))
        (st.success if res["ok"] else st.error)("OK" if res["ok"] else "FAILED")
        st.json(res)
