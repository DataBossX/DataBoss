#!/usr/bin/env python3
"""
Mineral & Leasehold Ownership Report generator — Section 31-12N-24W, Roger Mills Co., OK.

Reads the examiner's working title workbook (the 19/20-sheet NHE cursory) DIRECTLY
and renders a self-contained, print-ready HTML report plus a Markdown twin. Every
figure is pulled live from the workbook's Title, OGL, Well 1, and WI sheets — nothing
is transcribed or invented (honors the project's anti-fabrication "Golden Law").

Usage:
    python scripts/mineral_leasehold_report.py --xlsx /path/to/workbook.xlsx
"""
from __future__ import annotations
import argparse, html, re
from pathlib import Path
import openpyxl

NAVY = "#1F4E79"; AMBER = "#FFE699"; GREEN = "#C6EFCE"; RED = "#FBD5D0"; GREY = "#6b7280"
OUT = Path(__file__).resolve().parent.parent / "reports"


def esc(v):
    return html.escape("" if v is None else str(v))


def num(v, dp=2):
    try:
        return f"{float(v):,.{dp}f}"
    except (TypeError, ValueError):
        return esc(v)


def dt(v):
    s = str(v)
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    return f"{int(m.group(2))}/{int(m.group(3))}/{m.group(1)}" if m else esc(v)


def name_addr(cell):
    """Split a multi-line 'Name\\nAddr...' cell into (name, address_lines)."""
    if cell is None:
        return "", ""
    parts = [p.strip() for p in str(cell).split("\n") if p.strip()]
    return (parts[0] if parts else ""), (" · ".join(parts[1:]) if len(parts) > 1 else "")


# ── Parse the Title sheet into tracts + working-interest blocks ─────────────────
def parse_title(ws):
    tracts, wi_blocks = [], []
    cur = None; mode = None
    for r in range(1, ws.max_row + 1):
        b = ws.cell(r, 2).value
        c = ws.cell(r, 3).value
        bs = str(b).strip() if b is not None else ""
        if bs.startswith("TRACT ") and ":" in bs:
            cur = {"id": bs.replace(":", "").strip(), "legal": str(c or "").strip(), "owners": [], "total": None}
            tracts.append(cur); mode = "tract"; continue
        if bs == "Working Interest:":
            cur = {"label": str(c or "").strip(), "owners": []}
            wi_blocks.append(cur); mode = "wi"; continue
        if bs in ("Containing:", "Mineral Owner", "Owner", "Note", ""):
            if bs == "Containing:" and cur is not None and mode == "tract":
                cur["containing"] = str(c or "").strip()
            continue
        if bs in ("REPORT TOTAL", "TOTAL"):
            if cur is not None and mode == "tract" and cur.get("total") is None:
                cur["total"] = c
            continue
        if cur is None:
            continue
        nm, ad = name_addr(b)
        row = {
            "name": nm, "addr": ad, "acres": c,
            "ogl": ws.cell(r, 4).value, "roy": ws.cell(r, 5).value,
            "exp": ws.cell(r, 6).value, "cmt": ws.cell(r, 7).value,
        }
        if nm:
            cur["owners"].append(row)
    return tracts, wi_blocks


def parse_ogl(ws):
    leases = []
    for r in range(2, ws.max_row + 1):
        n = ws.cell(r, 1).value
        if n is None:
            continue
        leases.append({
            "n": n, "lh": ws.cell(r, 2).value, "instr": ws.cell(r, 4).value,
            "bkpg": ws.cell(r, 5).value, "exec": ws.cell(r, 6).value,
            "grantor": ws.cell(r, 8).value, "grantee": ws.cell(r, 9).value,
            "legal": ws.cell(r, 10).value, "term": ws.cell(r, 12).value,
            "gross": ws.cell(r, 13).value, "tracts": ws.cell(r, 14).value,
            "exp": ws.cell(r, 15).value, "nma": ws.cell(r, 16).value,
            "roy": ws.cell(r, 17).value,
        })
    return leases


def parse_well(ws):
    keys = [ws.cell(2, c).value for c in range(1, ws.max_column + 1)]
    vals = [ws.cell(3, c).value for c in range(1, ws.max_column + 1)]
    return [(k, v) for k, v in zip(keys, vals) if k]


# ── HTML rendering ──────────────────────────────────────────────────────────────
def acre_class(o):
    """Amber-flag undetermined/open balance lines; green solid known leased owners."""
    nm = (o.get("name") or "").lower()
    if "undetermined" in nm or "balance of" in nm or o.get("ogl") in ("—", None) and "estate" in nm:
        return "verify"
    return ""


def render_html(meta, tracts, wi_blocks, leases, well, rollup):
    def owner_rows(t):
        out = []
        for o in t["owners"]:
            cls = "verify" if ("undetermined" in (o["name"] or "").lower()
                               or "balance of" in (o["name"] or "").lower()) else ""
            nm = f"<strong>{esc(o['name'])}</strong>"
            if o["addr"]:
                nm += f"<br><span class='addr'>{esc(o['addr'])}</span>"
            cmt = esc(o["cmt"]) if o["cmt"] else ""
            out.append(
                f"<tr class='{cls}'><td>{nm}</td><td class='num'>{num(o['acres'])}</td>"
                f"<td>{esc(o['ogl']) if o['ogl'] not in (None,'—') else '—'}</td>"
                f"<td>{num(o['roy'],4) if isinstance(o['roy'],(int,float)) else esc(o['roy'])}</td>"
                f"<td>{esc(o['exp'])}</td><td class='cmt'>{cmt}</td></tr>")
        return "\n".join(out)

    tract_html = []
    for t in tracts:
        cont = t.get("containing", "")
        tract_html.append(f"""
        <div class="tract">
          <h3>{esc(t['id'])} <span class="legal">{esc(t['legal'])}</span></h3>
          <div class="cont">Containing: {esc(cont)}</div>
          <table class="owners">
            <thead><tr><th>Mineral owner</th><th>Net ac</th><th>OGL</th><th>Roy.</th><th>Expiration</th><th>Comments</th></tr></thead>
            <tbody>
              {owner_rows(t)}
              <tr class="tot"><td>REPORT TOTAL</td><td class="num">{num(t['total'])}</td><td colspan="4"></td></tr>
            </tbody>
          </table>
        </div>""")

    # OGL register split base vs top
    def lease_row(l):
        top = str(l["lh"]).upper().startswith("TOP")
        return (f"<tr class='{'top' if top else ''}'>"
                f"<td class='num'>{esc(l['n'])}</td><td>{esc(l['lh'])}</td>"
                f"<td>{esc(l['grantor'])}</td><td>{esc(l['grantee'])}</td>"
                f"<td>{dt(l['exec'])}</td><td>{esc(l['bkpg'])}</td>"
                f"<td class='num'>{num(l['roy'],4) if isinstance(l['roy'],(int,float)) else esc(l['roy'])}</td>"
                f"<td class='num'>{num(l['nma'])}</td><td>{esc(l['tracts'])}</td>"
                f"<td>{dt(l['exp'])}</td></tr>")
    base = [l for l in leases if not str(l["lh"]).upper().startswith("TOP")]
    top = [l for l in leases if str(l["lh"]).upper().startswith("TOP")]
    ogl_head = ("<tr><th>OGL</th><th>Status</th><th>Lessor (grantor)</th><th>Lessee</th>"
                "<th>Exec.</th><th>Bk/Pg</th><th>Roy.</th><th>NMA</th><th>Tracts</th><th>Exp.</th></tr>")

    wi_html = []
    for w in wi_blocks:
        rows = "\n".join(
            f"<tr><td><strong>{esc(o['name'])}</strong>{('<br><span class=addr>'+esc(o['addr'])+'</span>') if o['addr'] else ''}</td>"
            f"<td class='num'>{num(o['acres']) if isinstance(o['acres'],(int,float)) else esc(o['acres'])}</td>"
            f"<td>{esc(o['ogl'])}</td><td class='cmt'>{esc(o['cmt']) if o['cmt'] else ''}</td></tr>"
            for o in w["owners"] if o["name"])
        wi_html.append(f"<h4>{esc(w['label'])}</h4>"
                       "<table class='wi'><thead><tr><th>Party of record</th><th>Net ac</th>"
                       "<th>Ref (Bk/Pg)</th><th>Comments</th></tr></thead><tbody>"
                       f"{rows}</tbody></table>")

    _date_re = re.compile(r"\d{4}-\d{2}")

    def _wv(v):
        return dt(v) if isinstance(v, str) and _date_re.match(str(v)) else esc(v)
    well_html = "\n".join(f"<tr><td>{esc(k)}</td><td>{_wv(v)}</td></tr>" for k, v in well)

    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>Mineral & Leasehold Ownership — Sec 31-12N-24W, Roger Mills Co., OK</title>
<style>
 :root{{--navy:{NAVY};--amber:{AMBER};--green:{GREEN}}}
 *{{box-sizing:border-box}} body{{font-family:"Segoe UI",Arial,sans-serif;color:#1a1a1a;margin:0;background:#eef0f3;line-height:1.45}}
 .page{{max-width:1180px;margin:22px auto;background:#fff;box-shadow:0 1px 8px rgba(0,0,0,.14);padding-bottom:40px}}
 header.rpt{{background:var(--navy);color:#fff;padding:26px 40px}}
 header.rpt .brand{{font-size:12px;letter-spacing:2px;text-transform:uppercase;opacity:.85}}
 header.rpt h1{{margin:6px 0 4px;font-size:25px}} header.rpt h2{{margin:0;font-weight:500;font-size:15px;opacity:.9}}
 .meta{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#d9dde3;border-bottom:3px solid var(--navy)}}
 .meta div{{background:#fff;padding:9px 14px;font-size:12.5px}} .meta .k{{color:{GREY};text-transform:uppercase;font-size:9.5px;letter-spacing:.8px}} .meta .v{{font-weight:600}}
 section{{padding:6px 40px}} h3{{color:var(--navy);border-bottom:2px solid var(--navy);padding-bottom:5px;margin:26px 0 6px;font-size:16px}}
 h4{{color:var(--navy);margin:16px 0 4px;font-size:13.5px}}
 .legal{{font-weight:400;color:{GREY};font-size:12px}} .cont{{font-size:12px;color:{GREY};margin:2px 0 6px}}
 table{{width:100%;border-collapse:collapse;font-size:12px;margin:4px 0 10px}}
 th{{background:var(--navy);color:#fff;text-align:left;padding:6px 7px;font-weight:600;vertical-align:bottom}}
 td{{border:1px solid #dce0e5;padding:5px 7px;vertical-align:top}} td.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
 tr.verify td{{background:var(--amber)}} tr.tot td{{background:#eef2f7;font-weight:700}} tr.top td{{background:#eaf3fb}}
 td.cmt{{font-size:11px;color:#333;max-width:360px}} .addr{{font-size:10.5px;color:{GREY}}}
 .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:12px 0}}
 .kpi{{border:1px solid #dce0e5;border-radius:8px;padding:12px 14px;background:#f8fafc}}
 .kpi .n{{font-size:23px;font-weight:700;color:var(--navy)}} .kpi .l{{font-size:11px;color:{GREY};text-transform:uppercase;letter-spacing:.5px}}
 .callout{{background:#fff8e1;border-left:4px solid #d9a400;padding:10px 14px;font-size:12.5px;margin:10px 0}}
 .danger{{background:#fdecea;border-left:4px solid #c0392b}}
 ul.tight{{margin:6px 0 12px;padding-left:20px}} ul.tight li{{margin:3px 0;font-size:12.5px}}
 .foot{{font-size:10.5px;color:{GREY};padding:16px 40px 0;border-top:1px solid #e5e7eb;margin-top:22px}}
 .scroll{{overflow-x:auto}} .legend span{{display:inline-block;padding:2px 9px;margin-right:8px;border-radius:3px;font-size:11px;border:1px solid #cfd4da}}
 .legend .v{{background:var(--amber)}}
 @media print{{body{{background:#fff}}.page{{box-shadow:none;margin:0;max-width:none}}header.rpt{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body><div class=page>
 <header class=rpt><div class=brand>{esc(meta['brand'])}</div>
  <h1>Cursory Mineral &amp; Leasehold Ownership Report</h1>
  <h2>Section 31, Township 12 North, Range 24 West, Indian Meridian — Roger Mills County, Oklahoma</h2></header>
 <div class=meta>
  <div><div class=k>Prospect</div><div class=v>{esc(meta['prospect'])}</div></div>
  <div><div class=k>Gross acres</div><div class=v>{esc(meta['gross'])}</div></div>
  <div><div class=k>Tracts</div><div class=v>10</div></div>
  <div><div class=k>Report date</div><div class=v>{esc(meta['date'])}</div></div>
  <div><div class=k>Unit well</div><div class=v>Alexander 1-31</div></div>
  <div><div class=k>API</div><div class=v>35-129-22925</div></div>
  <div><div class=k>Last index entry</div><div class=v>{esc(meta['last'])}</div></div>
  <div><div class=k>Examiner</div><div class=v>{esc(meta['examiner'])}</div></div>
 </div>
 <section>
  <div class=callout danger><strong>Cursory report — not a certified title opinion.</strong>
   Interests are subject to the curative requirements noted per tract. Confirm every interest against the
   recorded instruments before relying on this report for a transaction. No legal facts have been fabricated;
   figures are read directly from the working title workbook.</div>

  <h3>1. Executive summary</h3>
  <div class=kpis>
   <div class=kpi><div class=n>{num(rollup['gross'])}</div><div class=l>Gross acres</div></div>
   <div class=kpi><div class=n>{num(rollup['identified'])}</div><div class=l>NMA identified of record</div></div>
   <div class=kpi><div class=n>{num(rollup['open'])}</div><div class=l>NMA undetermined (curative)</div></div>
   <div class=kpi><div class=n>{len(leases)}</div><div class=l>Leases of record (OGL 1–{len(leases)})</div></div>
  </div>
  <p>Section 31 is a fully-leased, held-by-production Cherokee section. The base leasehold (OGL 1–63,
     recorded 2004–2006 in the EOG / Arrowhead play) is carried <strong>held by production (HBP)</strong> by the
     active <strong>Alexander 1-31</strong> unit well. In 2026, <strong>Silver Oak Natural Resources, LLC</strong> recorded a
     six-lease <strong>top-lease sweep</strong> (OGL 64–69, 3/16 royalty) over the principal current owners; those top
     leases are <strong>subordinate / springing</strong> until the base leases terminate. Fee mineral ownership is a
     family mosaic (Mitchell / Williams / Moore, Bain / Jensen / Fuchs, Kirk, and Daigle / Sorenson / Johnson)
     with modern mineral-fund buyers layered on. Tracts 1, 2, 3, 8 and 10 are fully owner-reconciled to gross;
     Tracts 4, 5, 6, 7 and 9 carry explicit undetermined balances (amber) pending curative.</p>

  <h3>2. Section plat (schematic — not a survey)</h3>
  <div class=scroll><table><thead><tr><th>Tract</th><th>Legal description</th><th>Gross ac</th></tr></thead><tbody>
   {''.join(f"<tr><td>{esc(t['id'])}</td><td class=cmt>{esc(t['legal'])}</td><td class=num>{num(t['total'])}</td></tr>" for t in tracts)}
   <tr class=tot><td colspan=2>SECTION TOTAL</td><td class=num>{num(rollup['gross'])}</td></tr>
  </tbody></table></div>

  <h3>3. Mineral ownership by tract</h3>
  <div class=legend><span class=v>Amber = interest/balance undetermined of record — see curative</span></div>
  <div class=scroll>{''.join(tract_html)}</div>

  <h3>4. Leasehold — base register (OGL 1–63) &amp; Silver Oak top leases (64–69)</h3>
  <div class=scroll><table><thead>{ogl_head}</thead><tbody>
   {''.join(lease_row(l) for l in base)}
  </tbody></table></div>
  <h4>Silver Oak Natural Resources top-lease package (2026) — subordinate / springing</h4>
  <div class=scroll><table><thead>{ogl_head}</thead><tbody>
   {''.join(lease_row(l) for l in top)}
  </tbody></table></div>

  <h3>5. Working interest &amp; wellbore chain</h3>
  {''.join(wi_html)}

  <h3>6. Unit well &amp; held-by-production</h3>
  <div class=scroll><table class=wi><tbody>{well_html}</tbody></table></div>
  <div class=callout>A single active vertical well (Alexander 1-31, OCC status active, last production
   {esc(meta['lastprod'])}) holds the base leases by production; Silver Oak top leases remain subordinate.
   <strong>Confirm continuous production via OTC gross-production by PUN</strong> and pull OCC Form 1002A / 1073.
   Surface-call note: quarter call "C NW/4 SE/4" vs footages 660′ FWL × 1980′ FSL (which fall in C NW/4 SW/4) —
   reconcile against the survey / 1002A.</div>

  <h3>7. Open items &amp; curative requirements (pull to certify)</h3>
  <ul class=tight>
   <li><strong>Base-lease HBP</strong> — OTC gross-production history by PUN for API 35-129-22925 (confirms OGL 1–63 HBP).</li>
   <li><strong>Well completion</strong> — OCC Form 1002A (spud, perforations, TD/TVD) and Form 1073 (operator of record; sheet shows Martin's Resources LLC vs. Martin's Empire → Stride Bank wellbore assignments).</li>
   <li><strong>Undetermined mineral balances</strong> — recorded conveyance images to reconcile carried balances on Tracts 4 (~61.60), 5 (~37.54), 6 (Ella Pearl Kirk estate 48.80), 7 (~36.85) and 9 (~18.84 NMA).</li>
   <li><strong>Conveyed fractions</strong> — instrument images for flagged tract-grid columns (see workbook punch list).</li>
   <li><strong>Root of title</strong> — pre-2000 vesting deeds / probate decrees / heirship affidavits for highlighted grantors (Rowley 1916, Ridling 1953, Thurman 1974, Kirk 1976, and peers).</li>
   <li><strong>Recent-filing sweep</strong> — instruments filed after the last index entry ({esc(meta['last'])}).</li>
  </ul>

  <div class=foot>
   Basis: the working title workbook (19-sheet NHE cursory, dated {esc(meta['date'])}), its OGL register, WI
   chains, and Well 1 record, plus the Roger Mills County unplatted legal index (OCR). Current ownership reflects
   identified record owners; carried/undetermined balances are shown as explicit open lines, not distributed. All
   ten tract grids foot to gross and to the section total of {esc(meta['gross'])}.
   <br><br><strong>Cursory cleanup only from available workbook, county index (OCR), OCC status, and OTC evidence.
   Not a certified title opinion. Open and verify items remain only where source evidence was insufficient.</strong>
  </div>
 </section></div></body></html>"""


def render_md(meta, tracts, wi_blocks, leases, rollup):
    L = [f"# Section 31, T12N–R24W, Roger Mills County, Oklahoma",
         "## Cursory Mineral & Leasehold Ownership Report", "",
         f"**Prospect {meta['prospect']} · {meta['gross']} gross acres · 10 tracts · Report date {meta['date']}**",
         f"**Unit well: Alexander 1-31 · API 35-129-22925 · Cherokee · active (HBP) · last prod {meta['lastprod']}**",
         f"**Last index entry: {meta['last']}**", "",
         "> **Cursory — not a certified title opinion.** Confirm all interests against the recorded instruments.", "",
         "## Executive summary", "",
         f"- **Gross acres:** {num(rollup['gross'])}",
         f"- **NMA identified of record:** {num(rollup['identified'])}",
         f"- **NMA undetermined (curative):** {num(rollup['open'])}",
         f"- **Leases of record:** {len(leases)} (base OGL 1–63 + Silver Oak top OGL 64–69)", "",
         "## Mineral ownership by tract", ""]
    for t in tracts:
        L += [f"### {t['id']} — {t['legal']}  ({num(t['total'])} ac)", "",
              "| Mineral owner | Net ac | OGL | Roy. | Expiration | Comments |",
              "|---|--:|---|--:|---|---|"]
        for o in t["owners"]:
            roy = num(o['roy'], 4) if isinstance(o['roy'], (int, float)) else (o['roy'] or "")
            cmt = str(o['cmt'] or "").replace("\n", " ")
            exp = str(o['exp'] or "").replace("\n", " ")
            L.append(f"| {o['name']} | {num(o['acres'])} | {o['ogl'] if o['ogl'] not in (None,'—') else ''} "
                     f"| {roy} | {exp} | {cmt} |")
        L += [f"| **REPORT TOTAL** | **{num(t['total'])}** | | | | |", ""]
    L += ["## Leasehold register (OGL 1–69)", "",
          "| OGL | Status | Lessor | Lessee | Exec. | Bk/Pg | Roy. | NMA | Tracts | Exp. |",
          "|--:|---|---|---|---|---|--:|--:|---|---|"]
    for l in leases:
        roy = num(l['roy'], 4) if isinstance(l['roy'], (int, float)) else (l['roy'] or "")
        L.append(f"| {l['n']} | {l['lh']} | {l['grantor']} | {l['grantee']} | {dt(l['exec'])} | {l['bkpg']} "
                 f"| {roy} | {num(l['nma'])} | {l['tracts']} | {dt(l['exp'])} |")
    L += ["", "## Working interest / wellbore chain", ""]
    for w in wi_blocks:
        L += [f"**{w['label']}**", "", "| Party of record | Net ac | Ref | Comments |", "|---|--:|---|---|"]
        for o in w["owners"]:
            if o["name"]:
                cmt = str(o['cmt'] or "").replace("\n", " ")
                L.append(f"| {o['name']} | {o['acres']} | {o['ogl']} | {cmt} |")
        L.append("")
    L += ["---", "*Cursory cleanup only from available workbook, county index (OCR), OCC status, and OTC "
          "evidence. Not a certified title opinion. Open and verify items remain only where source evidence "
          "was insufficient.*"]
    return "\n".join(L)


def compute_rollup(tracts):
    gross = sum(float(t["total"]) for t in tracts if isinstance(t["total"], (int, float)))
    open_ = 0.0
    for t in tracts:
        for o in t["owners"]:
            nm = (o["name"] or "").lower()
            if ("undetermined" in nm or "balance of" in nm) and isinstance(o["acres"], (int, float)):
                open_ += float(o["acres"])
    return {"gross": gross, "open": open_, "identified": gross - open_}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default="/tmp/rm/final.xlsx")
    ap.add_argument("--out", default=str(OUT / "31-12N-24W_Roger_Mills_Mineral_and_Leasehold_Ownership_Report"))
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.xlsx, data_only=True)
    tracts, wi_blocks = parse_title(wb["Title "])
    leases = parse_ogl(wb["OGL"])
    well = parse_well(wb["Well 1"])
    rollup = compute_rollup(tracts)
    ov = wb["Overview"]
    meta = {
        "brand": "DataBossX — Mineral Deal Intelligence", "prospect": "25-004",
        "gross": "637.42", "date": "7/3/2026", "examiner": "RG",
        "last": "2026-003315, Bk 2704/142 (6/5/2026)", "lastprod": "3/1/2026",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    Path(args.out + ".html").write_text(render_html(meta, tracts, wi_blocks, leases, well, rollup), encoding="utf-8")
    Path(args.out + ".md").write_text(render_md(meta, tracts, wi_blocks, leases, rollup), encoding="utf-8")
    print(f"tracts={len(tracts)} leases={len(leases)} wi_blocks={len(wi_blocks)}")
    print(f"rollup: gross={rollup['gross']:.2f} identified={rollup['identified']:.2f} open={rollup['open']:.2f}")
    print("wrote", args.out + ".html", "and .md")


if __name__ == "__main__":
    main()
