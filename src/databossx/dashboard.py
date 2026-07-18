"""Self-contained HTML project dashboard.

One file, no external assets, no secrets -- safe to double-click on Windows. It
shows the run's RAG status, headline counts, the deliverables produced, and the
defect list a person must work before release.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .command_center import RunResult

_RAG_COLORS = {"GREEN": "#1a7f37", "YELLOW": "#9a6700", "RED": "#b42318"}


def _esc(v: object) -> str:
    return html.escape("" if v is None else str(v))


def render_dashboard(result: "RunResult") -> str:
    rag = result.rag
    color = _RAG_COLORS.get(rag, "#555")
    counts = result.counts

    def card(label: str, value: object) -> str:
        return (f'<div class="card"><div class="num">{_esc(value)}</div>'
                f'<div class="lbl">{_esc(label)}</div></div>')

    cards = "".join([
        card("Runsheet rows", counts.get("runsheet_rows", 0)),
        card("Tracts", counts.get("tracts", 0)),
        card("Mineral owners", counts.get("mineral_owners", 0)),
        card("DOI rows", counts.get("doi_rows", 0)),
        card("Chain breaks", counts.get("chain_breaks", 0)),
        card("Examiner reviews", counts.get("review_items", 0)),
        card("Defects", counts.get("defects", 0)),
        card("Evidence records", counts.get("evidence", 0)),
    ])

    deliv_rows = "".join(
        f"<li><b>{_esc(k)}</b>: <code>{_esc(v)}</code></li>"
        for k, v in result.deliverables.items() if not isinstance(v, list))

    if result.defects:
        sev_rank = {"red": 0, "yellow": 1, "info": 2}
        defect_rows = "".join(
            f'<tr class="sev-{_esc(d.get("severity",""))}">'
            f'<td>{_esc(d.get("severity",""))}</td>'
            f'<td>{_esc(d.get("category",""))}</td>'
            f'<td>{_esc(d.get("subject",""))}</td>'
            f'<td>{_esc(d.get("detail",""))}</td>'
            f'<td>{_esc(d.get("curative",""))}</td></tr>'
            for d in sorted(result.defects,
                            key=lambda x: sev_rank.get(x.get("severity"), 3)))
        defects_table = (
            "<table><thead><tr><th>Severity</th><th>Category</th><th>Subject</th>"
            "<th>Detail</th><th>Curative action</th></tr></thead><tbody>"
            f"{defect_rows}</tbody></table>")
    else:
        defects_table = '<p class="ok">No defects detected in this run.</p>'

    warns = "".join(f"<li>{_esc(w)}</li>" for w in result.warnings) or "<li>none</li>"
    errs = "".join(f"<li>{_esc(e)}</li>" for e in result.errors)
    errs_block = f"<h2>Errors</h2><ul class='err'>{errs}</ul>" if errs else ""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DataBossX Dashboard -- {_esc(result.project)}</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
    margin: 0; background: #f4f6f9; color: #1a2230; }}
  header {{ background: #13233b; color: #fff; padding: 22px 28px; }}
  header h1 {{ margin: 0 0 4px; font-size: 22px; }}
  header .meta {{ opacity: .85; font-size: 13px; }}
  .rag {{ display: inline-block; padding: 4px 14px; border-radius: 20px; color:#fff;
    background: {color}; font-weight: 700; margin-left: 10px; }}
  main {{ max-width: 1080px; margin: 0 auto; padding: 22px 28px 60px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(120px,1fr));
    gap: 12px; margin: 18px 0; }}
  .card {{ background:#fff; border:1px solid #dde3ea; border-radius:10px; padding:14px;
    text-align:center; }}
  .card .num {{ font-size: 28px; font-weight: 700; color:#13233b; }}
  .card .lbl {{ font-size: 12px; color:#5a6675; margin-top:4px; }}
  h2 {{ margin: 26px 0 10px; font-size: 16px; color:#13233b;
    border-bottom: 2px solid #e2e7ee; padding-bottom: 6px; }}
  table {{ width:100%; border-collapse: collapse; background:#fff; font-size:13px;
    border:1px solid #dde3ea; border-radius:8px; overflow:hidden; }}
  th {{ background:#1f3a5f; color:#fff; text-align:left; padding:8px 10px; }}
  td {{ padding:7px 10px; border-top:1px solid #eef1f5; vertical-align:top; }}
  tr.sev-red td {{ background:#fdecea; }}
  tr.sev-yellow td {{ background:#fff8e6; }}
  code {{ background:#eef1f5; padding:1px 5px; border-radius:4px; font-size:12px;
    word-break: break-all; }}
  ul {{ line-height: 1.6; }}
  .ok {{ color:#1a7f37; font-weight:600; }}
  .err {{ color:#b42318; }}
  footer {{ max-width:1080px; margin:0 auto; padding: 0 28px 40px; color:#7a8494;
    font-size:12px; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background:#0f151d; color:#e6ebf2; }}
    .card, table {{ background:#18202b; border-color:#2a3644; }}
    .card .num {{ color:#e6ebf2; }} td {{ border-top-color:#232d3a; }}
    tr.sev-red td {{ background:#3a1e1c; }} tr.sev-yellow td {{ background:#38310f; }}
    code {{ background:#232d3a; }}
  }}
</style></head><body>
<header>
  <h1>DataBossX &mdash; {_esc(result.project)}<span class="rag">{_esc(rag)}</span></h1>
  <div class="meta">Section {_esc(result.section)} &nbsp;|&nbsp; Generated {_esc(result.generated)}
    &nbsp;|&nbsp; Source: <code>{_esc(result.source_root)}</code></div>
</header>
<main>
  <div class="cards">{cards}</div>
  <h2>Deliverables</h2>
  <ul>{deliv_rows or '<li>none</li>'}</ul>
  <h2>Defects &amp; missing evidence</h2>
  {defects_table}
  <h2>Warnings</h2>
  <ul>{warns}</ul>
  {errs_block}
</main>
<footer>
  Unreviewed output is DRAFT work product &mdash; not a certified abstract or
  title opinion. Technical verification is not client release; a human approval
  gate is required.
</footer>
</body></html>
"""


def write_dashboard(path: Path, result: "RunResult") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard(result), encoding="utf-8")
    return path
