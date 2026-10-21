#!/usr/bin/env python3
"""Lineage reconciliation, v2 — multiple defensible join keys.

v1 keyed on (Doc No, Book-Page) and over-split: the donor lineage sometimes
prefixes the recording year to Doc No (36246 vs 195136246) and the two lineages
use different book-numbering conventions in some sections. So we report a RANGE
using three independent keys and take book-folio as the primary.
"""
import sys, os, re, glob, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from odslib import Book
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def bookfolio(s):
    """'87A53-0700 through 0703' -> ('87A53','700');  'R/W32-0623-0632' -> ('RW32','623')"""
    t = (s or '').upper().replace('–','-').replace('—','-')
    t = re.sub(r'\s*(THROUGH|THRU|TO)\s*', '-', t)
    t = re.sub(r'[^0-9A-Z-]', '', t)
    parts = [p for p in t.split('-') if p]
    if len(parts) < 2: return None
    return (parts[0].lstrip('0') or '0', parts[1].lstrip('0') or '0')

def docno(s):
    d = re.sub(r'[^0-9]', '', s or '')
    return d.lstrip('0') or None

def docno_tail(s):
    """last 5-6 digits, to survive a year prefix like 1951|36246"""
    d = docno(s)
    return d[-5:] if d and len(d) >= 5 else d

def rows(path):
    b = Book(path); out=[]
    for rn, r in b.data_rows(9):
        out.append({'row':rn,'bf':bookfolio(r[4].text),'dn':docno(r[3].text),
                    'dt':docno_tail(r[3].text),
                    'doctype':(r[0].text or '').strip(),
                    'grantor':(r[1].text or '').strip()[:38],
                    'bookpage':(r[4].text or '').strip(),
                    'docnoraw':(r[3].text or '').strip(),
                    'rec':(r[6].text or '').strip()[:12],
                    'legal':(r[7].text or '').strip()[:55]})
    return out

SEC={'S6':'06','S7':'07','S13':'13','S18':'18','S24':'24'}
A={SEC[re.match(r'(S\d+)_',os.path.basename(p)).group(1)]:p
   for p in glob.glob(os.path.join(W,'src','*_County_Formatted_Index.ods'))
   if re.match(r'(S\d+)_',os.path.basename(p)).group(1) in SEC}
B={re.match(r'47N-7[67]W-(\d+)_',os.path.basename(p)).group(1).zfill(2):p
   for p in glob.glob(os.path.join(W,'src_donor','47N-*.ods'))}

print(f'{"Sec":>4} {"Fmt":>5} {"Donor":>6} | {"book-folio":>10} {"docno":>7} {"dn-tail":>8} | {"union(any key)":>14}')
print('-'*72)
detail=[]; T=collections.Counter()
for s in sorted(set(A)&set(B)):
    ra,rb=rows(A[s]),rows(B[s])
    def ov(k):
        ka={r[k] for r in ra if r[k]}; kb={r[k] for r in rb if r[k]}
        return ka&kb
    o_bf,o_dn,o_dt=ov('bf'),ov('dn'),ov('dt')
    # a Formatted row counts as matched if ANY key hits the donor set
    kb_bf={r['bf'] for r in rb if r['bf']}; kb_dn={r['dn'] for r in rb if r['dn']}
    kb_dt={r['dt'] for r in rb if r['dt']}
    matched=[r for r in ra if (r['bf'] in kb_bf) or (r['dn'] in kb_dn) or (r['dt'] in kb_dt)]
    ka_bf={r['bf'] for r in ra if r['bf']}; ka_dn={r['dn'] for r in ra if r['dn']}
    ka_dt={r['dt'] for r in ra if r['dt']}
    matched_b=[r for r in rb if (r['bf'] in ka_bf) or (r['dn'] in ka_dn) or (r['dt'] in ka_dt)]
    print(f'{s:>4} {len(ra):>5} {len(rb):>6} | {len(o_bf):>10} {len(o_dn):>7} {len(o_dt):>8} | {len(matched):>5}/{len(ra):<4} Fmt matched')
    T['fmt']+=len(ra); T['donor']+=len(rb); T['m']+=len(matched); T['mb']+=len(matched_b)
    for r in ra:
        if r not in matched:
            detail.append({'section':s,'only_in':'Formatted_Index','row':r['row'],
                'docno':r['docnoraw'],'bookpage':r['bookpage'],'rec':r['rec'],
                'doctype':r['doctype'],'grantor':r['grantor'],'legal':r['legal']})
    for r in rb:
        if r not in matched_b:
            detail.append({'section':s,'only_in':'donor-named','row':r['row'],
                'docno':r['docnoraw'],'bookpage':r['bookpage'],'rec':r['rec'],
                'doctype':r['doctype'],'grantor':r['grantor'],'legal':r['legal']})
print('-'*72)
print(f'{"TOT":>4} {T["fmt"]:>5} {T["donor"]:>6} |')
print(f'\nFormatted_Index rows matched in donor lineage : {T["m"]}/{T["fmt"]}  ({T["fmt"]-T["m"]} unique to Formatted)')
print(f'donor-named rows matched in Formatted lineage : {T["mb"]}/{T["donor"]}  ({T["donor"]-T["mb"]} unique to donor)')
out=os.path.join(W,'qa','LINEAGE_RECONCILIATION.csv')
with open(out,'w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['section','only_in','row','docno','bookpage','rec','doctype','grantor','legal'])
    w.writeheader(); w.writerows(detail)
print(f'rows unique to one lineage: {len(detail)} -> {out}')
