"""
report.py
=========
Generates a single self-contained HTML report (logs/report.html) from the CSV
audit logs, so a non-coder can see results at a glance in a browser without
opening Excel - color-coded rows, counts, and links.

No external dependencies (hand-rolled HTML + inline CSS).
"""

from __future__ import annotations

import csv
import html
import logging
import os
from datetime import datetime
from typing import Dict, List

log = logging.getLogger("horizon.report")

_STATUS_COLOR = {
    "green": "#C6EFCE",
    "yellow": "#FFEB9C",
    "red": "#FFC7CE",
    "skipped": "#E7E6E6",
    "failed": "#FFC7CE",
    "blocked": "#FFC7CE",
    "login_expired": "#FFC7CE",
    "error": "#FFC7CE",
}


def _read_csv(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _read_summary(path: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not os.path.exists(path):
        return out
    with open(path, "r", newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if len(row) >= 2:
                out[row[0]] = row[1]
    return out


def _esc(v: str) -> str:
    return html.escape(str(v or ""))


def generate_report(logs_dir: str, workbook_name: str = "") -> str:
    """Write logs/report.html and return its path."""
    rows = _read_csv(os.path.join(logs_dir, "run_log.csv"))
    summary = _read_summary(os.path.join(logs_dir, "summary.csv"))
    out_path = os.path.join(logs_dir, "report.html")

    # Count statuses.
    counts: Dict[str, int] = {}
    for r in rows:
        counts[r.get("status", "")] = counts.get(r.get("status", ""), 0) + 1

    def card(label: str, value, color: str = "#f4f4f4") -> str:
        return (
            f"<div style='background:{color};border-radius:8px;padding:12px 18px;"
            f"min-width:120px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.1)'>"
            f"<div style='font-size:26px;font-weight:700'>{_esc(value)}</div>"
            f"<div style='font-size:12px;color:#444'>{_esc(label)}</div></div>"
        )

    cards = "".join(
        [
            card("Rows seen", summary.get("total_rows_seen", len(rows))),
            card("Linked", summary.get("linked_rows", "")),
            card("Processed", summary.get("processed_rows", ""), "#C6EFCE"),
            card("Changed", summary.get("changed_rows", ""), "#FFEB9C"),
            card("Failed", summary.get("failed_rows", ""), "#FFC7CE"),
            card("Skipped", summary.get("skipped_rows", ""), "#E7E6E6"),
            card("Review needed", summary.get("review_needed_rows", ""), "#FFEB9C"),
        ]
    )

    # Table rows.
    header_cells = [
        "Sheet", "Row", "Status", "Confidence", "Changed fields",
        "Review?", "Error", "Link", "Time",
    ]
    thead = "".join(f"<th style='text-align:left;padding:6px 10px'>{h}</th>" for h in header_cells)

    body_rows = []
    for r in rows:
        color = _STATUS_COLOR.get(r.get("status", ""), "#ffffff")
        link = r.get("link", "")
        link_cell = (
            f"<a href='{_esc(link)}' target='_blank'>open</a>" if link else ""
        )
        cells = [
            _esc(r.get("sheet")),
            _esc(r.get("row")),
            f"<b>{_esc(r.get('status'))}</b>",
            _esc(r.get("confidence")),
            _esc(r.get("changed_fields")),
            _esc(r.get("review_needed")),
            _esc(r.get("error_message")),
            link_cell,
            _esc(r.get("timestamp")),
        ]
        tds = "".join(f"<td style='padding:6px 10px'>{c}</td>" for c in cells)
        body_rows.append(f"<tr style='background:{color}'>{tds}</tr>")

    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>HorizonTitleLinkExtractor Report</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#222">
  <h1 style="margin-bottom:4px">Horizon Title Link Extractor - Review Report</h1>
  <div style="color:#666;margin-bottom:16px">
    Workbook: {_esc(workbook_name or summary.get('workbook',''))} &nbsp;|&nbsp;
    Generated: {generated} &nbsp;|&nbsp;
    Run: {_esc(summary.get('start_time',''))} &rarr; {_esc(summary.get('end_time',''))}
  </div>
  <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px">{cards}</div>
  <div style="margin-bottom:12px;color:#666">
    <b>Legend:</b>
    <span style="background:#C6EFCE;padding:2px 8px;border-radius:4px">green = looks good</span>
    <span style="background:#FFEB9C;padding:2px 8px;border-radius:4px">yellow = check suggested change</span>
    <span style="background:#FFC7CE;padding:2px 8px;border-radius:4px">red = failed / needs human</span>
  </div>
  <table style="border-collapse:collapse;width:100%;font-size:13px;box-shadow:0 1px 3px rgba(0,0,0,.1)">
    <thead style="background:#333;color:#fff">{thead}</thead>
    <tbody>{''.join(body_rows)}</tbody>
  </table>
  <p style="color:#999;margin-top:20px;font-size:12px">
    Review only - the original workbook was not modified. Suggested corrections
    live in the AI columns of the output workbook.
  </p>
</body></html>"""

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    log.info("HTML report written: %s", out_path)
    return out_path
