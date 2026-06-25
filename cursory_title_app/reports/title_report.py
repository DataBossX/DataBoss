"""Consolidated, printable HTML title report (the human-facing deliverable).

Pulls together, from data already computed:
  * executive summary (acreage accounted, Title-vs-ledger gap, defect counts)
  * per-tract entity-resolved CURRENT mineral ownership + which owners are
    missing from the curated Title summary
  * chain-of-title defects (categorized) with verified Oklahoma legal authorities
  * curative checklist with authorities
  * legal-authority appendix with verifiable URLs + disclaimer

Research/drafting aid only. NOT a title opinion. External file; the workbook
and its tabs are never touched.
"""
from __future__ import annotations

import html
from pathlib import Path

from .. import config
from . import ownership
from ..chain import reconstruct
from ..legal import authorities as law

DATED = "(6-25-2026)"


def _esc(v) -> str:
    return html.escape("" if v is None else str(v))


def _table(headers, rows, cls="") -> str:
    h = "".join(f"<th>{_esc(x)}</th>" for x in headers)
    body = []
    for r in rows:
        cells = "".join(f"<td>{c if isinstance(c, str) and c.startswith('<') else _esc(c)}</td>"
                        for c in r)
        body.append(f"<tr>{cells}</tr>")
    return f"<table class='{cls}'><thead><tr>{h}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build(source: Path, out_dir: Path = config.OUTPUT_DIR) -> dict:
    rec = ownership.reconcile(source)
    chain = reconstruct.reconstruct(source)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"Section31_Title_Report_{DATED}.html"

    led_total = round(sum((t.get("net_acres_traced") or 0) for t in rec["tracts"]), 2)
    title_total = round(sum((s["title_total"] or 0) for s in rec["summary"]), 2)
    missing_total = round(sum(s["acres_missing_from_title"] for s in rec["summary"]), 2)

    parts = [f"""<!doctype html><html><head><meta charset='utf-8'>
<title>Section 31-12N-24W Cursory Title Report {DATED}</title>
<style>
 body{{font-family:Georgia,serif;max-width:1100px;margin:24px auto;color:#1a1a1a;line-height:1.45}}
 h1{{font-size:24px;border-bottom:3px solid #1F4E78;padding-bottom:6px}}
 h2{{color:#1F4E78;margin-top:30px;border-bottom:1px solid #ccc}}
 h3{{margin-bottom:4px}}
 table{{border-collapse:collapse;width:100%;margin:8px 0;font-size:13px;font-family:Arial,sans-serif}}
 th{{background:#1F4E78;color:#fff;text-align:left;padding:5px 7px}}
 td{{border:1px solid #ddd;padding:4px 7px;vertical-align:top}}
 tr:nth-child(even){{background:#f6f8fb}}
 .miss{{background:#fde9e0!important}}
 .disc{{background:#fff8e1;border:1px solid #e0c200;padding:10px 14px;font-size:13px;border-radius:4px}}
 .kpi{{display:inline-block;border:1px solid #1F4E78;border-radius:6px;padding:8px 14px;margin:4px;min-width:120px}}
 .kpi b{{display:block;font-size:20px;color:#1F4E78}}
 a{{color:#0563C1}} .small{{font-size:12px;color:#555}}
 .cat-wild{{color:#9c1b1b}} .cat-probate{{color:#8a6d00}} .cat-entity{{color:#1f4e78}}
</style></head><body>
<h1>Section 31, T12N, R24W — Roger Mills County, Oklahoma<br><span class='small'>Cursory Title Report {DATED} · computer-assisted draft</span></h1>
<div class='disc'><b>RESEARCH / DRAFTING AID — NOT A TITLE OPINION.</b> Ownership figures are
computed from the existing workbook's tract ledgers; chain-of-title flags and
legal authorities are computer-generated and must be verified by a licensed
Oklahoma attorney/landman against the source instruments. {_esc(law.disclaimer())}</div>

<h2>Executive summary</h2>
<div>
 <span class='kpi'>Section acreage<b>640.00</b></span>
 <span class='kpi'>NMA accounted (ledgers)<b>{led_total}</b></span>
 <span class='kpi'>Curated Title NMA<b>{title_total}</b></span>
 <span class='kpi'>Current owners missing from Title<b>{missing_total} ac</b></span>
 <span class='kpi'>Mineral instruments<b>{chain['total_mineral_events']}</b></span>
 <span class='kpi'>Chain defects to verify<b>{chain['total_defects']}</b></span>
</div>
<p class='small'>Chain defects by category: {_esc(chain['defects_by_category'])}.
Tracts lacking a root grant: {_esc(chain['tracts_without_root'] or 'none')}.</p>
"""]

    # Per-tract ownership
    parts.append("<h2>Current mineral ownership by tract (entity-resolved)</h2>")
    summary_by_tract = {s["tract"]: s for s in rec["summary"]}
    for t in rec["tracts"]:
        s = summary_by_tract.get(t["tract"], {})
        parts.append(f"<h3>Tract {t['tract']} — {_esc(t.get('tract_acres'))} acres</h3>")
        parts.append(f"<p class='small'>Owners (raw→resolved): "
                     f"{s.get('ledger_owners')}→{s.get('ledger_owners_resolved')}; "
                     f"net acres traced {s.get('ledger_net_acres')}; curated Title TOTAL "
                     f"{s.get('title_total')}; <b>{s.get('owners_missing_from_title')} owners "
                     f"/ {s.get('acres_missing_from_title')} ac not in Title summary</b>.</p>")
        rows = []
        for o in t.get("consolidated_owners", [])[:40]:
            tag = "" if o["in_title"] else " class='miss'"
            rows.append((f"<span{tag}>{_esc(o['owner'])}</span>",
                         round(o["net_acres"], 4), round(o["net_interest"], 6),
                         "in Title" if o["in_title"] else "MISSING from Title",
                         len(o["variants"])))
        parts.append(_table(["Owner (resolved)", "Net acres", "Net interest",
                             "Title status", "name variants"], rows))

    # Chain defects with authorities
    parts.append("<h2>Chain-of-title items to verify</h2>")
    parts.append("<p class='small'>A flag means the grantor was not found vested earlier "
                 "in the section chain — verify, do not assume a defect. Cursory report: "
                 "gaps are expected.</p>")
    rows = []
    for d in chain["defects"]:
        auth = law.for_category(d["category"])
        auth_html = "<br>".join(
            f"<a href='{_esc(a.get('url',''))}'>{_esc(a.get('cite') or a.get('statute') or a.get('note'))}</a>"
            if a.get("url") else _esc(a.get("note") or a.get("cite") or a.get("statute"))
            for a in auth) or "<span class='small'>verify; no on-point authority retrieved</span>"
        rows.append((d["row"], d["date"], _esc(d["doc"]), d["tracts"],
                     f"<span class='cat-{d['category'].split('-')[0]}'>{_esc(d['category'])}</span>",
                     _esc(d["grantor"]), d["confidence"], auth_html))
    parts.append(_table(["row", "date", "doc", "tracts", "category", "grantor",
                         "conf", "Oklahoma authority (verify)"], rows))

    # Curative checklist
    parts.append("<h2>Curative checklist (Title-tab gaps)</h2>")
    from .builder import curative_rows
    crows = curative_rows(source)
    rows = []
    for c in crows:
        rows.append((c["tract"], _esc(c["owner"]), _esc(c["stated_net_acres"]),
                     _esc(c["ogl_or_bkpg"]),
                     f"<a href='{_esc(c['okcountyrecords_search'])}'>search</a>"))
    parts.append(_table(["tract", "owner", "stated net ac", "OGL/Bk-Pg", "lookup"], rows))
    parts.append(f"<p class='small'>{len(crows)} curative items. Lease held-by-production "
                 "/ release status requires the lease instruments — see authorities below.</p>")

    # Authorities appendix
    parts.append("<h2>Legal authorities (research aid — verify each)</h2>")
    seen = set()
    rows = []
    for cat in ("wild-deed", "probate", "entity-succession", "ogl-hbp"):
        for a in law.for_category(cat):
            key = a.get("cite") or a.get("statute") or a.get("note")
            if key in seen:
                continue
            seen.add(key)
            link = f"<a href='{_esc(a.get('url',''))}'>{_esc(a.get('url'))}</a>" if a.get("url") else ""
            rows.append((cat, _esc(a.get("cite") or a.get("statute") or "—"),
                         _esc(a.get("point") or a.get("note")), a.get("confidence", ""), link))
    parts.append(_table(["topic", "authority", "point", "conf", "source URL"], rows))

    parts.append("<hr><p class='small'>Generated by Cursory Title App. "
                 "Computer-assisted draft for attorney/landman review. Not a title opinion.</p>")
    parts.append("</body></html>")

    out.write_text("\n".join(parts), encoding="utf-8")
    return {"html": str(out),
            "kpis": {"ledger_nma": led_total, "title_nma": title_total,
                     "missing_acres": missing_total,
                     "chain_defects": chain["total_defects"]}}


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(build(Path(sys.argv[1]))["kpis"], indent=2))
