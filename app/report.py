"""Render human-readable title-review reports and write them safely.

Reports are written through guardrails.safe_write, so an existing report is
never overwritten — a _REVIEW_<ts> sibling is produced instead.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict, List

from tools import guardrails

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"


def render_decision_report(
    owner: str,
    section: str,
    decision: Dict[str, Any],
    docs: List[Dict[str, Any]],
    generated_at: str | None = None,
) -> str:
    generated_at = generated_at or datetime.datetime.now().isoformat(timespec="seconds")
    lines = [
        f"# DataBossX Title Review — {section}",
        "",
        f"**Owner queried:** {owner}",
        f"**Section:** {section}",
        f"**Generated:** {generated_at}",
        "",
        "## Decision",
        f"- **Status:** {decision.get('status')}",
        f"- **Confidence:** {decision.get('confidence')}",
        f"- **Explanation:** {decision.get('explanation')}",
        "",
        "## Instrument chain (as extracted)",
        "",
        "| # | Instrument | Recording date | Grantor | Grantee | Legal |",
        "|---|-----------|----------------|---------|---------|-------|",
    ]
    for i, d in enumerate(docs, 1):
        grantees = ", ".join(d.get("grantee") or []) or "—"
        lines.append(
            f"| {i} | {d.get('instrument') or '—'} | {d.get('recording_date') or '—'} "
            f"| {d.get('grantor') or '—'} | {grantees} | {d.get('legal_short') or '—'} |"
        )
    lines += [
        "",
        "---",
        "_Untrusted source data. AI-assisted extraction — review by a qualified "
        "landman/attorney before relying on this. Every step is logged in the "
        "DataBossX audit_log._",
        "",
    ]
    return "\n".join(lines)


def render_summary_report(results: List[Dict[str, Any]], generated_at: str | None = None) -> str:
    """Render a one-line-per-section summary across a notice-list run."""
    generated_at = generated_at or datetime.datetime.now().isoformat(timespec="seconds")
    lines = [
        "# DataBossX Notice-List Summary",
        "",
        f"**Generated:** {generated_at}",
        f"**Sections processed:** {len(results)}",
        "",
        "| Owner | Section | Status | Confidence | Docs |",
        "|-------|---------|--------|------------|------|",
    ]
    for r in results:
        d = r.get("decision", {})
        lines.append(
            f"| {r.get('owner') or '—'} | {r.get('section') or '—'} | {d.get('status') or '—'} "
            f"| {d.get('confidence') if d.get('confidence') is not None else '—'} "
            f"| {len(r.get('docs') or [])} |"
        )
    lines += ["", "_AI-assisted; review by a qualified professional. See per-section reports and audit_log._", ""]
    return "\n".join(lines)


def write_report(
    text: str,
    section: str,
    out_dir: Path | None = None,
    ts: str | None = None,
) -> Path:
    out_dir = out_dir or REPORTS_DIR
    ts = ts or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_section = section.replace(" ", "_").replace("/", "_")
    target = Path(out_dir) / f"{safe_section}_REVIEW_{ts}.md"
    return guardrails.safe_write(target, text)
