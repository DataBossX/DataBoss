"""Generated project-control dashboard (Move #5) — a single self-contained
HTML file rendered from the data layer (manifests, health, needs-me queue).

No external assets, no JavaScript frameworks, nothing invented: every number
on the page comes from the same functions the CLI uses. Regenerate any time;
never hand-edit.
"""

from __future__ import annotations

import html
from pathlib import Path

from .health import assess
from .manifest import ProjectManifest, find_manifests
from .needs_me import collect

_STATE_COLOR = {"OK": "#1a7f37", "ATTENTION": "#9a6700", "BLOCKED": "#cf222e"}

_CSS = """
body{font-family:system-ui,sans-serif;margin:2rem auto;max-width:60rem;
     line-height:1.45;color:#1f2328}
h1{font-size:1.4rem} h2{font-size:1.1rem;margin-top:2rem}
table{border-collapse:collapse;width:100%}
td,th{border:1px solid #d0d7de;padding:.4rem .6rem;text-align:left;
      vertical-align:top;font-size:.92rem}
th{background:#f6f8fa}
.badge{display:inline-block;padding:.1rem .5rem;border-radius:1rem;
       color:#fff;font-size:.8rem;font-weight:600}
.sev-critical{color:#cf222e;font-weight:700}.sev-high{color:#9a6700;font-weight:600}
.sev-medium{color:#57606a}.sev-low,.sev-{color:#8c959f}
footer{margin-top:2rem;color:#57606a;font-size:.85rem}
"""


def _badge(state: str) -> str:
    color = _STATE_COLOR.get(state, "#57606a")
    return f'<span class="badge" style="background:{color}">{html.escape(state)}</span>'


def generate_dashboard(projects_root: str | Path, generated_at: str) -> str:
    """Render the dashboard HTML. ``generated_at`` is passed in so output is
    deterministic for a given data state."""
    manifest_paths = find_manifests(projects_root)
    sections: list[str] = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>DataBossX Control Dashboard</title>",
        f"<style>{_CSS}</style></head><body>",
        "<h1>DataBossX Control Dashboard</h1>",
        f"<p>Generated {html.escape(generated_at)} from "
        f"{len(manifest_paths)} project manifest(s). "
        "Every value is computed from the data layer — no invented numbers.</p>",
        "<h2>Projects</h2>",
        "<table><tr><th>Project</th><th>Client</th><th>Overall</th>"
        "<th>Dimensions</th></tr>",
    ]
    for mp in manifest_paths:
        m = ProjectManifest.load(mp)
        h = assess(mp.parent)
        dims = "<br>".join(
            f"{_badge(d.state)} {html.escape(d.name)}: {html.escape(d.detail)}"
            for d in h.dimensions)
        sections.append(
            f"<tr><td><b>{html.escape(m.project_id)}</b><br>"
            f"<small>{html.escape(m.county)} Co., {html.escape(m.jurisdiction)} "
            f"Sec {html.escape(m.section)}-{html.escape(m.township)}-"
            f"{html.escape(m.range)}</small></td>"
            f"<td>{html.escape(m.client)}</td>"
            f"<td>{_badge(h.overall)}</td><td>{dims}</td></tr>")
    sections.append("</table>")

    items = collect(projects_root)
    sections.append(f"<h2>What needs you — {len(items)} decision(s)</h2>")
    if items:
        sections.append("<table><tr><th>Severity</th><th>Project</th>"
                        "<th>Source</th><th>Decision</th></tr>")
        for i in items:
            sev = i.severity or "info"
            sections.append(
                f"<tr><td class='sev-{html.escape(sev)}'>{html.escape(sev.upper())}</td>"
                f"<td>{html.escape(i.project)}</td><td>{html.escape(i.source)}</td>"
                f"<td>{html.escape(i.description)}</td></tr>")
        sections.append("</table>")
    else:
        sections.append("<p>Nothing needs you. All tracked decisions are resolved.</p>")

    sections.append(
        "<footer>DataBossX land_title_os — regenerate with "
        "<code>python -m core.land_title_os dashboard</code>. "
        "Private operating data: do not publish.</footer></body></html>")
    return "\n".join(sections)


def write_dashboard(projects_root: str | Path, out_path: str | Path,
                    generated_at: str) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(generate_dashboard(projects_root, generated_at), encoding="utf-8")
    return out
