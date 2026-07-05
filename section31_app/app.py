"""Streamlit dashboard for the Section 31 report machine.

Run via the desktop launcher, or:  streamlit run section31_app/app.py

Everything the operator needs on one screen: point at the Roger Mills folder,
see scanned candidates and their ranking, run the full pipeline, and review QA,
spend (with the $100 cap), ownership totals, and the final workbook location.
Secrets are never displayed -- only presence/absence of each configured key.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow ``streamlit run section31_app/app.py`` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from section31_app.config import (  # noqa: E402
    DEFAULT_WINDOWS_ROOT, SECTION_LABEL, Section31Config,
)
from section31_app.env_utils import load_env, safe_env_summary  # noqa: E402
from section31_app.ranker import rank_workbooks  # noqa: E402
from section31_app.scanner import scan_all  # noqa: E402
from section31_app.pipeline import run_pipeline  # noqa: E402


st.set_page_config(page_title="Section 31 Report Machine",
                   page_icon="🛢️", layout="wide")


@st.cache_data(show_spinner=False)
def _load_env_summary():
    loaded = load_env()
    watched = {
        "OKCOUNTYRECORDS_BASE_URL": False,
        "OKCOUNTYRECORDS_API_KEY": True,
        "GOOGLE_APPLICATION_CREDENTIALS": False,
        "GOOGLE_DRIVE_FOLDER_ID": False,
        "GOOGLE_DRIVE_TOKEN": True,
    }
    watched.update(loaded)
    return safe_env_summary(watched)


def main():
    st.title("🛢️ Section 31 Ownership & Title Report Machine")
    st.caption(f"{SECTION_LABEL} · Roger Mills County, Oklahoma — "
               "the workbook is the product; this app keeps improving it.")

    with st.sidebar:
        st.header("Configuration")
        root = st.text_input("Roger Mills folder", value=DEFAULT_WINDOWS_ROOT,
                             help="Main folder that holds the final workbook.")
        extra = st.text_area("Extra folders to scan (one per line)", value="")
        use_drive = st.checkbox("Google Drive fallback", value=False,
                               help="Local-first. Only consult Drive when asked "
                                    "or when local sources are thin.")
        do_archive = st.checkbox("Archive non-final files after export",
                                value=True)

        st.divider()
        st.subheader("Environment (.env)")
        st.caption("Presence only — secret values are never shown.")
        for key, state in _load_env_summary().items():
            icon = "✅" if state == "set" else "⬜"
            st.write(f"{icon} `{key}` — {state}")

    cfg = Section31Config.from_env(root)
    extra_roots = [ln.strip() for ln in extra.splitlines() if ln.strip()]

    tab_scan, tab_run, tab_results = st.tabs(
        ["1 · Scan & Rank", "2 · Run Pipeline", "3 · Results & QA"])

    # -- Scan & rank -------------------------------------------------------
    with tab_scan:
        st.subheader("Scan folders for Section 31 files")
        if st.button("🔍 Scan now", type="primary"):
            with st.spinner("Scanning (local-first)…"):
                cands = scan_all(cfg, extra_roots=extra_roots, use_drive=use_drive)
                ranked = rank_workbooks(cands)
            st.session_state["candidates"] = cands
            st.session_state["ranked"] = ranked

        cands = st.session_state.get("candidates", [])
        if cands:
            st.write(f"**{len(cands)}** candidate files found.")
            st.dataframe(
                [{"name": c.name, "kind": c.kind, "source": c.source,
                  "section_match": c.section_match, "path": c.path}
                 for c in cands],
                use_container_width=True, hide_index=True)
        ranked = st.session_state.get("ranked", [])
        if ranked:
            st.subheader("Ranked workbooks (best base first)")
            st.dataframe(
                [{"rank": i + 1, "name": r.name, "score": r.score,
                  "rows": r.total_rows, "tabs": ", ".join(r.sheet_names),
                  "why": " ; ".join(r.reasons)}
                 for i, r in enumerate(ranked)],
                use_container_width=True, hide_index=True)

    # -- Run ---------------------------------------------------------------
    with tab_run:
        st.subheader("Run the full pipeline")
        st.markdown(
            "- Bootstrap folders + template  → scan → rank → select base\n"
            "- Merge tabs → runsheet fallback → crosswalk legals → push OGL#\n"
            "- Normalise title + WI ownership → wells → QA\n"
            "- Export final XLSX → archive non-final files")
        if st.button("▶️ Build / update the final workbook", type="primary"):
            with st.spinner("Running the machine…"):
                result = run_pipeline(cfg, extra_roots=extra_roots,
                                     use_drive=use_drive, do_archive=do_archive)
            st.session_state["result"] = result
            st.success(f"Done — {result['verdict']}")

    # -- Results -----------------------------------------------------------
    with tab_results:
        result = st.session_state.get("result")
        if not result:
            st.info("Run the pipeline to see results here.")
            return
        verdict = result["verdict"]
        (st.success if "READY" == verdict else
         st.warning if "WARNINGS" in verdict else st.error)(verdict)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Owners", result["ownership_totals"]["owners"])
        c2.metric("Net mineral acres",
                  result["ownership_totals"]["total_net_mineral_acres"])
        c3.metric("Wells", result["wells"])
        c4.metric("Image spend",
                  f"${result['spend']['spent_usd']:.0f}",
                  f"cap ${result['spend']['cap_usd']:.0f}")

        st.write(f"**Base workbook:** {result['base']}  ·  "
                 f"**OGL# pushed:** {result['ogl_pushed']}  ·  "
                 f"**Legal matches:** {result['crosswalk_matched']}/"
                 f"{result['crosswalk_total']}")
        st.write(f"**Final workbook:** `{result['final_workbook']}`")
        st.write(f"**Main folder holds only the final XLSX:** {result['clean']}")

        st.subheader("QA checks")
        st.dataframe(result["qa"], use_container_width=True, hide_index=True)

        st.subheader("Sheet row counts")
        st.dataframe([{"sheet": k, "rows": v} for k, v in result["counts"].items()],
                     use_container_width=True, hide_index=True)

        with st.expander("Run log (secret-scrubbed)"):
            st.code(result["log"])

        wb = Path(result["final_workbook"])
        if wb.exists():
            with open(wb, "rb") as fh:
                st.download_button("⬇️ Download final workbook", fh.read(),
                                  file_name=wb.name,
                                  mime="application/vnd.openxmlformats-"
                                       "officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    main()
