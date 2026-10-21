#!/usr/bin/env python3
"""Acceptance cycles 1-3: assert every client formatting rule actually holds in the saved ODS."""
import sys,os,glob,json
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from odslib import Book
import rules, re

fails=[]; checks=0
def ck(cond,msg):
    global checks; checks+=1
    if not cond: fails.append(msg)

for p in sorted(glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'out','Section_*','*.CORRECTED.ods'))):
    n=os.path.basename(p)
    b=Book(p); hdr=[c.text for c in b.grid(11)[8]]
    schema=rules.detect_schema(hdr); nc=10 if schema=='federal' else 9
    g=b.grid(nc)
    # headings exact
    want = rules.FEDERAL_HDR if schema=='federal' else rules.COUNTY_HDR
    ck([ (c.text or "").strip() for c in g[8][:nc]]==want, f'{n}: row9 headings != donor set')
    # row 8 blank
    ck(not any((c.text or '').strip() for c in g[7][:nc]), f'{n}: row 8 not blank')
    # prep date
    ck((g[2][1].text or '')==rules.PREP_DATE_TEXT, f'{n}: Date != 10/19/2026 (got {g[2][1].text!r})')
    ck((g[5][1].text or '')=='Ryan Gille', f'{n}: Indexed By != "Ryan Gille"')
    for i in range(9,len(g)):
        r=g[i]
        if not any((c.text or '').strip() for c in r[:nc]): continue
        rn=i+1
        if schema=='federal':
            ck(not (r[3].text or '').strip(), f'{n} r{rn}: File No not blank')
            pg=(r[4].text or '').strip()
            ck(pg=='' or pg.isdigit() or pg=='UNKNOWN' or re.match(r'^\d{3,4}-\d{3,4}$',pg),
               f'{n} r{rn}: Page not single number/UNKNOWN/book-page: {pg!r}')
            cm=(r[7].text or '').strip()
            ck(cm in ('','missing image'), f'{n} r{rn}: Comments not blank/"missing image": {cm!r}')
            ck((r[9].text or '').strip().upper()!='SRP', f'{n} r{rn}: SRP still in Part')
            legal=r[8].text or ''
        else:
            cm=(r[8].text or '').strip()
            ck(cm in ('','missing image'), f'{n} r{rn}: Comments not blank/"missing image": {cm!r}')
            legal=r[7].text or ''
        ck('See retained operative terms' not in legal, f'{n} r{rn}: internal x-ref still in Legal')
print(f'checks run : {checks}')
print(f'failures   : {len(fails)}')
for f in fails[:25]: print('  FAIL', f)
print('RESULT:', 'PASS' if not fails else 'FAIL')
sys.exit(1 if fails else 0)
