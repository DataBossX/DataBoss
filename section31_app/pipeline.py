"""End-to-end Section 31 pipeline orchestrator.

Runs the full mission in order:
  bootstrap -> scan (local-first, Drive fallback) -> rank -> select base ->
  merge tabs -> read runsheet (controlling fallback) -> crosswalk legals ->
  push OGL numbers -> normalise title + WI ownership -> wells (local + OCC) ->
  QA -> export final XLSX (+ timestamped copy) -> archive non-final files.

Pure orchestration: every step lives in its own module and is independently
testable. The function returns a rich result dict the Streamlit UI renders.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import archive as archive_mod
from . import legal_match, leasehold, ownership, wells
from .bootstrap import bootstrap
from .config import Section31Config
from .drive import DriveClient
from .exporter import export_workbook
from .logbook import LogBook
from .okcountyrecords import OKCountyRecordsClient
from .qa import qa_verdict, run_qa
from .ranker import rank_workbooks, select_base
from .runsheet import read_runsheet
from .scanner import scan_all
from .schema import SHEETS
from .spend import SpendTracker


class PipelineResult(dict):
    """dict subclass so the UI can attach attributes without ceremony."""


def _change(log: LogBook, changes: List[Dict], step: str, action: str, detail: str):
    log.info(f"{step}: {action} -- {detail}")
    changes.append({
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
        "step": step, "action": action, "detail": detail,
    })


def run_pipeline(
    cfg: Section31Config,
    extra_roots: Optional[List[str]] = None,
    use_drive: bool = False,
    do_archive: bool = True,
) -> PipelineResult:
    log = LogBook(cfg.logs_dir / "section31_audit.log")
    changes: List[Dict] = []
    spend = SpendTracker(cap=cfg.image_spend_cap,
                         log_path=cfg.logs_dir / "spend_log.csv")

    # 0. Bootstrap workspace + template.
    boot = bootstrap(cfg, log)
    _change(log, changes, "bootstrap", "workspace ready",
            f"seeded_template={boot['seeded_template']}")

    # 1. Scan (local-first, Drive fallback).
    drive = DriveClient(log) if use_drive else None
    candidates = scan_all(cfg, extra_roots=extra_roots, drive_client=drive,
                          use_drive=use_drive)
    _change(log, changes, "scan", "found candidates",
            f"{len(candidates)} files "
            f"({sum(c.kind=='workbook' for c in candidates)} workbooks, "
            f"{sum(c.kind=='runsheet' for c in candidates)} runsheets, "
            f"{sum(c.kind=='image' for c in candidates)} images)")

    # 2-3. Rank + select base workbook.
    ranked = rank_workbooks(candidates)
    base = select_base(ranked)
    base_path = base.path if base else None
    _change(log, changes, "rank", "selected base",
            base.name if base else "none (no workbooks found)")

    # 4. Merge workbook tabs into canonical sheets.
    from .workbook_merge import merge_workbooks

    data: Dict[str, List[Dict]] = {name: [] for name in SHEETS}
    merged = merge_workbooks(ranked, base_path)
    for sheet, rows in merged.items():
        data[sheet] = rows
    _change(log, changes, "merge", "merged tabs",
            ", ".join(f"{k}={len(v)}" for k, v in merged.items()) or "nothing to merge")

    # 5. Runsheet = controlling fallback.
    runsheet_rows: List[Dict] = []
    for rw in ranked:
        runsheet_rows.extend(read_runsheet(rw.path))
    if runsheet_rows:
        data["Runsheet"] = runsheet_rows
    _change(log, changes, "runsheet", "read controlling notes/legals",
            f"{len(runsheet_rows)} runsheet entries")

    # 6-7. Crosswalk runsheet legals to OGL legals; push OGL onto records.
    ogl_rows = data.get("OGL Register", [])
    runsheet_legals = sorted({r.get("legal_description", "")
                              for r in runsheet_rows if r.get("legal_description")})
    matches = legal_match.crosswalk(runsheet_legals, ogl_rows,
                                    threshold=cfg.legal_match_threshold)
    data["Legal Crosswalk"] = [m.as_row() for m in matches]
    pushed = 0
    for sheet in ("Tract & Title Ownership", "Leasehold WI Ownership"):
        pushed += legal_match.push_ogl_onto_records(data.get(sheet, []), matches)
    _change(log, changes, "crosswalk", "matched legals + pushed OGL#",
            f"{sum(m.matched for m in matches)}/{len(matches)} matched, "
            f"{pushed} records stamped with OGL#")

    # 8. Normalise title ownership.
    data["Tract & Title Ownership"] = ownership.normalize_ownership(
        data.get("Tract & Title Ownership", []))
    own_tot = ownership.ownership_totals(data["Tract & Title Ownership"])
    _change(log, changes, "ownership", "normalised title ownership",
            f"{own_tot['owners']} owners, "
            f"{own_tot['total_net_mineral_acres']} net mineral acres")

    # 9. Normalise leasehold / WI.
    data["Leasehold WI Ownership"] = leasehold.normalize_leasehold(
        data.get("Leasehold WI Ownership", []))
    _change(log, changes, "leasehold", "normalised WI + assignment chains",
            str(leasehold.leasehold_totals(data["Leasehold WI Ownership"])))

    # 10-11. Wells: workbook + OKCountyRecords/OCC.
    records = OKCountyRecordsClient(log=log, spend=spend)
    ext = records.fetch_wells()
    data["Wells"] = wells.build_wells(data.get("Wells", []),
                                      ext.wells if ext.available else [])
    _change(log, changes, "wells", "assembled wells",
            f"{len(data['Wells'])} wells "
            f"(records source available={ext.available}; {ext.reason})")

    # 12. Spend + 13. QA.
    data["Spend Log"] = spend.rows()
    spend_summary = spend.summary()
    qa_results = run_qa(data, spend_summary)
    data["QA Checks"] = [q.as_row() for q in qa_results]
    verdict = qa_verdict(qa_results)
    _change(log, changes, "qa", "ran checks", verdict)

    # Sources sheet (provenance of the whole run).
    data["Sources"] = [{
        "name": rw.name, "source": rw.candidate.source, "kind": rw.candidate.kind,
        "score": rw.score, "chosen_base": "yes" if rw.path == base_path else "",
        "sheet_names": ", ".join(rw.sheet_names), "total_rows": rw.total_rows,
        "path": rw.path, "reasons": " ; ".join(rw.reasons),
    } for rw in ranked]
    data["Change Log"] = changes

    # 14. Export final XLSX (+ timestamped copy in _exports).
    cover_extras = {
        "QA verdict": verdict,
        "Image spend": f"${spend_summary['spent_usd']:.2f} of "
                       f"${spend_summary['cap_usd']:.2f} (cap)",
        "Base workbook": base.name if base else "none",
        "Candidates scanned": len(candidates),
        "Total net mineral acres": own_tot["total_net_mineral_acres"],
    }
    export_workbook(cfg.final_workbook, data, cover_extras)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    copy_path = cfg.exports_dir / f"section31_report_{stamp}.xlsx"
    try:
        shutil.copy2(cfg.final_workbook, copy_path)
    except OSError:
        copy_path = None
    _change(log, changes, "export", "wrote final workbook",
            str(cfg.final_workbook))

    # 15-16. Archive non-final files; leave only the final workbook.
    archived = {}
    if do_archive:
        archived = archive_mod.archive_non_final(cfg, log)
        _change(log, changes, "archive", "moved non-final files",
                str({k: len(v) for k, v in archived.items()}))

    # Persist QA log + completion note.
    _write_qa_log(cfg, qa_results, verdict)
    _write_completion_note(cfg, verdict, own_tot, spend_summary, base)

    return PipelineResult(
        verdict=verdict,
        final_workbook=str(cfg.final_workbook),
        export_copy=str(copy_path) if copy_path else "",
        candidates=[c.__dict__ for c in candidates],
        ranked=[{"name": r.name, "score": r.score, "reasons": r.reasons,
                 "base": r.path == base_path} for r in ranked],
        base=base.name if base else None,
        qa=[q.as_row() for q in qa_results],
        ownership_totals=own_tot,
        spend=spend_summary,
        wells=len(data["Wells"]),
        crosswalk_matched=sum(m.matched for m in matches),
        crosswalk_total=len(matches),
        ogl_pushed=pushed,
        archived=archived,
        clean=archive_mod.verify_clean(cfg) if do_archive else False,
        log=log.text(),
        counts={k: len(v) for k, v in data.items()},
    )


def _write_qa_log(cfg: Section31Config, qa_results, verdict: str):
    lines = [f"Section 31-12N-24W QA LOG", f"Verdict: {verdict}", ""]
    for q in qa_results:
        lines.append(f"[{q.result:<4}] {q.check} ({q.severity}): {q.detail}")
    try:
        (cfg.qa_dir / "qa_log.txt").write_text("\n".join(lines) + "\n",
                                               encoding="utf-8")
    except OSError:
        pass


def _write_completion_note(cfg, verdict, own_tot, spend_summary, base):
    note = f"""SECTION 31-12N-24W ROGER MILLS -- COMPLETION NOTE
================================================================
Status:            {verdict}
Final workbook:    {cfg.final_workbook.name}
Base workbook:     {base.name if base else 'none found'}
Owners (title):    {own_tot['owners']}
Net mineral acres: {own_tot['total_net_mineral_acres']}
Leased tracts:     {own_tot['leased_tracts']}
Open tracts:       {own_tot['open_tracts']}
Image spend:       ${spend_summary['spent_usd']:.2f} of ${spend_summary['cap_usd']:.2f} cap
Main folder holds only the final workbook: {archive_mod.verify_clean(cfg)}

The workbook is the product. Re-run the app any time new source files land in
_candidate_workbooks or _source_images to keep improving it.
"""
    # Written into _qa (not root) so the main folder holds only the final XLSX.
    try:
        (cfg.qa_dir / "COMPLETION_NOTE.txt").write_text(note, encoding="utf-8")
    except OSError:
        pass
