#!/usr/bin/env python3
"""Cell-level gap ledger for the expanded candidate packages.
A gap = a substantive cell that is 'Unknown' or blank. Comments / File No are
intentionally blank per client rule and never counted. Nothing is filled in:
UNKNOWN IS NOT ZERO."""
import sys,os,glob,csv,re,collections
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from odslib import Book
W=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows=[]; pop=collections.Counter(); cells=collections.Counter()
for p in sorted(glob.glob(os.path.join(W,'pkgx','Sec*','*','*Abstract_Index.ods'))):
    sec=p.split(os.sep)[-3]; book=os.path.basename(p).split('_Johnson')[0]
    b=Book(p); hdr=[c.text for c in b.grid(11)[8]]
    fed='File No' in hdr; nc=10 if fed else 9; g=b.grid(nc); H=[c.text for c in g[8][:nc]]
    kind='federal' if fed else 'county'
    for i in range(9,len(g)):
        r=g[i]
        if not any((c.text or '').strip() for c in r[:nc]): continue
        pop[(sec,kind)]+=1
        ident=(r[3].text if not fed else (r[4].text or ''))
        for j,c in enumerate(r[:nc]):
            if H[j] in ('Comments','File No'): continue
            cells[(sec,kind)]+=1
            t=(c.text or '').strip()
            if t=='' or t.lower()=='unknown':
                rows.append({'section':sec,'book':book,'kind':kind,'sheet_row':i+1,'column':H[j],
                    'value':t or '(blank)','doc_type':(r[0].text or '')[:48],
                    'date_of_doc':(r[5].text or ''),'doc_no_or_page':(r[3].text if not fed else r[4].text) or ''})
out=os.path.join(W,'qa','EXPANDED_PACKAGE_GAP_LEDGER.csv')
with open(out,'w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(f'{"section":7s}{"kind":8s}{"rows":>5s}{"cells":>7s}{"gaps":>6s}{"populated%":>12s}')
G=collections.Counter((r['section'],r['kind']) for r in rows); tr=tc=tg=0
for k in sorted(pop):
    c=cells[k]; g_=G[k]; tr+=pop[k]; tc+=c; tg+=g_
    print(f'{k[0]:7s}{k[1]:8s}{pop[k]:5d}{c:7d}{g_:6d}{100*(c-g_)/c:11.2f}%')
print(f'{"TOTAL":15s}{tr:5d}{tc:7d}{tg:6d}{100*(tc-tg)/tc:11.2f}%')
byc=collections.Counter(r['column'] for r in rows)
print('\ngaps by column:',dict(byc.most_common()))
print('ledger ->',out,len(rows),'rows')
