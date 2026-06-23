"""CSV and Markdown deliverables that accompany the Excel workbook.

  * SOURCE_LOG.csv
  * CURATIVE_LIST.csv
  * MISSING_OR_UNVERIFIED_INSTRUMENTS.csv
  * CHANGE_SUMMARY.md
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from .models import TitleReport, UNKNOWN
from . import fractions as fr


def _write_csv(path: Path, header: List[str], rows: List[list]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow(r)
    return str(path)


def write_source_log(rpt: TitleReport, out_dir: Path) -> str:
    rows = [
        [s.source_id, s.category, s.name, s.location, s.accessed_date,
         fr.frac_str(s.doc_count) if not isinstance(s.doc_count, str) else s.doc_count,
         "YES" if s.credential_required else "no", s.page_ref, s.notes]
        for s in rpt.sources
    ]
    return _write_csv(
        out_dir / "SOURCE_LOG.csv",
        ["source_id", "category", "name", "location", "accessed_date",
         "doc_count", "credential_required", "page_ref", "notes"],
        rows,
    )


def write_curative_list(rpt: TitleReport, out_dir: Path) -> str:
    rows = [
        [c.issue_id, c.issue_type, c.instrument_no, c.description, c.materiality,
         c.priority, c.status, c.recommended_action, c.citation]
        for c in rpt.curative
    ]
    return _write_csv(
        out_dir / "CURATIVE_LIST.csv",
        ["issue_id", "issue_type", "instrument_no", "description", "materiality",
         "priority", "status", "recommended_action", "citation"],
        rows,
    )


def compute_missing(rpt: TitleReport) -> List[dict]:
    """Derive the missing/unverified list from the model.

    Flags: instruments referenced by abstractions/chains/curative but absent
    from the runsheet; instruments lacking a citation; abstractions marked for
    review; and the global placeholder caveat.
    """
    missing: List[dict] = []
    known_instr = {i.instrument_no for i in rpt.instruments}

    if rpt.config.is_placeholder:
        missing.append({
            "item": "ALL live records", "type": "Placeholder run",
            "reason": "No live county/OCC/BLM/court sources examined.",
            "source": "n/a",
        })

    referenced = set()
    for a in rpt.abstractions:
        referenced.add(a.instrument_no)
    for c in rpt.chain_links:
        referenced.add(c.instrument_no)
    for c in rpt.curative:
        if c.instrument_no and c.instrument_no != UNKNOWN:
            referenced.add(c.instrument_no)
    for ref in sorted(referenced - known_instr):
        missing.append({
            "item": ref, "type": "Referenced instrument",
            "reason": "Referenced by a schedule but absent from the runsheet.",
            "source": "n/a",
        })

    for i in rpt.instruments:
        if i.citation == UNKNOWN or not i.citation:
            missing.append({
                "item": i.instrument_no, "type": "Uncited instrument",
                "reason": "Runsheet row has no source citation.",
                "source": UNKNOWN,
            })

    for a in rpt.abstractions:
        if a.needs_review:
            missing.append({
                "item": a.instrument_no, "type": "Abstraction needs review",
                "reason": "Low-confidence or flagged extraction; manual review required.",
                "source": a.citation,
            })
    return missing


def write_missing(rpt: TitleReport, out_dir: Path) -> str:
    rows = [[m["item"], m["type"], m["reason"], m["source"]] for m in compute_missing(rpt)]
    return _write_csv(
        out_dir / "MISSING_OR_UNVERIFIED_INSTRUMENTS.csv",
        ["item", "type", "reason", "source"],
        rows,
    )


def write_change_summary(rpt: TitleReport, out_dir: Path, run_date: str,
                         prior_exists: bool) -> str:
    path = out_dir / "CHANGE_SUMMARY.md"
    cfg = rpt.config
    if prior_exists:
        body = (
            "## Revision\n\n"
            f"- Regenerated report for {cfg.tract_label} on {run_date}.\n"
            "- Compare schedule counts and curative status against the prior run.\n"
            "- Document any material additions, removals, or status changes below.\n"
        )
    else:
        body = (
            "## Initial generation\n\n"
            f"- First generation of the cursory title report for {cfg.tract_label}.\n"
            f"- Report date: {cfg.report_date}; source cutoff: {cfg.source_cutoff_date}.\n"
            f"- Schedules: {len(rpt.sources)} sources, {len(rpt.instruments)} instruments, "
            f"{len(rpt.wells)} wells, {len(rpt.curative)} curative items, "
            f"{len(rpt.ownership)} ownership entries.\n"
        )
        if cfg.is_placeholder:
            body += "- DATA STATUS: PLACEHOLDER — no live records examined.\n"

    content = (
        f"# CHANGE_SUMMARY — {cfg.tract_label}\n\n"
        f"_Generated {run_date}_\n\n"
        f"{body}\n"
        "Every modification after the first run must be appended here per the QA change-log gate.\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)
