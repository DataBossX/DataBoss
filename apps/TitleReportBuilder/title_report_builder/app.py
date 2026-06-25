"""Streamlit UI for the Title Report Builder. Cross-platform (Windows/macOS/Linux).

Run:  streamlit run title_report_builder/app.py
or via the launcher RUN_APP.bat / run.sh
"""
from __future__ import annotations
import json
from pathlib import Path

try:
    import streamlit as st
except Exception:  # pragma: no cover
    raise SystemExit("Streamlit is not installed. Run INSTALL_OR_REPAIR first.")

from .config import load_secrets
from .discovery import discover, write_manifest
from .report.qa import scan
from .report.workbook_builder import repair_all_tracts
from .models.provider import available_providers

st.set_page_config(page_title="Title Report Builder", layout="wide")
st.title("🛢️  Cursory Title Report Builder")
st.caption("Golden Law: AI does the labor, the human approves risk, every action leaves proof. "
           "The pipeline never fabricates owners, fractions, acreage, royalties, or legals.")

secrets = load_secrets()
with st.sidebar:
    st.subheader("Environment")
    st.write("Model providers available:", ", ".join(available_providers()))
    st.write({k: ("configured" if v else "—") for k, v in secrets.items()})

tabs = st.tabs(["1 · Scan files", "2 · OCR index", "3 · Foot & repair", "4 · QA", "5 · About"])

with tabs[0]:
    proj = st.text_input("Project / evidence folder", "")
    recurse = st.checkbox("Recurse subfolders", True)
    if st.button("Scan", disabled=not proj):
        files = discover(proj, recurse=recurse)
        st.success(f"Found {len(files)} files")
        st.dataframe([f.__dict__ for f in files[:500]])
        outp = Path(proj) / "files" / "_audit" / "source_manifest.csv"
        outp.parent.mkdir(parents=True, exist_ok=True)
        write_manifest(files, str(outp))
        st.info(f"Manifest written: {outp}")

with tabs[1]:
    pdf = st.text_input("Index PDF path", "")
    dpi = st.slider("Render DPI", 150, 400, 300, 10)
    if st.button("Render + OCR", disabled=not pdf):
        from .extractors.pdf_extractor import ocr_pdf
        with st.spinner("OCR running…"):
            pages = ocr_pdf(pdf, dpi=dpi)
        st.success(f"OCR'd {len(pages)} pages")
        st.text_area("Page 1 preview", pages[0][:2000] if pages else "", height=240)

with tabs[2]:
    wb = st.text_input("Workbook (.xlsx)", "")
    out = st.text_input("Output (.xlsx)", "")
    tracts = st.text_input("Tract sheet names (comma-sep)",
                           "Tract 1,Tract 2,Tract 3,Tract 4,Tract 5,Tract 6,Tract 7,Tract 8")
    if st.button("Standardize footing + exact fractions", disabled=not (wb and out)):
        res = repair_all_tracts(wb, [t.strip() for t in tracts.split(",")], out)
        st.success(f"Saved {out} · fractions replaced: {res['fractions_replaced']}")
        st.dataframe([{"tract": k, "D5": v["d5"], "foots": v["foots"],
                       "exact_foot": v["exact_foot"], "pos_owners": v["positive_owners"]}
                      for k, v in res["tracts"].items()])

with tabs[3]:
    wbq = st.text_input("Workbook to QA", "", key="qa")
    if st.button("Run QA", disabled=not wbq):
        rep = scan(wbq)
        (st.success if rep.passed else st.error)(f"QA passed: {rep.passed}")
        st.json({"cached_errors": rep.cached_errors,
                 "formula_error_literals": rep.formula_error_literals,
                 "broken_link_targets": rep.broken_link_targets[:20],
                 "error_samples": rep.error_samples})

with tabs[4]:
    st.markdown(Path(__file__).resolve().parents[1].joinpath("README.md").read_text()
                if Path(__file__).resolve().parents[1].joinpath("README.md").exists()
                else "See README.md")
