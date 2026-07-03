"""One entry point to close Section 31: status board + guided runner.

It reports where you are in the fetch -> extract -> approve -> write -> report
loop, runs the SAFE steps (status, report rebuild), and prints the exact next
command for the paid (OKCountyRecords) and browser (OCC/OTC) steps — it never
spends money or drives your browser without you asking.

    python -m cursory_title_app.close_section31 --status
    python -m cursory_title_app.close_section31 --report "31-...(7-3-26)-NHE.xlsx"
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import config
from .db import store

PLAN = """
Section 31-12N-24W — close-out plan (run on your machine; see docs/RUN_ON_YOUR_MACHINE.md)
  1. County docs   python -m cursory_title_app.okcounty.fetch            (dry run; ~$26 to --confirm)
                   python -m cursory_title_app.okcounty.process         (vision -> review CSV)
  2. Well/prod     chrome.exe --remote-debugging-port=9222  (log into OCC/OTC)
                   python -m cursory_title_app.occ_otc.browser_fetch    (capture HBP + 1002A/1073)
  3. Approve       edit _data/output/okcounty_reimport.csv -> approve=yes on verified rows
  4. Write         reimport.apply_csv(WORKBOOK, okcounty_reimport.csv)  -> *.REIMPORT.xlsx
  5. Report        python -m cursory_title_app.close_section31 --report *.REIMPORT.xlsx
"""


def status() -> dict:
    store.init()

    def n(sql, p=()):
        try:
            return store.fetch_one(f"SELECT COUNT(*) c FROM {sql}", p)["c"]
        except Exception:
            return 0

    st = {
        "okcounty_queued": n("work_queue WHERE source='okcounty'"),
        "okcounty_downloaded": n("work_queue WHERE source='okcounty' AND status IN ('downloaded','extracted')"),
        "okcounty_extracted": n("work_queue WHERE source='okcounty' AND status='extracted'"),
        "occ_otc_captured": n("work_queue WHERE diff_kind='well_production' AND status IN ('captured','takeover')"),
        "evidence_items": n("evidence"),
    }
    outputs = {}
    for name in ("okcounty_reimport.csv",
                 "31-12N-24W_Roger_Mills_Cursory_Title_Report_(6-25-2026).xlsx",
                 "Section31_Title_Report_(6-25-2026).html",
                 "Section31_Chain_of_Title_(6-25-2026).xlsx"):
        outputs[name] = (config.OUTPUT_DIR / name).exists()
    st["outputs_present"] = outputs
    return st


def rebuild_report(workbook: Path, prefer: str = "auto") -> dict:
    from .reports import builder
    res = builder.build_all(Path(workbook), prefer=prefer)
    return {
        "dated_workbook": res["dated_workbook"]["output"],
        "verify_ok": res["dated_workbook"]["verify_ok"],
        "html_report": res["title_report"]["html"],
        "chain_defects": res["chain"]["summary"]["defects"],
        "curative_items": res["curative"]["items"],
        "ownership_missing_acres": res["title_report"]["kpis"]["missing_acres"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--report", metavar="WORKBOOK", help="rebuild all reports from a workbook")
    ap.add_argument("--prefer", default="auto", choices=["auto", "com", "openpyxl"])
    a = ap.parse_args()

    import json
    config.ensure_dirs()
    if a.report:
        print(json.dumps(rebuild_report(Path(a.report), a.prefer), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2))
        print(PLAN)


if __name__ == "__main__":
    main()
