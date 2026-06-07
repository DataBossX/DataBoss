#!/usr/bin/env python3
"""
DataBoss Landman Report Generator
Section 27-11N-25W, Beckham County, Oklahoma | Client: Diversified | Prospect: 26-005
Run this script to regenerate the HTML report from the source Excel files.
"""

import zipfile
import xml.etree.ElementTree as ET
import json
import os
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

# ── Source files ───────────────────────────────────────────────────────────────
UPLOADS = Path("/root/.claude/uploads/496f911b-2b6f-52cd-95f3-e3f2cbdb83d5")
FILES = {
    "public_context": UPLOADS / "8dddcea9-Diversified_Cherokee_Public_Record_Context_2711N25W_20260607.xlsx",
    "project_notes":  UPLOADS / "11d58466-project_notes_updated.xlsx",
    "shanwee":        UPLOADS / "25355059-11N_23W_10__Shanwee_Cursory__05212026.xlsx",
    "main_report":    UPLOADS / "562eb829-11N_25W_27_Diversified_Cursory_Report_672026.xlsx",
}
OUTPUT = Path("/root/Desktop/Diversified_27-11N-25W_Landman_Report.html")

# ── XLSX reader (pure Python, no openpyxl) ────────────────────────────────────
NS = {'ss': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def col_num(col):
    n = 0
    for c in col.upper():
        n = n * 26 + ord(c) - 64
    return n - 1

def parse_ref(ref):
    import re
    m = re.match(r'([A-Za-z]+)(\d+)', ref)
    return (col_num(m.group(1)), int(m.group(2)) - 1) if m else (0, 0)

def shared_strings(zf):
    try:
        with zf.open('xl/sharedStrings.xml') as f:
            root = ET.parse(f).getroot()
        return [''.join(t.text or '' for t in si.findall('.//ss:t', NS))
                for si in root.findall('.//ss:si', NS)]
    except KeyError:
        return []

def read_sheet(zf, path, ss):
    with zf.open(path) as f:
        root = ET.parse(f).getroot()
    cells = {}
    for row in root.findall('.//ss:row', NS):
        for c in row.findall('ss:c', NS):
            ci, ri = parse_ref(c.get('r', ''))
            v = c.find('ss:v', NS)
            if v is None:
                continue
            val = v.text or ''
            if c.get('t') == 's':
                try:
                    val = ss[int(val)]
                except (IndexError, ValueError):
                    pass
            cells.setdefault(ri, {})[ci] = val
    if not cells:
        return []
    mr, mc = max(cells), max(max(r.keys()) for r in cells.values())
    return [[cells.get(r, {}).get(c, '') for c in range(mc + 1)] for r in range(mr + 1)]

def load_workbook(path):
    sheets = {}
    with zipfile.ZipFile(path) as zf:
        ss = shared_strings(zf)
        try:
            with zf.open('xl/workbook.xml') as f:
                wb = ET.parse(f).getroot()
            names = [s.get('name', f'Sheet{i}') for i, s in
                     enumerate(wb.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet'))]
        except Exception:
            names = []
        sfiles = sorted(n for n in zf.namelist() if n.startswith('xl/worksheets/sheet') and n.endswith('.xml'))
        for i, sf in enumerate(sfiles):
            name = names[i] if i < len(names) else sf
            sheets[name] = read_sheet(zf, sf, ss)
    return sheets

def xdate(n):
    """Convert Excel serial date to YYYY-MM-DD string."""
    if not n:
        return ''
    try:
        v = int(float(str(n).replace(',', '')))
        if v < 1000:
            return str(n)
        return (datetime(1899, 12, 30) + timedelta(days=v)).strftime('%Y-%m-%d')
    except Exception:
        return str(n)

def rows_to_dicts(rows, header_row=0):
    if not rows or header_row >= len(rows):
        return []
    headers = [str(h).strip() for h in rows[header_row]]
    result = []
    for row in rows[header_row + 1:]:
        if not any(v for v in row):
            continue
        d = {}
        for i, h in enumerate(headers):
            d[h] = str(row[i]).strip() if i < len(row) else ''
        result.append(d)
    return result

# ── Load all data ─────────────────────────────────────────────────────────────
print("Reading Excel files...")
MAIN  = load_workbook(FILES["main_report"])
CTX   = load_workbook(FILES["public_context"])

# Main report sheets
runsheet   = rows_to_dicts(MAIN.get('Runsheet', MAIN.get('RS', [])))
runsheet2  = rows_to_dicts(MAIN.get('runsheet2', []))
ogls       = rows_to_dicts(MAIN.get('diversified', []))
ogls_need  = rows_to_dicts(MAIN.get('needed', []))
chain_fp   = rows_to_dicts(MAIN.get('WI 1', []))
chain_dp   = rows_to_dicts(MAIN.get('DP Legacy', []))
wells_main = rows_to_dicts(MAIN.get('Wells', []))
lh         = rows_to_dicts(MAIN.get('LH', []))
tract3_rows = MAIN.get('Tract 3', [])
chain_legacy = rows_to_dicts(MAIN.get('chainlegacy', []))
index_all    = rows_to_dicts(MAIN.get('Index', []))
needed_items = rows_to_dicts(MAIN.get('notes 3', []))

# Public context sheets
wells_occ  = rows_to_dicts(CTX.get('OCC RBDMS Wells', []))
completions = rows_to_dicts(CTX.get('OCC Completion Data', []))
orders      = rows_to_dicts(CTX.get('OCC Order Watchlist', []))
vq          = rows_to_dicts(CTX.get('Verification Queue', []))
sources     = rows_to_dicts(CTX.get('Source Register', []))

# Extract leasehold chain summary from Tract 3
tract3_summary = []
for row in tract3_rows:
    if any(v for v in row[:4]):
        tract3_summary.append([str(v)[:120] for v in row[:5]])

print(f"  Runsheet: {len(runsheet)} instruments")
print(f"  OGL Leases: {len(ogls)}")
print(f"  FourPoint chain: {len(chain_fp)}")
print(f"  DP Legacy chain: {len(chain_dp)}")
print(f"  OCC Wells: {len(wells_occ)}")
print(f"  Needed items: {len(needed_items)}")

# ── Helpers for HTML ──────────────────────────────────────────────────────────
def esc(s):
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

def badge(text, cls='badge-blue'):
    return f'<span class="badge {cls}">{esc(text)}</span>'

def status_badge(s):
    s = str(s).strip().upper()
    if 'AC' in s or 'ACTIVE' in s:
        return badge('ACTIVE','badge-green')
    if 'PA' in s or 'PLUGGED' in s:
        return badge('PLUGGED','badge-red')
    if 'HBP' in s:
        return badge('HBP','badge-orange')
    if 'UNVERIFIED' in s:
        return badge('UNVERIFIED','badge-yellow')
    if 'P1' in s:
        return badge('P1 NEEDED','badge-red')
    return badge(s,'badge-gray') if s else ''

def table(headers, rows, cls=''):
    if not rows:
        return '<p class="empty">No data</p>'
    h = ''.join(f'<th>{esc(h)}</th>' for h in headers)
    body = ''
    for r in rows:
        cells = ''.join(f'<td>{esc(str(v))}</td>' for v in r)
        body += f'<tr>{cells}</tr>'
    return f'<div class="tbl-wrap"><table class="tbl {cls}"><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table></div>'

def rs_table(rows):
    if not rows:
        return '<p class="empty">No run sheet data</p>'
    h = ['County','Instrument','Recorded','Type','Book/Page','Grantor','Grantee','Legal Description']
    body = ''
    for r in rows:
        county   = r.get('County','')
        inst     = r.get('Instrument', r.get('Instrument #',''))
        rec      = xdate(r.get('Recorded', r.get('Rec. Date','')))
        itype    = r.get('Type', r.get('Instrument Type',''))
        book     = r.get('Book','')
        page     = r.get('Page(s)', r.get('Page',''))
        bp       = f"{book}/{page}" if book or page else ''
        grantor  = r.get('Grantor', r.get('Grantors',''))
        grantee  = r.get('Grantee', r.get('Grantees',''))
        legal    = r.get('Legal Description','')[:80]
        row_cls  = 'row-highlight' if any(k in itype.upper() for k in ['ASSIGN','CONVEY','DEED']) else ''
        cells = ''.join(f'<td>{esc(v)}</td>' for v in [county,inst,rec,itype,bp,grantor,grantee,legal])
        body += f'<tr class="{row_cls}">{cells}</tr>'
    cols = ''.join(f'<th>{h}</th>' for h in h)
    return f'<div class="tbl-wrap"><table class="tbl"><thead><tr>{cols}</tr></thead><tbody>{body}</tbody></table></div>'

# ── Build HTML sections ───────────────────────────────────────────────────────
TODAY = datetime.today().strftime('%B %d, %Y')

# Chain summary text
chain_summary_rows = [r for r in tract3_summary if len(r) >= 2 and r[0] and r[0] not in ('Track/Type','Leasehold Summary')]
chain_html = ''
for row in chain_summary_rows[:20]:
    track = esc(row[0])
    result = esc(row[1]) if len(row) > 1 else ''
    support = esc(row[2]) if len(row) > 2 else ''
    reliance = esc(row[3]) if len(row) > 3 else ''
    chain_html += f'<tr><td><strong>{track}</strong></td><td>{result}</td><td>{support}</td><td>{reliance}</td></tr>'

# FourPoint chain table
fp_rows = []
for r in chain_fp:
    d = xdate(r.get('Date',''))
    inst = r.get('Instrument / Source','')
    itype = r.get('Instrument Type','')
    bp = r.get('Book/Page','')
    g_from = r.get('Grantor / From','')
    g_to   = r.get('Grantee / To','')
    fn     = r.get('Chain Function','')[:80]
    conf   = r.get('Confidence','')[:60]
    fp_rows.append([d, inst, itype, bp, g_from, g_to, fn, conf])

# DP Legacy chain table
dp_rows = []
for r in chain_dp:
    flag = r.get('Interest Flag','')
    inst = r.get('Instrument','')
    bkpg = r.get('Bk/Pg.','')
    rec  = xdate(r.get('Recorded Date',''))
    itype= r.get('Doc Type','')
    parties = r.get('Parties','')[:80]
    effect  = r.get('Effect / Next Move','')[:80]
    dp_rows.append([flag[:40], inst, bkpg, rec, itype, parties, effect])

# Leasehold chain table
lh_rows = []
for r in lh:
    track = r.get('Track/Type','')
    inst  = r.get('Instrument','')
    bp    = r.get('Book/Page','')
    rec   = xdate(r.get('Recorded Date',''))
    itype = r.get('Doc Type','')
    parties = r.get('Parties','')[:70]
    effect  = r.get('Report Effect','')[:70]
    status  = r.get('Status / Next Step','')[:60]
    lh_rows.append([track, inst, bp, rec, itype, parties, effect, status])

# Needed items (P1 only first)
p1_needed = [r for r in needed_items if str(r.get('Priority','')).upper() == 'P1']
p1_rows = []
for r in p1_needed[:50]:
    nid   = r.get('Need ID','')
    cat   = r.get('Category','')
    inst  = r.get('Document / Target', r.get('Instrument #',''))
    bp    = r.get('Book/Page','')
    rec   = xdate(r.get('Recorded',''))
    gran  = r.get('Grantor / Lessor','')
    gran2 = r.get('Grantee / Lessee','')
    action= r.get('Next Action','')[:80]
    p1_rows.append([nid, cat, inst, bp, rec, gran, gran2, action])

# Verification queue from File 1
vq_rows = [[r.get('Priority',''), r.get('Required Action','')[:100], r.get('Why It Matters','')[:100]] for r in vq]

# OGL needs
ogl_need_rows = []
for r in ogls_need[:30]:
    ogl_no = r.get('OGL #','')
    inst   = r.get('Instrument','')
    bp     = r.get('Bk./Pg.','')
    exec_d = xdate(r.get('Execution\nDate', r.get('Execution Date','')))
    file_d = xdate(r.get('Filing\nDate', r.get('Filing Date','')))
    grantor = r.get('Grantor','')
    grantee = r.get('Grantee','')
    legal   = r.get('Legal\nDescription', r.get('Legal Description',''))
    term    = r.get('Term','')
    acres   = r.get('Gross Acres','')
    ogl_need_rows.append([ogl_no, inst, bp, exec_d, file_d, grantor, grantee, legal, term, acres])

# Source register
src_rows = [[r.get('Exact Source Name','')[:60], r.get('Source Type',''), r.get('Used For','')[:80], r.get('Reliability',''), r.get('Date Accessed','')] for r in sources[:15]]

# Active wells count
active_wells = sum(1 for w in wells_occ if 'AC' in str(w.get('Status','')).upper())
total_wells  = len(wells_occ)

# Pre-compute well cards HTML (can't use join inside f-string)
well_cards_html = ''
for w in wells_occ:
    well_cards_html += f"""
  <div class="summary-box" style="margin-bottom:12px">
    <strong>{esc(w.get('Well Name',''))} {esc(w.get('Well No.',''))}</strong>
    &nbsp;{status_badge(w.get('Status',''))}&nbsp;{badge(w.get('Well Type',''),'badge-blue')}
    <br><span style="color:var(--gray);font-size:12px">
      API: {esc(w.get('API',''))} &nbsp;|&nbsp;
      Operator: {esc(w.get('Operator',''))} &nbsp;|&nbsp;
      Sec {esc(w.get('Section',''))} {esc(w.get('Township',''))} {esc(w.get('Range',''))} &nbsp;|&nbsp;
      County: {esc(w.get('County',''))}
    </span>
  </div>"""

# Pre-compute claim log HTML
claim_log_rows = [[r.get('ID',''), r.get('Research Area',''), r.get('Exact Source Name','')[:50],
                   r.get('Confidence','')[:60], r.get('Workbook Treatment','')[:60]]
                  for r in rows_to_dicts(CTX.get('Claim Log',[]))]

# ── Generate full HTML ────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Landman Cursory Report – Section 27-11N-25W – Beckham County, OK</title>
<style>
:root {{
  --navy: #0f2d52;
  --blue: #1a5276;
  --ltblue: #2e86c1;
  --accent: #f39c12;
  --green: #1e8449;
  --red: #c0392b;
  --orange: #d35400;
  --gray: #566573;
  --ltgray: #f2f3f4;
  --white: #fff;
  --border: #d5d8dc;
  --text: #1c2833;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #eaf0fb; color: var(--text); font-size: 13px; }}
a {{ color: var(--ltblue); }}

/* ── Header ── */
.report-header {{
  background: linear-gradient(135deg, var(--navy) 0%, var(--blue) 100%);
  color: var(--white); padding: 28px 36px 20px;
}}
.report-header h1 {{ font-size: 22px; font-weight: 700; letter-spacing: .5px; }}
.report-header .subtitle {{ font-size: 14px; opacity: .85; margin-top: 4px; }}
.meta-grid {{ display: flex; flex-wrap: wrap; gap: 24px; margin-top: 18px; }}
.meta-item {{ }}
.meta-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 1px; opacity: .65; }}
.meta-value {{ font-size: 14px; font-weight: 600; margin-top: 2px; }}
.disclaimer {{
  background: #fff3cd; border-left: 4px solid #f39c12;
  padding: 10px 16px; font-size: 12px; color: #856404;
  margin: 0; border-radius: 0;
}}

/* ── Tabs ── */
.tab-bar {{
  background: var(--navy); padding: 0 28px;
  display: flex; gap: 2px; overflow-x: auto;
}}
.tab-btn {{
  background: none; border: none; color: rgba(255,255,255,.65);
  padding: 12px 18px; cursor: pointer; font-size: 12.5px; font-weight: 600;
  letter-spacing: .3px; border-bottom: 3px solid transparent;
  white-space: nowrap; transition: all .15s;
}}
.tab-btn:hover {{ color: var(--white); }}
.tab-btn.active {{ color: var(--white); border-bottom-color: var(--accent); }}

/* ── Content ── */
.tab-content {{ display: none; padding: 24px 28px 40px; }}
.tab-content.active {{ display: block; }}

/* ── Cards ── */
.card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px,1fr)); gap: 16px; margin-bottom: 24px; }}
.card {{
  background: var(--white); border-radius: 8px; padding: 18px 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,.08); border-left: 4px solid var(--ltblue);
}}
.card.warn {{ border-left-color: var(--accent); }}
.card.danger {{ border-left-color: var(--red); }}
.card.ok {{ border-left-color: var(--green); }}
.card-number {{ font-size: 30px; font-weight: 800; color: var(--navy); }}
.card-label {{ font-size: 11px; color: var(--gray); margin-top: 4px; font-weight: 600; text-transform: uppercase; letter-spacing: .5px; }}

/* ── Section headings ── */
.section-title {{
  font-size: 15px; font-weight: 700; color: var(--navy);
  border-bottom: 2px solid var(--ltblue); padding-bottom: 6px; margin: 24px 0 14px;
}}
.section-title:first-child {{ margin-top: 0; }}

/* ── Tables ── */
.tbl-wrap {{ overflow-x: auto; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.07); margin-bottom: 20px; }}
.tbl {{ width: 100%; border-collapse: collapse; background: var(--white); font-size: 12px; }}
.tbl thead tr {{ background: var(--navy); color: var(--white); }}
.tbl th {{ padding: 9px 11px; text-align: left; font-weight: 600; font-size: 11px; letter-spacing: .3px; white-space: nowrap; }}
.tbl tbody tr {{ border-bottom: 1px solid var(--border); }}
.tbl tbody tr:last-child {{ border-bottom: none; }}
.tbl tbody tr:hover {{ background: #eaf4fb; }}
.tbl td {{ padding: 8px 11px; vertical-align: top; }}
.tbl .row-highlight td {{ background: #eaf7f0; }}

/* ── Badges ── */
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; letter-spacing: .4px; }}
.badge-green  {{ background: #d5f5e3; color: var(--green); }}
.badge-red    {{ background: #fadbd8; color: var(--red); }}
.badge-orange {{ background: #fdebd0; color: var(--orange); }}
.badge-yellow {{ background: #fef9e7; color: #7d6608; }}
.badge-blue   {{ background: #d6eaf8; color: var(--ltblue); }}
.badge-gray   {{ background: var(--ltgray); color: var(--gray); }}

/* ── Summary blocks ── */
.summary-box {{
  background: var(--white); border-radius: 8px; padding: 18px 22px;
  box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 20px;
}}
.chain-track {{
  background: var(--ltgray); border-radius: 8px; padding: 14px 18px;
  margin-bottom: 12px; border-left: 4px solid var(--ltblue);
}}
.chain-track.trackA {{ border-left-color: var(--green); }}
.chain-track.trackB {{ border-left-color: var(--orange); }}
.chain-track h4 {{ font-size: 13px; font-weight: 700; margin-bottom: 6px; }}
.chain-track p {{ font-size: 12px; color: var(--gray); line-height: 1.5; }}

/* ── Priority indicator ── */
.p1 {{ color: var(--red); font-weight: 700; }}
.p2 {{ color: var(--orange); font-weight: 600; }}

.empty {{ color: var(--gray); font-style: italic; padding: 16px 0; }}

@media print {{
  .tab-bar {{ display: none; }}
  .tab-content {{ display: block !important; page-break-before: always; }}
  .report-header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
}}
</style>
</head>
<body>

<!-- ═══ HEADER ═══ -->
<div class="report-header">
  <h1>LANDMAN CURSORY REPORT — Section 27, T11N, R25W</h1>
  <div class="subtitle">Beckham County, Oklahoma &nbsp;|&nbsp; Client: Diversified &nbsp;|&nbsp; Prospect: 26-005</div>
  <div class="meta-grid">
    <div class="meta-item"><div class="meta-label">Prepared</div><div class="meta-value">{TODAY}</div></div>
    <div class="meta-item"><div class="meta-label">Total Acres</div><div class="meta-value">640.00</div></div>
    <div class="meta-item"><div class="meta-label">Active Wells</div><div class="meta-value">{active_wells} / {total_wells}</div></div>
    <div class="meta-item"><div class="meta-label">Run Sheet Instruments</div><div class="meta-value">{len(runsheet)}</div></div>
    <div class="meta-item"><div class="meta-label">Base OGL Leases</div><div class="meta-value">{len(ogls)}</div></div>
    <div class="meta-item"><div class="meta-label">Open P1 Requirements</div><div class="meta-value">{len(p1_needed)}</div></div>
  </div>
</div>
<div class="disclaimer">
  ⚠️ CURSORY / APPARENT ONLY — This report is based on public-record context and county index data.
  It is NOT a title opinion. Do not rely for drilling, acquisition, transaction, or financing decisions
  without a full title run and review by a licensed attorney. Images, lease schedules, and production
  records have not been verified.
</div>

<!-- ═══ TABS ═══ -->
<div class="tab-bar">
  <button class="tab-btn active" onclick="showTab('exec')">Executive Summary</button>
  <button class="tab-btn" onclick="showTab('wells')">Wells (OCC)</button>
  <button class="tab-btn" onclick="showTab('runsheet')">Run Sheet</button>
  <button class="tab-btn" onclick="showTab('ogls')">OGL Leases</button>
  <button class="tab-btn" onclick="showTab('chain')">Chain of Title</button>
  <button class="tab-btn" onclick="showTab('needed')">Open Requirements</button>
  <button class="tab-btn" onclick="showTab('recent')">Recent Instruments</button>
  <button class="tab-btn" onclick="showTab('sources')">Public Record Context</button>
</div>

<!-- ═══ TAB 1: EXECUTIVE SUMMARY ═══ -->
<div id="tab-exec" class="tab-content active">
  <div class="card-grid">
    <div class="card ok"><div class="card-number">{active_wells}</div><div class="card-label">Active Wells (OCC)</div></div>
    <div class="card"><div class="card-number">{len(runsheet)}</div><div class="card-label">Run Sheet Instruments</div></div>
    <div class="card"><div class="card-number">{len(ogls)}</div><div class="card-label">Base OGL Leases</div></div>
    <div class="card warn"><div class="card-number">{len(p1_needed)}</div><div class="card-label">P1 Open Requirements</div></div>
    <div class="card"><div class="card-number">{len(chain_fp)}</div><div class="card-label">FourPoint Chain Links</div></div>
    <div class="card"><div class="card-number">{len(chain_dp)}</div><div class="card-label">DP Legacy Chain Links</div></div>
  </div>

  <div class="section-title">Subject Legal</div>
  <div class="summary-box">
    <strong>Section 27, Township 11 North, Range 25 West (27-11N-25W)</strong><br>
    Beckham County, Oklahoma &nbsp;|&nbsp; Indian Meridian (IM) &nbsp;|&nbsp; 640.00 acres, more or less
  </div>

  <div class="section-title">Apparent Diversified Leasehold Chain — Summary</div>
  <div class="chain-track trackA">
    <h4>Track A — FourPoint / Maverick / Diversified Energy</h4>
    <p>Diversified appears to hold a successor leasehold interest via corporate acquisition chain:
    Nadel &amp; Gussman → FourPoint Energy (Instr. 2017-004597, 2019-002937, 2019-002988) →
    Maverick Natural Resources (corporate acquisition) → Diversified Energy Company PLC (completed acquisition ~2025).
    County-recorded assignments confirm FourPoint entries. Corporate-level transfers not recorded at county.
    <br><strong>Reliance:</strong> Cursory / apparent only. Image review and schedule reconciliation required.</p>
  </div>
  <div class="chain-track trackB">
    <h4>Track B — DP Legacy / Tapstone / Diversified Production</h4>
    <p>Diversified may also hold a separate leasehold chain: Chesapeake entities → KL CHK SPV / Diversified
    Production (2022-000152) → DP Legacy Central (merger 2022-003506) → DP Legacy Tapstone →
    DP Sooner Holdco → Diversified Production, LLC (conveyance 2023-000796 / Book 24/551).
    Schedule-heavy instruments; legal descriptions not confirmed on all index entries.
    <br><strong>Reliance:</strong> Possible / unresolved. Full image review required.</p>
  </div>

  <div class="section-title">OGL Lease Base</div>
  <div class="summary-box">
    <strong>{len(ogls)} base oil and gas leases</strong> cover Section 27-11N-25W.
    Index only — primary terms, royalty fractions, expiration dates, and HBP status require image verification.
    All OGLs executed with Sanguine Ltd. as lessee (~2001). Pooling/unit affidavit recorded (Bk 1626/107-119, 2000).
    Lease images are a <span class="p1">P1 requirement</span> before any title reliance.
  </div>

  <div class="section-title">OCC / HBP Status</div>
  <div class="summary-box">
    OCC RBDMS identifies <strong>{active_wells} active wells</strong> in Section 27-11N-25W:
    MANDRELL #2-27 (AC/Gas), BETTY SITES #1-27 (AC/Gas), and SITES #1H-2215 (AC/Oil, horizontal).
    MANDRELL #1-27 is plugged (PA). Active well status is consistent with HBP; however,
    lease-by-lease production tie-in and OTC production history verification are required.
    OCC order images for pooling/spacing orders 147147, 212526, 677424, and 688488 must be reviewed.
  </div>

  <div class="section-title">Key Open Requirements (P1)</div>
  <ul style="margin-left:20px;line-height:2">
    <li><span class="p1">P1</span> — Pull and abstract all {len(ogls)} base OGL lease images (confirm terms, HBP, parties)</li>
    <li><span class="p1">P1</span> — Verify OCC orders 147147, 212526, 677424, 688488 (spacing/pooling)</li>
    <li><span class="p1">P1</span> — Pull OTC production history; tie production to each lease and unit</li>
    <li><span class="p1">P1</span> — Pull assignment chain images: 28 intermediate assignments (1999–2002)</li>
    <li><span class="p1">P1</span> — Confirm Track A: FourPoint assignment exhibits match subject legal</li>
    <li><span class="p1">P1</span> — Confirm Track B: DP Legacy/Tapstone conveyance schedules include subject section</li>
    <li><span class="p1">P1</span> — Re-run BLM/GLO patent/plat search when maintenance ends</li>
  </ul>
</div>

<!-- ═══ TAB 2: WELLS ═══ -->
<div id="tab-wells" class="tab-content">
  <div class="section-title">OCC RBDMS Well Records — Section 27-11N-25W, Beckham County</div>
  {well_cards_html}

  <div class="section-title">OCC Completion Data</div>
  {table(
    ['API','Well','Operator','Status','Type','Surface Location','Spud','Completion'],
    [[r.get('API',''), r.get('Well',''), r.get('Operator / No.','')[:40],
      r.get('Status',''), r.get('Type / Class',''), r.get('Location','')[:50],
      xdate(r.get('Spud','')), xdate(r.get('Completion',''))] for r in completions]
  )}

  <div class="section-title">OCC Order Watchlist (Requires Image Review)</div>
  {table(
    ['Order/Case','Linked Well(s)','Confidence','Required Follow-Up','Treatment'],
    [[r.get('Order / Case Reference',''), r.get('Linked Well(s)',''), r.get('Confidence','')[:60],
      r.get('Required Follow-Up','')[:80], r.get('Treatment','')[:60]] for r in orders]
  )}
</div>

<!-- ═══ TAB 3: RUN SHEET ═══ -->
<div id="tab-runsheet" class="tab-content">
  <div class="section-title">Full Run Sheet — All Instruments Affecting Section 27-11N-25W
    <span style="font-weight:400;color:var(--gray);font-size:12px"> ({len(runsheet)} instruments — index only, images not verified)</span>
  </div>
  {rs_table(runsheet)}
</div>

<!-- ═══ TAB 4: OGL LEASES ═══ -->
<div id="tab-ogls" class="tab-content">
  <div class="section-title">Base Oil and Gas Leases — {len(ogls)} Leases (Index / Cursory Only)</div>
  <div class="summary-box" style="margin-bottom:16px">
    All {len(ogls)} leases were executed with <strong>Sanguine Ltd.</strong> as lessee (~October 2001).
    Gross leases cover 640 acres (Section 27-11N-25W). HBP status is <strong>unverified</strong> — image review
    and production tie-in required for all leases before reliance.
  </div>
  {table(
    ['OGL#','Instrument','Book/Page','Grantor/Lessor','Lessee','Legal Desc','Gross Acres','Coverage','Exec Date','Filed'],
    [[r.get('OGL #',''), r.get('Instrument #',''), r.get('Book/Page',''),
      r.get('Grantor/Lessor','')[:35], r.get('Grantee/Lessee',''),
      r.get('Legal Description','')[:30], r.get('Gross Acres',''), r.get('Tract Coverage',''),
      xdate(r.get('Execution Date','')), xdate(r.get('Filing/Recording Date',''))] for r in ogls[:64]]
  )}

  <div class="section-title">OGL Needs — Images &amp; Abstractions Required</div>
  {table(
    ['OGL#','Instrument','Book/Pg','Exec Date','Filed Date','Grantor','Grantee','Legal','Term','Acres'],
    ogl_need_rows
  )}
</div>

<!-- ═══ TAB 5: CHAIN OF TITLE ═══ -->
<div id="tab-chain" class="tab-content">
  <div class="section-title">Leasehold Chain Summary</div>
  <div class="tbl-wrap">
    <table class="tbl">
      <thead><tr><th>Track/Type</th><th>Apparent Result</th><th>Key Support</th><th>Reliance Level</th></tr></thead>
      <tbody>{chain_html}</tbody>
    </table>
  </div>

  <div class="section-title">Track A — FourPoint / Maverick / Diversified</div>
  {table(
    ['Date','Instrument','Type','Book/Page','From','To','Chain Function','Confidence'],
    fp_rows
  )}

  <div class="section-title">Track B — DP Legacy / Tapstone / Diversified Production</div>
  {table(
    ['Interest Flag','Instrument','Bk/Pg','Recorded','Type','Parties','Effect / Next Move'],
    dp_rows
  )}

  <div class="section-title">Leasehold Chain — Full Instrument List</div>
  {table(
    ['Track/Type','Instrument','Book/Page','Recorded','Type','Parties','Report Effect','Status'],
    lh_rows
  )}

  <div class="section-title">Mineral / Title Support Chain (chainlegacy)</div>
  {table(
    ['County','Recorded','Instrument','Type','Book/Page','Grantor','Grantee','Legal'],
    [[r.get('County',''), xdate(r.get('Recorded','')), r.get('Instrument',''),
      r.get('Type',''), f"{r.get('Book','')}/{r.get('Page(s)','')}",
      r.get('Grantor','')[:40], r.get('Grantee','')[:40],
      r.get('Legal Description',r.get('Legal / Scope',''))[:40]] for r in chain_legacy[:50]]
  )}
</div>

<!-- ═══ TAB 6: OPEN REQUIREMENTS ═══ -->
<div id="tab-needed" class="tab-content">
  <div class="card-grid">
    <div class="card danger"><div class="card-number">{len(p1_needed)}</div><div class="card-label">P1 Priority Items</div></div>
    <div class="card warn"><div class="card-number">{len(needed_items) - len(p1_needed)}</div><div class="card-label">Other Needed Items</div></div>
    <div class="card"><div class="card-number">{len(vq)}</div><div class="card-label">Verification Queue</div></div>
  </div>

  <div class="section-title">P1 Priority Requirements — Needed Before Title Reliance</div>
  {table(
    ['Need ID','Category','Document / Target','Book/Page','Recorded','Grantor','Grantee','Required Action'],
    p1_rows
  )}

  <div class="section-title">Verification Queue (from Public Record Context)</div>
  {table(['Priority','Required Action','Why It Matters'], vq_rows)}
</div>

<!-- ═══ TAB 7: RECENT INSTRUMENTS ═══ -->
<div id="tab-recent" class="tab-content">
  <div class="section-title">Recent Instruments (2022–2026) — Beckham County Index</div>
  {table(
    ['County','Recorded','Instrument','Type','Book/Page','Grantor','Grantee','Images'],
    [[r.get('County',''), xdate(r.get('Recorded','')), r.get('Instrument',''),
      r.get('Type',''), f"{r.get('Book','')}/{r.get('Page(s)','')}",
      r.get('Grantor','')[:40], r.get('Grantee','')[:40],
      r.get('Images', r.get('Images',''))[:20]] for r in runsheet2]
  )}
</div>

<!-- ═══ TAB 8: PUBLIC RECORD CONTEXT ═══ -->
<div id="tab-sources" class="tab-content">
  <div class="section-title">Public-Record Context Notes</div>
  <div class="summary-box">
    <strong>Scope:</strong> Official OCC / BLM / GLO sources only. No county recorder images accessed.
    This pass establishes well activity, public land context, and source hierarchy only.
    Cherokee/HBP scope remains unconfirmed from public sources alone.
    Do not treat this public-source pass as a title run.
  </div>

  <div class="section-title">Source Register ({len(sources)} sources)</div>
  {table(['Source Name','Type','Used For','Reliability','Date Accessed'], src_rows)}

  <div class="section-title">Claim Log (Verified Public-Record Claims)</div>
  {table(
    ['ID','Research Area','Source','Confidence','Treatment'],
    claim_log_rows
  )}
</div>

<!-- ═══ FOOTER ═══ -->
<div style="background:var(--navy);color:rgba(255,255,255,.6);padding:16px 28px;font-size:11px;margin-top:24px">
  Generated by DataBoss Landman Report System &nbsp;|&nbsp; {TODAY} &nbsp;|&nbsp;
  Section 27-11N-25W, Beckham County, OK &nbsp;|&nbsp; Client: Diversified &nbsp;|&nbsp;
  <strong style="color:rgba(255,255,255,.85)">NOT A TITLE OPINION — FOR INFORMATIONAL USE ONLY</strong>
</div>

<script>
function showTab(id) {{
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  event.target.classList.add('active');
}}
</script>
</body>
</html>"""

# ── Save and open ─────────────────────────────────────────────────────────────
OUTPUT.write_text(html, encoding='utf-8')
print(f"\n✓ Report saved: {OUTPUT}")
print(f"  Size: {OUTPUT.stat().st_size:,} bytes")

try:
    webbrowser.open(OUTPUT.as_uri())
    print("✓ Opened in browser")
except Exception:
    print("  (Open the file manually in a browser)")

print("\nDone.")
