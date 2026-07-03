# -*- coding: utf-8 -*-
import data as D, datetime, openpyxl
M=D.META
wb=openpyxl.load_workbook('source2/NHE_7-3-26.xlsx',data_only=True); ws=wb['OGL']
def dt(v): return v.strftime('%-m/%-d/%Y') if isinstance(v,datetime.datetime) else (v or '')
def royf(v):
    try:return {0.1875:'3/16',0.25:'1/4',0.125:'1/8'}.get(round(float(v),4),f'{float(v):.4f}')
    except:return v or ''
def trf(v):
    if isinstance(v,datetime.datetime): return str((v-datetime.datetime(1900,1,1)).days+1)
    return v or ''
ogl=[]
for r in range(2,ws.max_row+1):
    if ws.cell(r,1).value is None:continue
    ogl.append((ws.cell(r,1).value,ws.cell(r,2).value,ws.cell(r,4).value,ws.cell(r,5).value,
                ws.cell(r,8).value,ws.cell(r,9).value,trf(ws.cell(r,14).value),royf(ws.cell(r,17).value),dt(ws.cell(r,15).value)))

L=[]
w=L.append
w(f"# Section 31, T12N–R24W, Roger Mills County, Oklahoma")
w(f"## Cursory Mineral & Leasehold Ownership Report — DEFINITIVE\n")
w(f"**Prospect {M['prospect']} · {M['gross']} gross acres · {M['tracts']} tracts · Report {M['report_date']} · Examiner {M['examiner']}**  ")
w(f"**Unit well: {M['well']} · API {M['api']} · {M['formation']} · active (HBP) · last production 3/1/2026**  ")
w(f"**Last index entry: {M['last_entry']}**\n")
w("> **Cursory — not a certified title opinion.** Interests are subject to curative requirements; confirm every interest against the recorded instruments before relying on this for a transaction.\n")
w("---\n## Executive summary\n")
w("Section 31 is a fully-leased, held-by-production Cherokee section. Every net mineral acre sits under one of **63 base oil-and-gas leases** (the 2004–2006 EOG / Arrowhead play, OGL 1–63), all carried **HBP** by the single active **Alexander 1-31** unit well. In 2026 **Silver Oak Natural Resources, LLC** took a six-lease **top-lease sweep** (OGL 64–69, 3/16 royalty) over the principal current owners — subordinate and springing until the base leases terminate.\n")
w("Fee mineral ownership is a family mosaic dominated by the **Mitchell / Williams / Moore**, **Bain**, **Kirk**, and **Daigle / Sorenson / Johnson** families, with modern mineral-fund buyers layered on top. All ten tracts foot to **637.42** acres; Tracts 1, 2, 6 and 8 are owner-reconciled, and carried HBP balances on the remaining tracts are shown as explicit open lines — never distributed to look finished. Nothing is fabricated.\n")

w("## Section plat (schematic — not a survey)\n")
w("| Tract | Legal | Gross ac | Status |")
w("|---|---|--:|---|")
stat={'reconciled':'Reconciled','partial':'Open balance','estate':'Estate/heirship','succession':'Succession verify'}
for t in D.TRACTS: w(f"| {t['n']} | {t['legal']} | {t['gross']:.2f} | {stat[t['status']]} |")
w(f"| | **SECTION** | **{M['gross']}** | |\n")

w("## Mineral ownership by tract\n")
w("*Identified record owners with net mineral acres, base OGL and 2026 Silver Oak top lease. Open/unreconciled balances are carried as explicit lines pending the instruments in Open Items — never spread to force a footing.*\n")
for t in D.TRACTS:
    n=t['n']
    w(f"**Tract {n} — {t['legal']} — {t['gross']:.2f} ac — {stat[t['status']]}**\n")
    w("| Owner | Net ac | Base OGL | Top | Royalty |")
    w("|---|--:|---|---|---|")
    for name,na,base,top,roy in D.OWNERS.get(n,[]):
        w(f"| {name} | {na:.2f} | {base} | {top} | {roy} |")
    w("")

w("## Leasehold — Silver Oak top leases (OGL 64–69, 3/16, springing)\n")
w("| OGL | Top lessor (current owner) | Bk/Pg | Executed | Expires | Term |")
w("|---|---|---|---|---|---|")
for n,l,bp,ex,xp,tm in D.TOP: w(f"| {n} | {l} | {bp} | {ex} | {xp} | {tm} |")
w("\n## Base lease register — OGL 1–63 (2004–2006, all HBP)\n")
w("| OGL | Instrument | Bk/Pg | Lessor | Lessee | Tracts | Roy. | Exp. |")
w("|---|---|---|---|---|---|---|---|")
for num,lh,instr,bp,gr,ge,tr,roy,exp in ogl:
    if str(lh).upper().startswith('TOP'):continue
    w(f"| {num} | {instr} | {bp} | {gr} | {ge} | {tr} | {roy} | {exp} |")

w("\n## Depth severances & non-standard royalty\n")
w("| OGL | Lessor → Lessee | Roy. | Depth / term provision |")
w("|---|---|---|---|")
for o,g,r,c in D.DEPTH: w(f"| {o} | {g} | {r} | {c} |")

w("\n## Working interest — wellbore chain\n")
w(" → ".join(D.WI_CHAIN))
w("\n\nCurrent wellbore assignment: Instr. 2026-002547, Bk 2698/069 (5-4-2026), Martin's Empire, LLC → Stride Bank, N.A., Trustee. **Reconcile against OCC Form 1073** — well of record shows operator Martin's Resources LLC; \"Martin's Empire, LLC\" did not surface in any public operator/entity index this session.\n")

w("## Unit well & HBP\n")
w("- **Alexander 1-31**, API 35-129-22925, Cherokee; surface C NW/4 SE/4, 660′ FWL × 1980′ FSL; completed 5/19/2006; OCC status **Active (AC)**; last reported production 3/1/2026; type oil; spacing 640 ac (order not of record).")
w("- A single active vertical well holds the base register (OGL 1–63) by production; Silver Oak top leases remain subordinate/springing.")
w("- Operator **Martin's Resources LLC** is a confirmed active but **marginal/stripper** Oklahoma producer (~2,792 BOE/mo across 3 wells; Roger Mills + Custer) — consistent with continuous-but-low production holding the section.")
w("- **Reserve for examiner:** OTC gross production by PUN (HBP proof); OCC Form 1002A (spud/perfs/TD-TVD); Form 1073 (operator of record). **Location discrepancy:** quarter call \"C NW/4 SE/4\" vs footages that fall in C NW/4 SW/4 — reconcile against plat/1002A.\n")

w("## Open items — what to pull to certify\n")
w("*Every item requires a source document blocked by this session's egress policy (okcountyrecords.com / OCC imaging & RBDMS / OTC all returned proxy 403). Pull each on an unrestricted machine. Nothing is fabricated to fill them.*\n")
w(f"### Source-in gaps — pull the grantor's vesting instrument ({len(D.GAPS)})\n")
w("| Conveying party (no source-in located) | Instrument out | Why open |")
w("|---|---|---|")
for p,i,ww in D.GAPS: w(f"| {p} | {i} | {ww} |")
w(f"\n### Conveyed-fraction gaps — read the granting language (39)\n")
w("| Tract | Instruments needing the conveyed fraction |")
w("|---|---|")
for k,v in D.FRACTION_GAPS.items(): w(f"| {k} | {v} |")
w(f"\n### Resolved this engagement ({len(D.RESOLVED)} parties)\n")
w("| Party | Source-in located (grantee-side) |")
w("|---|---|")
for p,s in D.RESOLVED: w(f"| {p} | {s} |")

w("\n## Well & regulatory research addendum (7/3/2026)\n")
w("*Egress blocked OCC RBDMS/imaging, OTC, ShaleXP, DrillingEdge (WebFetch 403 globally); operational facts are search-snippet level and must be re-pulled with direct access.*\n")
w("- **Martin's Resources LLC (confirmed active):** OK producer id 23562; ~2,792 BOE for 8/2025; 3 producing wells; Roger Mills & Custer; no future permits. (mineralanswers.com, shalexp.com)")
w("- **\"Martin's Empire, LLC\" — not found:** no OK SOS entity, OCC operator record, or O&G profile surfaced. Verify existence & relationship. *(flag)*")
w("- **Offset:** Charter Oak \"Solo 1-8H,\" horizontal Cottage Grove test in 8-12N-24W (MD ~16,230′, TVD ~10,850′, spud ~Aug 2025). Roger Mills is the busiest OK permit county. (mineralrightsforum.com, shaleexperts.com)")
w("- **Regional targets (context):** Cottage Grove, Tonkawa, Cleveland, Marmaton, Granite Wash; deeper Morrow/Springer/Chester/Hunton/Woodford basin-wide.")
w("- **Spacing:** 640-ac horizontal units standard in the township; no Section-31-specific order retrievable — pull OCC Case Processing by legal 31-12N-24W.\n")

w("---\n")
w(f"*Basis: 7-3-2026 NHE cursory workbook (19 sheets) · Roger Mills County Unplatted Legal Index (OCR, {M['instruments']} instruments, 2000–2026) · OGL register (69 leases) · independent OCC/operator research.*\n")
w("**Cursory cleanup only. Not a certified title opinion. Open and verify items remain only where source evidence was insufficient. Confirm all interests against the recorded instruments before relying on this report for a transaction.**")

open('report/REPORT_31-12N-24W.md','w').write("\n".join(str(x) for x in L))
print("wrote report/REPORT_31-12N-24W.md", sum(len(str(x)) for x in L),"chars")
