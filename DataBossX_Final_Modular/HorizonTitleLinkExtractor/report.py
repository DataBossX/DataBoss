"""
report.py
=========
Human-readable HTML review report. A spreadsheet full of new columns is hard to
scan; this produces output/<workbook>_REVIEW_REPORT.html with a color-coded
summary, per-row status, changed fields, costs, and links you can click.

Pure stdlib (string templating) - no jinja/external deps.
"""

from __future__ import annotations

import html
import os
import urllib.parse
from typing import Any

_COLOR_BG = {"green": "#C6EFCE", "yellow": "#FFEB9C", "red": "#FFC7CE",
             "": "#f2f2f2"}

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Horizon Title AI Review</title>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#1a1a1a;background:#fafafa}}
 h1{{margin:0 0 4px}} .sub{{color:#666;margin-bottom:18px}}
 .cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:22px}}
 .card{{background:#fff;border:1px solid #e3e3e3;border-radius:10px;padding:12px 16px;min-width:120px;box-shadow:0 1px 2px rgba(0,0,0,.04)}}
 .card .n{{font-size:26px;font-weight:700}} .card .l{{color:#666;font-size:12px;text-transform:uppercase;letter-spacing:.04em}}
 table{{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
 th,td{{border:1px solid #e6e6e6;padding:7px 9px;font-size:13px;text-align:left;vertical-align:top}}
 th{{background:#2c3e50;color:#fff;position:sticky;top:0}}
 tr:hover td{{background:#fbfbe9}}
 .pill{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}}
 a{{color:#1565c0;text-decoration:none}} a:hover{{text-decoration:underline}}
 .muted{{color:#888}} code{{background:#f0f0f0;padding:1px 4px;border-radius:4px}}
</style></head><body>
<h1>Horizon Title - AI Review Report</h1>
<div class="sub">{workbook} &middot; generated {ts}</div>
<div class="cards">{cards}</div>
{cost}
<table><thead><tr>
 <th>Sheet</th><th>Row</th><th>Status</th><th>Conf.</th><th>Consensus</th>
 <th>Changed fields</th><th>Review?</th><th>Viewer</th><th>Notes</th><th>Link</th>
</tr></thead><tbody>
{rows}
</tbody></table>
<p class="muted" style="margin-top:18px">Review-only output. Original workbook
cells are never modified unless apply_corrections is enabled. Yellow = please
check, Red = could not read / failed, Green = high-confidence match.</p>
</body></html>"""


def _card(n: Any, label: str, color: str = "") -> str:
    bg = _COLOR_BG.get(color, "#fff")
    return (f'<div class="card" style="background:{bg}">'
            f'<div class="n">{html.escape(str(n))}</div>'
            f'<div class="l">{html.escape(label)}</div></div>')


def _safe_link_html(link: str) -> str:
    """Render a document link as a clickable anchor ONLY when it is a web URL.

    Document links come from the (potentially untrusted) source workbook. Any
    non-http(s) scheme - e.g. javascript: or data: - is rendered as inert,
    escaped text so it cannot execute when the report is opened in a browser.
    """
    if not link:
        return '<span class="muted">-</span>'
    scheme = urllib.parse.urlparse(link).scheme.lower()
    if scheme in ("http", "https"):
        return (f'<a href="{html.escape(link, quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">open</a>')
    return (f'<span class="muted" title="non-web link suppressed for safety">'
            f'{html.escape(link)}</span>')


def _row_html(r: dict[str, Any]) -> str:
    bg = _COLOR_BG.get(r.get("color", ""), "#fff")
    link_html = _safe_link_html(r.get("link") or "")
    conf = r.get("confidence")
    conf_html = f"{conf:.2f}" if isinstance(conf, (int, float)) else ""
    changed = ", ".join(r.get("changed_fields", []) or []) or \
        '<span class="muted">-</span>'
    return (
        f'<tr style="background:{bg}">'
        f'<td>{html.escape(str(r.get("sheet","")))}</td>'
        f'<td>{html.escape(str(r.get("row","")))}</td>'
        f'<td><span class="pill" style="background:{bg}">'
        f'{html.escape(str(r.get("status","")))}</span></td>'
        f'<td>{conf_html}</td>'
        f'<td>{html.escape(str(r.get("consensus_label","")))}</td>'
        f'<td>{changed}</td>'
        f'<td>{"YES" if r.get("review_needed") else ""}</td>'
        f'<td>{html.escape(str(r.get("viewer_method","")))}</td>'
        f'<td>{html.escape(str(r.get("notes","") or ""))[:240]}</td>'
        f'<td>{link_html}</td></tr>')


def build_report(path: str, workbook: str, ts: str, summary: dict[str, Any],
                 rows: list[dict[str, Any]], total_cost: float | None = None) -> str:
    cards = "".join([
        _card(summary.get("linked_rows", 0), "linked"),
        _card(summary.get("processed_rows", 0), "processed"),
        _card(summary.get("changed_rows", 0), "changed", "yellow"),
        _card(summary.get("review_needed_rows", 0), "need review", "yellow"),
        _card(summary.get("failed_rows", 0), "failed", "red"),
        _card(summary.get("high_confidence_rows", 0), "high conf.", "green"),
        _card(summary.get("skipped_rows", 0), "skipped"),
    ])
    cost_html = ""
    if total_cost is not None:
        cost_html = (f'<p class="sub">Estimated AI cost this run: '
                     f'<code>${total_cost:.4f}</code></p>')
    body_rows = "\n".join(_row_html(r) for r in rows) or \
        '<tr><td colspan="10" class="muted">No rows processed.</td></tr>'
    out = _PAGE.format(workbook=html.escape(workbook), ts=html.escape(ts),
                       cards=cards, cost=cost_html, rows=body_rows)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(out)
    return path
