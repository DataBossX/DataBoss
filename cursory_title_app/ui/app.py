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

tab_idx, tab_an, tab_q, tab_write, tab_qa, tab_build, tab_reimp = st.tabs(
    ["1. Read index", "2. Analyze runsheet", "3. Work queue", "4. Write", "5. QA",
     "6. Build 6-25-2026 report", "7. Re-import & write"])

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

with tab_build:
    import platform
    from cursory_title_app.reports import builder

    st.subheader("Build the 6-25-2026 report (one click)")
    on_windows = platform.system() == "Windows"
    st.write(f"Excel-COM backend available: **{'yes (Windows)' if on_windows else 'no — will use openpyxl'}**")
    st.caption("Produces 3 files in your output folder: the dated report "
               "(format-preserved, links repaired, QC-flagged), the ownership "
               "reconciliation, and the curative manifest. Nothing is fabricated; "
               "a timestamped backup of your source is made first.")
    backend_choice = st.radio("Excel write backend", ["auto", "com", "openpyxl"],
                              horizontal=True,
                              help="auto = Excel COM on Windows, else openpyxl.")
    if st.button("🛠️ Build 6-25-2026 report", type="primary", disabled=not wb_path):
        try:
            with st.spinner("Building…"):
                res = builder.build_all(Path(wb_path), prefer=backend_choice)
            dw = res["dated_workbook"]
            (st.success if dw["verify_ok"] else st.error)(
                f"Dated workbook built via **{dw['backend']}** — "
                f"verify {'PASSED' if dw['verify_ok'] else 'FAILED'}. "
                f"{len(dw['link_fixes'])} links repaired, "
                f"{len(dw['date_flags'])} date flags added.")

            o = res["ownership"]
            st.markdown(f"**Ownership reconciliation** — ledger NMA "
                        f"`{o['ledger_total_nma']}` vs Title-tab `{o['title_total_nma']}` "
                        f"of 640 total.")
            st.dataframe(o["summary"], use_container_width=True)

            st.markdown(f"**Curative manifest** — {res['curative']['items']} cells "
                        f"need a document.")

            for label, p in [("📘 Dated report", dw["output"]),
                             ("📊 Ownership reconciliation", o["output"]),
                             ("📋 Curative manifest (xlsx)", res["curative"]["xlsx"]),
                             ("📋 Curative manifest (csv)", res["curative"]["csv"])]:
                p = Path(p)
                if p.exists():
                    st.download_button(label, p.read_bytes(), file_name=p.name)
        except Exception as e:
            st.exception(e)

    st.divider()
    st.subheader("Open all curative items in my browser")
    st.caption(f"Walks every VERIFY/NEED item, opens its OKCountyRecords search "
               f"in your connected Chrome ({config.CDP_URL}), and saves a "
               f"screenshot + page text into the local evidence store. Pauses for "
               f"manual takeover on CAPTCHA/login/paywall. Never auto-fills the workbook.")
    from cursory_title_app.browser import curative_walker
    colA, colB, colC = st.columns(3)
    max_items = colA.number_input("Max items", 1, 200, 31)
    delay = colB.number_input("Delay between items (s)", 0.0, 30.0, 2.0, step=0.5)
    pause = colC.checkbox("Pause on takeover", value=True)

    if st.button("👀 Dry run (list only)", disabled=not wb_path):
        plan = curative_walker.walk_curative(Path(wb_path), dry_run=True,
                                             max_items=int(max_items))
        st.write(f"Would open **{plan['planned']}** items:")
        st.dataframe(plan["items"], use_container_width=True)

    if st.button("▶ Open in my browser", type="primary", disabled=not wb_path):
        bar = st.progress(0.0)
        msg = st.empty()

        def _prog(n, total, owner):
            bar.progress(n / max(total, 1))
            msg.write(f"{n}/{total}: {owner}")
        try:
            res = curative_walker.walk_curative(
                Path(wb_path), cdp_url=config.CDP_URL, delay=float(delay),
                max_items=int(max_items), pause_on_takeover=pause, progress=_prog)
            st.success(f"Processed {res['processed']}, captured {res['captured']}.")
            st.dataframe(res["results"], use_container_width=True)
            for r in res["results"]:
                shot = r.get("screenshot")
                if shot and Path(shot).exists():
                    st.image(shot, caption=f"#{r['id']} {r.get('owner','')}", width=480)
        except Exception as e:
            st.error("Browser walk failed. Is Chrome running with "
                     f"--remote-debugging-port matching {config.CDP_URL}, and are "
                     "you logged in?")
            st.exception(e)

with tab_reimp:
    import tempfile
    from cursory_title_app.reports import reimport

    st.subheader("Re-import reviewed picks → write to the Runsheet")
    st.caption("1) Download the template. 2) Open each document in your browser, "
               "paste the real document_link and any corrected fields, set "
               "approve=yes on verified rows. 3) Upload it back — ONLY approved "
               "rows are written, to a NEW workbook copy. 'add' rows are appended "
               "with the O–S formulas copied down; 'update' rows touch A–N/T/U only.")

    if st.button("⬇️ Generate re-import template", disabled=not wb_path):
        tmp = Path(tempfile.gettempdir()) / "reimport_template.csv"
        info = reimport.template_csv(Path(wb_path), tmp)
        st.success(f"Template: {info['add_rows']} add rows, {info['update_rows']} update rows.")
        st.download_button("Download template CSV", tmp.read_bytes(),
                           file_name="reimport_template.csv", mime="text/csv")

    st.divider()
    up = st.file_uploader("Upload your edited (approved) CSV", type=["csv"])
    backend_choice2 = st.radio("Write backend", ["auto", "com", "openpyxl"],
                               horizontal=True, key="reimp_backend")
    if up is not None and st.button("✍️ Write approved rows → new workbook",
                                    type="primary", disabled=not wb_path):
        tmp_csv = Path(tempfile.gettempdir()) / "reimport_approved.csv"
        tmp_csv.write_bytes(up.getvalue())
        try:
            res = reimport.apply_csv(Path(wb_path), tmp_csv, prefer=backend_choice2)
            (st.success if res["verify_ok"] else st.error)(
                f"Wrote via {res['backend']}: {len(res['rows_added'])} added, "
                f"{len(res['rows_updated'])} updated, {res['rows_skipped']} skipped "
                f"(not approved). Verify {'PASSED' if res['verify_ok'] else 'FAILED'}.")
            st.json({k: res[k] for k in ("rows_added", "rows_updated",
                                         "rows_skipped", "cells_written")})
            p = Path(res["output"])
            if p.exists():
                st.download_button("📘 Download updated workbook", p.read_bytes(),
                                   file_name=p.name)
        except Exception as e:
            st.exception(e)
