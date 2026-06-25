"""Self-contained interactive HTML dashboard for a cursory title report.

Produces a single ``.html`` file with no external assets or dependencies: an
anchor nav, summary cards, the full schedules, and a computed-NRI ownership
table whose totals are reconciled in Python (exact rational math). Derived
values follow the same rules as the workbook -- UNKNOWN stays UNKNOWN, and an
interest is only computed where exact basis language exists.
"""

from __future__ import annotations

import html
from fractions import Fraction
from pathlib import Path
from typing import List, Optional

from .models import TitleReport, UNKNOWN
from . import fractions as fr


def _esc(value) -> str:
    if isinstance(value, list):
        value = "; ".join(str(v) for v in value)
    if isinstance(value, Fraction):
        value = fr.frac_str(value)
    return html.escape("" if value is None else str(value))


def _link(text: str, url: str) -> str:
    if not url or url == UNKNOWN:
        return _esc(text)
    return f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{_esc(text)}</a>'


def _table(headers: List[str], rows: List[List[str]], section_id: str, title: str,
           subtitle: str = "") -> str:
    head = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = ""
    for r in rows:
        body += "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    sub = f'<p class="sub">{_esc(subtitle)}</p>' if subtitle else ""
    return (f'<section id="{section_id}"><h2>{_esc(title)}</h2>{sub}'
            f'<div class="scroll"><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table></div></section>')


def _ownership_rows(rpt: TitleReport):
    rows = []
    nris = []
    minerals = []
    for o in rpt.ownership:
        nri = fr.entry_nri(o.role, o.mineral_interest, o.lease_royalty,
                           o.working_interest, o.burdens, o.override_royalty)
        nris.append(nri)
        if o.role == "royalty":
            minerals.append(o.mineral_interest)
        nma = fr.net_mineral_acres(o.mineral_interest, rpt.config.gross_acres)
        rows.append([
            _esc(o.owner), _esc(o.role), _esc(fr.frac_str(o.mineral_interest)),
            _esc(fr.frac_str(o.lease_royalty)), _esc(fr.frac_str(o.working_interest)),
            _esc(fr.frac_str(o.burdens)), _esc(fr.frac_str(o.override_royalty)),
            _esc(fr.frac_str(nri)), _esc(fr.frac_str(nma) if fr.is_known(nma) else ""),
            _esc(o.basis_language), _esc(o.citation),
        ])
    mtot = fr.total_known(minerals) if minerals and all(fr.is_known(m) for m in minerals) else UNKNOWN
    ntot = fr.total_known(nris) if nris and all(fr.is_known(n) for n in nris) else UNKNOWN
    reconciles = fr.is_known(mtot) and mtot == Fraction(1) and fr.is_known(ntot) and ntot == Fraction(1)
    return rows, mtot, ntot, reconciles


def build_html(rpt: TitleReport, qa_summary: Optional[dict] = None,
               missing: Optional[List[dict]] = None) -> str:
    cfg = rpt.config
    own_rows, mtot, ntot, reconciles = _ownership_rows(rpt)

    banner = ""
    if cfg.data_status != "EXAMINED":
        banner = (f'<div class="banner">DATA STATUS: {_esc(cfg.data_status)} — '
                  "illustrative, internally-consistent title model. NOT an examination of "
                  "record title; no live records pulled.</div>")

    # summary cards
    open_curative = sum(1 for c in rpt.curative if c.status != "Cleared")
    high = sum(1 for c in rpt.curative if c.materiality == "High")
    hbp = "; ".join(f"{w.well_name} ({w.status})" for w in rpt.wells) or "none of record"
    qa_badge = ""
    if qa_summary:
        cls = "ok" if qa_summary["passed"] else "bad"
        qa_badge = f'<span class="badge {cls}">QA {"PASS" if qa_summary["passed"] else "FAIL"}</span>'
    cards = "".join(f'<div class="card"><div class="n">{_esc(n)}</div><div class="l">{_esc(l)}</div></div>'
                    for l, n in [
                        ("Instruments", len(rpt.instruments)),
                        ("Chain links", len(rpt.chain_links)),
                        ("Wells", len(rpt.wells)),
                        ("Curative (open)", open_curative),
                        ("High-materiality", high),
                        ("Ownership rows", len(rpt.ownership)),
                    ])

    recon = ('<span class="badge ok">RECONCILES 8/8 ✓</span>' if reconciles
             else '<span class="badge warn">totals do not reconcile to 8/8</span>')

    # nav
    nav_items = [
        ("summary", "Summary"), ("sources", "Sources"), ("runsheet", "Runsheet"),
        ("abstractions", "Abstractions"), ("chain-min", "Mineral Chain"),
        ("chain-lease", "Leasehold Chain"), ("wells", "Wells/HBP"),
        ("curative", "Curative"), ("ownership", "NRI/WI"), ("qa", "QA"),
    ]
    nav = "".join(f'<a href="#{i}">{_esc(t)}</a>' for i, t in nav_items)

    # sections
    sources = _table(
        ["ID", "Category", "Name", "Portal", "Accessed", "Docs", "Cred?", "Page Ref", "Notes"],
        [[_esc(s.source_id), _esc(s.category), _esc(s.name), _link("Open ↗", s.location),
          _esc(s.accessed_date), _esc(fr.frac_str(s.doc_count)),
          "YES" if s.credential_required else "no", _esc(s.page_ref), _esc(s.notes)]
         for s in rpt.sources],
        "sources", "Source Log")

    runsheet = _table(
        ["Instrument #", "Type", "Book", "Page", "Inst. Date", "Rec. Date",
         "Grantors", "Grantees", "Legal (norm.)", "Class", "Image", "Citation"],
        [[_esc(i.instrument_no), _esc(i.instrument_type), _esc(i.book), _esc(i.page),
          _esc(i.instrument_date), _esc(i.recording_date), _esc(i.grantors), _esc(i.grantees),
          _esc(i.legal_normalized), _esc(i.classification), _link("View ↗", i.image_url),
          _esc(i.citation)] for i in rpt.instruments],
        "runsheet", "Runsheet")

    abstractions = _table(
        ["Instrument #", "Grant", "Reservations", "Royalty/WI", "Pugh/Shut-in",
         "Depth", "Pooling", "Liens", "Conf.", "Review", "Citation"],
        [[_esc(a.instrument_no), _esc(a.grant_clause), _esc(a.reservations),
          _esc(a.royalty_wi_language), _esc(a.pugh_shutin), _esc(a.depth_limits),
          _esc(a.pooling_refs), _esc(a.liens),
          _esc(fr.decimal_str(a.confidence, 2) if isinstance(a.confidence, Fraction) else a.confidence),
          "YES" if a.needs_review else "no", _esc(a.citation)] for a in rpt.abstractions],
        "abstractions", "Instrument Abstractions")

    def _chain(ctype, sid, title):
        return _table(
            ["Seq", "Instrument #", "Date", "Conveyance", "From", "To", "Interest", "Gap"],
            [[_esc(c.seq), _esc(c.instrument_no), _esc(c.date), _esc(c.conveyance),
              _esc(c.from_party), _esc(c.to_party), _esc(c.interest),
              _esc(c.gap_note or "— continuous —")]
             for c in sorted([x for x in rpt.chain_links if x.chain_type == ctype], key=lambda x: x.seq)],
            sid, title)

    chain_min = _chain("mineral_surface", "chain-min", "Chain of Title — Mineral & Surface")
    chain_lease = _chain("leasehold_wi_burdens", "chain-lease", "Chain — Leasehold / WI / Burdens")

    wells = _table(
        ["API #", "Well", "Operator", "Formation", "Spacing", "Pooling",
         "First Prod.", "Status", "HBP", "Citation"],
        [[_esc(w.api_number), _esc(w.well_name), _esc(w.operator), _esc(w.formation),
          _esc(w.spacing_order), _esc(w.pooling_order), _esc(w.first_production),
          _esc(w.status), _esc(w.hbp_support), _esc(w.citation)] for w in rpt.wells],
        "wells", "Wells & Held-By-Production")

    curative = _table(
        ["ID", "Type", "Instrument #", "Description", "Materiality", "Priority",
         "Status", "Recommended Action", "Citation"],
        [[_esc(c.issue_id), _esc(c.issue_type), _esc(c.instrument_no), _esc(c.description),
          f'<span class="mat-{_esc(c.materiality).lower()}">{_esc(c.materiality)}</span>',
          _esc(c.priority), _esc(c.status), _esc(c.recommended_action), _esc(c.citation)]
         for c in rpt.curative],
        "curative", "Encumbrances & Curative")

    own_table = _table(
        ["Owner", "Role", "Mineral", "Royalty", "WI", "Burdens", "ORRI", "NRI",
         "NMA (ac)", "Basis", "Citation"],
        own_rows, "ownership",
        "Net Revenue / Working Interest Matrix",
        subtitle=(f"Total mineral = {fr.frac_str(mtot)} · Total NRI = {fr.frac_str(ntot)}"))

    qa_rows = []
    if qa_summary:
        for c in qa_summary.get("checks", []):
            cls = "ok" if c["status"] == "PASS" else "bad"
            qa_rows.append([_esc(c["name"]), f'<span class="badge {cls}">{_esc(c["status"])}</span>',
                            _esc(c["detail"])])
    qa = _table(["Check", "Result", "Detail"], qa_rows, "qa", "QA Gate Results")

    miss_rows = [[_esc(m.get("item")), _esc(m.get("type")), _esc(m.get("reason")),
                  _esc(m.get("source"))] for m in (missing or [])]
    missing_tbl = _table(["Item", "Type", "Reason", "Source"], miss_rows,
                         "missing", "Missing / Unverified")

    return _TEMPLATE.format(
        title=_esc(f"{cfg.report_type} — {cfg.tract_label}"),
        tract=_esc(cfg.tract_label), report_type=_esc(cfg.report_type),
        report_date=_esc(cfg.report_date), cutoff=_esc(cfg.source_cutoff_date),
        gross=_esc(fr.frac_str(cfg.gross_acres)), prepared_for=_esc(cfg.prepared_for),
        banner=banner, cards=cards, recon=recon, qa_badge=qa_badge, hbp=_esc(hbp),
        nav=nav, sources=sources, runsheet=runsheet, abstractions=abstractions,
        chain_min=chain_min, chain_lease=chain_lease, wells=wells, curative=curative,
        ownership=own_table, qa=qa, missing=missing_tbl,
        assumptions="".join(f"<li>{_esc(a)}</li>" for a in cfg.assumptions),
    )


def write_html(rpt: TitleReport, output_path: str, qa_summary=None, missing=None) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(build_html(rpt, qa_summary, missing), encoding="utf-8")
    return output_path


_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ --ink:#1f2933; --blue:#1f4e79; --line:#d9e2ec; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
        color:var(--ink); background:#f4f6f9; }}
header {{ background:var(--blue); color:#fff; padding:20px 28px; }}
header h1 {{ margin:0 0 4px; font-size:22px; }}
header .meta {{ opacity:.9; font-size:13px; }}
.banner {{ background:#fff3cd; color:#7f6000; font-weight:600; padding:10px 28px;
           border-bottom:1px solid #ffe69c; }}
nav {{ position:sticky; top:0; background:#fff; border-bottom:1px solid var(--line);
       padding:8px 28px; display:flex; gap:14px; flex-wrap:wrap; z-index:5; }}
nav a {{ color:var(--blue); text-decoration:none; font-size:13px; }}
nav a:hover {{ text-decoration:underline; }}
main {{ padding:20px 28px 60px; max-width:1200px; margin:0 auto; }}
.cards {{ display:flex; gap:12px; flex-wrap:wrap; margin:8px 0 20px; }}
.card {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:14px 18px;
         min-width:120px; }}
.card .n {{ font-size:24px; font-weight:700; color:var(--blue); }}
.card .l {{ font-size:12px; color:#52606d; }}
section {{ background:#fff; border:1px solid var(--line); border-radius:8px;
           padding:16px 18px; margin:0 0 18px; }}
section h2 {{ margin:0 0 10px; font-size:16px; color:var(--blue);
              border-bottom:2px solid var(--line); padding-bottom:6px; }}
.sub {{ margin:-4px 0 10px; color:#52606d; font-size:13px; }}
.scroll {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; font-size:13px; }}
th,td {{ border:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }}
th {{ background:var(--blue); color:#fff; position:sticky; top:0; }}
tbody tr:nth-child(even) {{ background:#f8fafc; }}
a {{ color:#0563c1; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:12px; font-weight:600; }}
.badge.ok {{ background:#c6efce; color:#0a6b2d; }}
.badge.bad,.badge.warn {{ background:#ffc7ce; color:#9c0006; }}
.mat-high {{ background:#ff9999; padding:1px 6px; border-radius:4px; }}
.mat-medium {{ background:#ffd580; padding:1px 6px; border-radius:4px; }}
.mat-low {{ background:#c6efce; padding:1px 6px; border-radius:4px; }}
.facts li {{ margin:2px 0; }}
footer {{ color:#7b8794; font-size:12px; padding:0 28px 30px; }}
</style></head>
<body>
<header>
  <h1>{report_type}</h1>
  <div class="meta">{tract} &nbsp;·&nbsp; Report date {report_date} &nbsp;·&nbsp;
       Source cutoff {cutoff} &nbsp;·&nbsp; Gross acres {gross}</div>
</header>
{banner}
<nav>{nav}</nav>
<main>
  <section id="summary"><h2>Summary {qa_badge}</h2>
    <div class="cards">{cards}</div>
    <p><strong>Ownership reconciliation:</strong> {recon}</p>
    <p><strong>HBP / wells:</strong> {hbp}</p>
    <p><strong>Prepared for:</strong> {prepared_for}</p>
    <details><summary>Assumptions &amp; scope</summary><ul class="facts">{assumptions}</ul></details>
  </section>
  {sources}
  {runsheet}
  {abstractions}
  {chain_min}
  {chain_lease}
  {wells}
  {curative}
  {ownership}
  {qa}
  {missing}
</main>
<footer>Generated by the DataBoss Cursory Title Report Engine. Derived interests use exact
rational math; UNKNOWN values are never inferred. Review by a qualified professional required.</footer>
</body></html>"""
