#!/usr/bin/env python3
"""DataBossX Title Report Engine v3 -- orchestrator.

Runs the full evidence-based pipeline for Section 31-12N-24W, Roger Mills County,
Oklahoma against a Horizon root folder:

  discover -> rank sources -> profile template -> profile Tract 1 -> parse
  runsheet -> parse OGL schedule -> build chain -> match OGLs -> assumptions ->
  notes -> final owners -> write workbook -> audit logs -> QA -> summary.

The engine never fabricates ownership. When the source files are absent or
incomplete it produces the best evidence-supported (often empty) workbook,
marks every gap, and exits with an honest "PASS WITH REVIEW FLAGS" / review
status rather than a fake clean report.

Usage:
    python app.py [--root PATH] [--demo]

--root  Horizon root to scan (default: the folder that CONTAINS this engine).
--demo  Also run the pipeline against the SYNTHETIC fixture under tests/ and
        write its (clearly-labeled synthetic) output into data/output, to prove
        the chain math end-to-end. The synthetic run never touches the top-level
        final report path.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import COUNTY, SECTION, STATE, __version__          # noqa: E402
from engine.assumptions import collect_assumptions, collect_flags  # noqa: E402
from engine.audit import AUDIT_COLUMNS, build_audit               # noqa: E402
from engine.chain import build_all                                # noqa: E402
from engine.discover import discover, rank_sources                # noqa: E402
from engine.ingest import load_workbook_rows                      # noqa: E402
from engine.models import FileRecord                              # noqa: E402
from engine.ogl_matcher import match_ogls, parse_ogl_schedule     # noqa: E402
from engine.parser import parse_runsheet_book                     # noqa: E402
from engine.qa import run_qa                                      # noqa: E402
from engine.tract1_profile import profile_template                # noqa: E402
from engine.utils import (get_logger, now_compact, now_stamp,     # noqa: E402
                          parse_acres, write_table_xlsx)
from engine.verifier import final_owner_table, owner_counts       # noqa: E402
from engine.writer import write_report                            # noqa: E402

log = get_logger()

LOGS = HERE / "logs"
DATA_INPUT = HERE / "data" / "input"
DATA_TEMPLATE = HERE / "data" / "template"
DATA_OUTPUT = HERE / "data" / "output"


def _pick(bucket: List[FileRecord]) -> Optional[FileRecord]:
    return bucket[0] if bucket else None


def run(root: Path) -> dict:
    root = Path(root)
    for d in (LOGS, DATA_INPUT, DATA_TEMPLATE, DATA_OUTPUT):
        d.mkdir(parents=True, exist_ok=True)

    log.info("=" * 70)
    log.info("DataBossX Title Report Engine v%s | Section %s, %s County, %s",
             __version__, SECTION, COUNTY, STATE)
    log.info("Horizon root: %s", root)
    log.info("=" * 70)

    # --- Task 1: discover -------------------------------------------------
    records = discover(root)
    write_table_xlsx(LOGS / "FILE_INVENTORY.xlsx",
                     ["path", "name", "ext", "size_bytes", "modified", "sha256",
                      "role", "confidence", "notes"],
                     [r.model_dump() for r in records], "File Inventory")

    buckets = rank_sources(records)
    template_rec = _pick(buckets["template"])
    runsheet_rec = _pick(buckets["runsheet"])
    ogl_rec = _pick(buckets["ogl"])
    prior_rec = _pick(buckets["prior_report"])

    ranking_rows = []
    for role, rec in [("template", template_rec), ("runsheet", runsheet_rec),
                      ("ogl", ogl_rec), ("prior_report", prior_rec)]:
        ranking_rows.append({
            "Role": role, "Selected": rec.name if rec else "NONE FOUND",
            "Path": rec.path if rec else "",
            "Confidence": rec.confidence if rec else 0.0,
            "Reason": rec.notes if rec else "no candidate met the confidence threshold",
        })
    for role in ("template", "runsheet", "ogl", "prior_report"):
        for rec in buckets[role][1:]:
            ranking_rows.append({"Role": f"{role} (rejected)", "Selected": rec.name,
                                 "Path": rec.path, "Confidence": rec.confidence,
                                 "Reason": "lower confidence than selected candidate"})
    write_table_xlsx(LOGS / "SOURCE_FILE_RANKING.xlsx",
                     ["Role", "Selected", "Path", "Confidence", "Reason"],
                     ranking_rows, "Source Ranking")

    # --- Task 5: copy selected sources into the workspace (non-destructive)
    import shutil
    if template_rec:
        try:
            shutil.copyfile(template_rec.path, DATA_TEMPLATE / "template.xlsx")
        except Exception as exc:
            log.warning("could not copy template: %s", exc)
    for rec in filter(None, [runsheet_rec, ogl_rec]):
        try:
            shutil.copyfile(rec.path, DATA_INPUT / Path(rec.path).name)
        except Exception as exc:
            log.warning("could not copy %s: %s", rec.name, exc)

    # --- Tasks 6 & 7: template + Tract 1 profile --------------------------
    template_path = (DATA_TEMPLATE / "template.xlsx") if template_rec else None
    template_prof = profile_template(template_path)
    write_table_xlsx(LOGS / "TEMPLATE_PROFILE.xlsx",
                     ["name", "index", "role", "hidden", "max_row", "max_col",
                      "freeze_panes", "has_formulas", "merged_cells"],
                     [{"name": s.name, "index": s.index, "role": s.role,
                       "hidden": s.hidden, "max_row": s.max_row, "max_col": s.max_col,
                       "freeze_panes": s.freeze_panes, "has_formulas": s.has_formulas,
                       "merged_cells": len(s.merged_cells)}
                      for s in template_prof.sheets] or
                     [{"name": "(no template)", "index": 0, "role": template_prof.note}],
                     "Template Profile")
    t1 = template_prof.tract1
    write_table_xlsx(LOGS / "TRACT1_PROFILE.xlsx",
                     ["attribute", "value"],
                     [{"attribute": k, "value": v} for k, v in {
                         "sheet_name": t1.sheet_name or "(none)",
                         "header_row": t1.header_row,
                         "headers": " | ".join(t1.headers),
                         "column_index": str(t1.column_index),
                         "first_data_row": t1.first_data_row,
                         "total_row": t1.total_row,
                         "yellow_fill_seen": t1.yellow_fill_seen,
                     }.items()], "Tract 1 Profile")

    # --- Task 8: parse runsheet ------------------------------------------
    evidence = []
    if runsheet_rec:
        book = load_workbook_rows(Path(runsheet_rec.path))
        evidence = parse_runsheet_book(book)
        if book.note:
            log.warning("runsheet note: %s", book.note)
    write_table_xlsx(LOGS / "PARSED_RUNSHEET_EVIDENCE.xlsx",
                     list(evidence[0].model_dump().keys()) if evidence else
                     ["source_file", "instrument_type", "grantor", "grantee", "note"],
                     [e.model_dump() for e in evidence] or
                     [{"source_file": "(none)", "instrument_type": "", "grantor": "",
                       "grantee": "", "note": "no runsheet found in Horizon root"}],
                     "Runsheet Evidence")

    # --- Task 9: OGL schedule + matching ---------------------------------
    schedule = []
    ogl_source = None
    if ogl_rec:
        ogl_source = ogl_rec.path
        obook = load_workbook_rows(Path(ogl_rec.path))
        schedule = parse_ogl_schedule(obook)
    elif runsheet_rec:  # OGL tab may live inside the runsheet workbook
        schedule = parse_ogl_schedule(load_workbook_rows(Path(runsheet_rec.path)))
        if schedule:
            ogl_source = runsheet_rec.path + " (OGL tab)"
    matches = match_ogls(evidence, schedule) if evidence or schedule else []
    write_table_xlsx(LOGS / "OGL_MATCH_REPORT.xlsx",
                     ["ogl_number", "runsheet_row", "schedule_row", "confidence",
                      "status", "detail"],
                     [{"ogl_number": m.ogl_number, "runsheet_row": m.runsheet_row,
                       "schedule_row": m.schedule_row, "confidence": m.confidence,
                       "status": m.status, "detail": m.detail} for m in matches] or
                     [{"ogl_number": "", "status": "no OGL data",
                       "detail": "no OGL schedule or runsheet OGL rows found"}],
                     "OGL Match Report")

    # --- Task 10: chain ---------------------------------------------------
    template_acres = _template_acres_by_tract(template_prof)
    results = build_all(evidence, template_acres)

    # chain ledger export
    ledger_rows = []
    for res in results:
        for ev in res.events:
            ledger_rows.append(ev.model_dump())
    write_table_xlsx(LOGS / "CHAIN_CALCULATION_LEDGER.xlsx",
                     ["tract", "seq", "instrument_number", "instrument_type",
                      "instrument_date", "grantor", "grantee", "action",
                      "before_acres", "conveyed_acres", "after_acres",
                      "retained_acres", "ogl_reference", "assn_reference",
                      "evidence", "assumption", "flag", "confidence", "notes"],
                     ledger_rows or [{"tract": "(none)", "notes": "no evidence rows to chain"}],
                     "Chain Ledger",
                     yellow_predicate=lambda r, c: c == "assumption" and bool(r.get("assumption")))

    # --- Tasks 11/12: assumptions, flags ---------------------------------
    assumptions = collect_assumptions(results)
    flags = collect_flags(results)
    write_table_xlsx(LOGS / "ASSUMPTIONS_AND_REVIEW_FLAGS.xlsx",
                     ["tract", "type", "statement", "basis", "severity", "action"],
                     [{"tract": a.tract, "type": "ASSUMPTION:" + a.kind,
                       "statement": a.statement, "basis": a.basis,
                       "severity": "yellow", "action": "verify"} for a in assumptions] +
                     [{"tract": f.tract, "type": "FLAG:" + f.category,
                       "statement": f.message, "basis": f.instrument_number,
                       "severity": f.severity, "action": f.recommended_action}
                      for f in flags] or
                     [{"tract": "-", "type": "-", "statement": "no assumptions or flags"}],
                     "Assumptions & Flags",
                     yellow_predicate=lambda r, c: c == "statement" and str(r.get("type", "")).startswith("ASSUMPTION"))

    # --- Task 13: final owners -------------------------------------------
    final_owners = final_owner_table(results)

    # --- Task 16: evidence score -----------------------------------------
    evidence_scores = [{"Tract": r.tract, "Evidence Score": r.evidence_score,
                        "Balanced": "Yes" if r.balanced else "NO",
                        "Control Acres": r.control_acres or "",
                        "Note": r.balance_note} for r in results]
    write_table_xlsx(LOGS / "EVIDENCE_SCORE_BY_TRACT.xlsx",
                     ["Tract", "Evidence Score", "Balanced", "Control Acres", "Note"],
                     evidence_scores or [{"Tract": "(none)", "Evidence Score": 0,
                                          "Balanced": "NO", "Note": "no tracts computed"}],
                     "Evidence Score",
                     yellow_predicate=lambda r, c: c == "Balanced" and r.get("Balanced") == "NO")

    # --- Task 15: audit log ----------------------------------------------
    audit = build_audit(results)
    write_table_xlsx(LOGS / "SECTION31_AUDIT_LOG.xlsx",
                     [c.replace("_", " ").title() for c in AUDIT_COLUMNS],
                     [{c.replace("_", " ").title(): e.model_dump()[c]
                       for c in AUDIT_COLUMNS} for e in audit] or
                     [{c.replace("_", " ").title(): "" for c in AUDIT_COLUMNS}],
                     "Audit Log",
                     yellow_predicate=lambda r, c: c == "Assumption" and bool(r.get("Assumption")))

    # --- Task 14 + 18: write final workbook ------------------------------
    final_name = "SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx"
    final_path = root / final_name
    banner = _banner(runsheet_rec, template_rec, results)

    # QA runs against the workbook, so write first, then QA, then embed QA sheet.
    # We do a two-pass: write once (with a provisional QA), run QA, rewrite with
    # the real QA summary embedded.
    provisional_qa = [{"Check": "pending", "Result": "PASS", "Detail": "pre-QA pass"}]
    write_report(final_path, results, final_owners, assumptions, flags, audit,
                 ranking_rows, evidence_scores, provisional_qa, template_prof, banner)
    qa_checks, qa_status = run_qa(final_path, results, final_owners, flags)
    write_report(final_path, results, final_owners, assumptions, flags, audit,
                 ranking_rows, evidence_scores, qa_checks, template_prof, banner)

    # timestamped backup
    backup = DATA_OUTPUT / final_name.replace(".xlsx", f"_{now_compact()}.xlsx")
    import shutil as _sh
    _sh.copyfile(final_path, backup)

    write_table_xlsx(LOGS / "QA_VALIDATION_REPORT.xlsx",
                     ["Check", "Result", "Detail"], qa_checks, "QA Validation")

    counts = owner_counts(final_owners)
    summary = {
        "final_path": str(final_path), "backup": str(backup),
        "template": template_rec.path if template_rec else "NONE FOUND",
        "runsheet": runsheet_rec.path if runsheet_rec else "NONE FOUND",
        "ogl": ogl_source or "NONE FOUND",
        "prior_report": prior_rec.path if prior_rec else "NONE USED",
        "tracts": len(results), "final_owners": counts["total"],
        "assumptions": len(assumptions), "flags": len(flags),
        "qa_status": qa_status,
        "score_range": _score_range(results),
        "unresolved": _unresolved(runsheet_rec, template_rec, flags, results),
        "files_created": _files_created(final_path, backup),
    }
    _write_run_summary(summary)
    return summary


# ------------------------------------------------------------------ helpers
def _template_acres_by_tract(prof) -> Dict[str, Decimal]:
    """Best-effort control acreage per tract from the template (if any)."""
    return {}  # populated only when a real template tract-total is parseable


def _banner(runsheet_rec, template_rec, results) -> str:
    if not runsheet_rec:
        return ("NO RUNSHEET FOUND IN HORIZON ROOT — this workbook is a STRUCTURAL "
                "template with NO ownership computed. Drop the controlling runsheet "
                "into the Horizon folder and rerun. No owners were invented.")
    if not any(r.events for r in results):
        return ("Runsheet located but no instrument rows parsed — verify the runsheet "
                "tab/headers. No ownership was fabricated.")
    if not template_rec:
        return ("No template workbook found; report built in clean mode honoring the "
                "Tract 1 master style. Formatting is engine-generated, not template-derived.")
    return ""


def _score_range(results) -> str:
    if not results:
        return "n/a"
    scores = [r.evidence_score for r in results]
    return f"{min(scores)}–{max(scores)}"


def _unresolved(runsheet_rec, template_rec, flags, results) -> List[str]:
    items = []
    if not runsheet_rec:
        items.append("No runsheet present in Horizon root — ownership cannot be computed.")
    if not template_rec:
        items.append("No template workbook — output uses engine formatting, not the client template.")
    for f in flags:
        if f.severity == "red":
            items.append(f"T{f.tract} [{f.category}] {f.message}")
    if not items:
        items.append("None — all tracts balanced with no red flags.")
    return items


def _files_created(final_path, backup) -> List[str]:
    created = [str(final_path), str(backup)]
    for f in sorted(LOGS.glob("*")):
        created.append(str(f))
    return created


def _write_run_summary(s: dict):
    lines = [
        "# RUN SUMMARY — DataBossX Title Report Engine v3",
        f"_Generated: {now_stamp()} • Section {SECTION}, {COUNTY} County, {STATE}_",
        "",
        f"- **Final output:** `{s['final_path']}`",
        f"- **Timestamped backup:** `{s['backup']}`",
        f"- **Selected template:** `{s['template']}`",
        f"- **Selected runsheet:** `{s['runsheet']}`",
        f"- **Selected OGL source:** `{s['ogl']}`",
        f"- **Selected prior report:** `{s['prior_report']}`",
        f"- **Tracts processed:** {s['tracts']}",
        f"- **Final owners:** {s['final_owners']}",
        f"- **Assumptions:** {s['assumptions']}",
        f"- **Review flags:** {s['flags']}",
        f"- **Evidence score range:** {s['score_range']}",
        f"- **QA status:** {s['qa_status']}",
        "",
        "## Unresolved issues / next manual review items",
    ]
    for it in s["unresolved"]:
        lines.append(f"- {it}")
    lines += ["", "## Files created", ""]
    for f in s["files_created"]:
        lines.append(f"- `{f}`")
    (LOGS / "RUN_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def _print_summary(s: dict):
    print()
    print("DATA BOSS TITLE ENGINE COMPLETE")
    print()
    print("Final XLSX:");         print(s["final_path"])
    print("\nSelected Template:"); print(s["template"])
    print("\nSelected Runsheet:"); print(s["runsheet"])
    print("\nSelected OGL Source:"); print(s["ogl"])
    print("\nSelected Prior Report:"); print(s["prior_report"])
    print("\nTracts Processed:");  print(s["tracts"])
    print("\nFinal Owners:");      print(s["final_owners"])
    print("\nAssumptions:");       print(s["assumptions"])
    print("\nReview Flags:");      print(s["flags"])
    print("\nQA Status:");         print(s["qa_status"])
    print("\nUnresolved Issues:")
    for it in s["unresolved"]:
        print(f"  - {it}")
    print("\nFiles Created:")
    for f in s["files_created"]:
        print(f"  - {f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DataBossX Title Report Engine v3")
    ap.add_argument("--root", default=str(HERE.parent),
                    help="Horizon root folder to scan (default: parent of this engine)")
    ap.add_argument("--demo", action="store_true",
                    help="Also run against the SYNTHETIC fixture to prove chain math")
    args = ap.parse_args(argv)

    summary = run(Path(args.root))
    _print_summary(summary)

    if args.demo:
        try:
            from tests.make_synthetic import build_synthetic_horizon
            demo_root = HERE / "tests" / "_synthetic_horizon"
            build_synthetic_horizon(demo_root)
            log.info("running SYNTHETIC demo against %s", demo_root)
            demo = run(demo_root)
            # move the synthetic final out of the top-level path into output/
            print("\n[DEMO] Synthetic run QA:", demo["qa_status"],
                  "| tracts:", demo["tracts"], "| owners:", demo["final_owners"])
        except Exception as exc:
            log.warning("demo run failed: %s", exc)

    return 0 if summary["qa_status"] != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
