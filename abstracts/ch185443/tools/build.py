#!/usr/bin/env python3
"""CH185443 build: apply Overtime donor formatting rules, emit ODS/XLSX/PDF + QA receipts."""
import sys, os, glob, json, csv, hashlib, subprocess, shutil, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from odslib import Book
import rules

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT, QA = os.path.join(W,'out'), os.path.join(W,'qa')

SEC_OF = {'S6':'06','S7':'07','S13':'13','S18':'18','S19':'19','S24':'24','S30':'30','S31':'31'}
TOWNSHIP = {'06':'T47N-R76W','07':'T47N-R76W','18':'T47N-R76W','19':'T47N-R76W',
            '30':'T47N-R76W','31':'T47N-R76W','13':'T47N-R77W','24':'T47N-R77W'}

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def sec_of(name):
    m=re.match(r'(S\d+)_',name)
    return SEC_OF.get(m.group(1)) if m else None

def main(srcs):
    os.makedirs(OUT,exist_ok=True); os.makedirs(QA,exist_ok=True)
    ledger=[]; summary=[]
    for p in sorted(srcs):
        base=os.path.basename(p); name=base[:-4]
        sec=sec_of(base)
        b=Book(p)
        hdr=[c.text for c in b.grid(11)[8]]
        schema=rules.detect_schema(hdr)
        ncols=10 if schema=='federal' else 9
        grid=b.grid(ncols)
        before=len(b.data_rows(ncols))
        # cell census BEFORE
        cells_before=sum(1 for r in grid[9:] for c in r[:ncols] if (c.text or '').strip())
        rules.apply(b,grid,schema,name,ledger)
        after=len(b.data_rows(ncols))  # unchanged structurally
        populated=sum(1 for r in grid[9:] for c in r[:ncols] if (c.text or '').strip())
        outdir=os.path.join(OUT,f'Section_{sec}')
        os.makedirs(outdir,exist_ok=True)
        outods=os.path.join(outdir,f'{name}.CORRECTED.ods')
        b.save(outods,grid,title=None)
        summary.append({'book':name,'section':sec,'township':TOWNSHIP.get(sec,''),
                        'schema':schema,'columns':ncols,'data_rows':before,
                        'populated_cells_before':cells_before,'populated_cells_after':populated,
                        'ods':outods,'sha256':sha(outods),'bytes':os.path.getsize(outods)})
        print(f'{name:48s} {schema:7s} rows={before:4d} cells {cells_before}->{populated}')
    # ledger
    lp=os.path.join(QA,'FORMATTING_CHANGE_LEDGER.csv')
    with open(lp,'w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['book','row','col','rule','old','new','note'])
        w.writeheader(); w.writerows(ledger)
    with open(os.path.join(QA,'BOOK_SUMMARY.json'),'w') as f:
        json.dump(summary,f,indent=2)
    # rule tally
    tally={}
    for e in ledger: tally[e['rule']]=tally.get(e['rule'],0)+1
    with open(os.path.join(QA,'RULE_TALLY.json'),'w') as f: json.dump(tally,f,indent=2)
    print('\n--- rule applications ---')
    for k in sorted(tally): print(f'  {k:28s} {tally[k]}')
    print(f'\nledger rows: {len(ledger)}  -> {lp}')
    return summary

if __name__=='__main__':
    srcs=sys.argv[1:] or (glob.glob(os.path.join(W,'src','*.ods'))+glob.glob(os.path.join(W,'src_fed','*.ods')))
    main(srcs)
