"""Report improver — produce an improved, clearly-labeled report as a NEW export.

It never adds unverified legal facts. It reorganizes the best prior report and
appends validation scorecards, missing-source tables and examiner action lists,
tagging every derived statement with a status label.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

LABELS = ["VERIFIED", "UNVERIFIED", "ESCALATED", "BLOCKED BY SPEND CAP",
          "BLOCKED BY MISSING CREDENTIALS", "NEEDS EXAMINER REVIEW"]


def _scorecard(results: List[Dict[str, Any]]) -> str:
    lines = ["| Gate | Status | Severity | Repairable | Subject |",
             "|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['gate_name']} | {r['status']} | {r['severity']} | "
                     f"{'yes' if r.get('repairable') else 'no'} | {r.get('affected_subject','') or ''} |")
    return "\n".join(lines)


def _missing_sources(sources: List[Dict[str, Any]]) -> str:
    open_docs = [s for s in sources if s.get("status") in ("queued", "blocked", "unavailable")]
    if not open_docs:
        return "_No open source documents._"
    lines = ["| Reference | Status | Detail |", "|---|---|---|"]
    for s in open_docs:
        ref = s.get("book_page") or s.get("instrument_number") or "?"
        lines.append(f"| {ref} | {s.get('status')} | {s.get('detail','')} |")
    return "\n".join(lines)


def improve_report(best: Optional[Dict[str, Any]], context: Dict[str, Any],
                   dest_path: Path) -> Path:
    dest_path = Path(dest_path)
    results = context.get("gate_results", [])
    sources = context.get("source_documents", [])
    escalations = context.get("escalations", [])

    base_text = ""
    if best and Path(best["path"]).suffix.lower() in {".md", ".txt"}:
        try:
            base_text = Path(best["path"]).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            base_text = ""

    final_status = context.get("final_status", "PENDING")
    md = [
        f"# Improved Validation Report — {context.get('prospect','(prospect)')}",
        f"Run: `{context.get('run_id','')}` · Final status: **{final_status}**",
        "",
        "> Labels used: " + ", ".join(f"**{l}**" for l in LABELS),
        "> No unverified legal fact is asserted. Open items are labeled, not resolved.",
        "",
        "## Validation scorecard",
        _scorecard(results),
        "",
        "## Missing / unretrieved source documents",
        _missing_sources(sources),
        "",
        "## Examiner action list (ESCALATED / NEEDS EXAMINER REVIEW)",
    ]
    if escalations:
        for e in escalations:
            md.append(f"- **ESCALATED** — {e.get('subject','')}: {e.get('reason','')} "
                      f"(needed: {e.get('needed_document','n/a')})")
    else:
        md.append("- _None._")

    md += ["", "## Source report (verbatim, unmodified excerpt)",
           f"_Best candidate: {best['path'] if best else '(none found)'}_", ""]
    if base_text:
        md.append("```")
        md.append(base_text[:8000])
        md.append("```")
    else:
        md.append("_No machine-readable base report located; scorecard stands alone._")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text("\n".join(md), encoding="utf-8")
    return dest_path
