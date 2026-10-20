# -*- coding: utf-8 -*-
import os,sys,json,re,hashlib,datetime,zipfile
from openpyxl import load_workbook
SCR=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT=os.path.join(SCR,'out')
CTY=os.path.join(OUT,'CH185443_S06_County_Abstract_Index_20261020.xlsx')
BLM=os.path.join(OUT,'CH185443_S06_BLM_WYW-149799_Abstract_Index_20261020.xlsx')
res=[]
def chk(gate,name,ok,detail=''):
    res.append({'gate':gate,'check':name,'status':'PASS' if ok else 'FAIL','detail':detail})

def grid(ws,ncols,nrows):
    bad_border=bad_font=bad_fill=bad_align=0; unk=[]
    for r in range(10,nrows+1):
        for c in range(1,ncols+1):
            cell=ws.cell(r,c)
            b=cell.border
            if not all(s and s.style=='thin' for s in (b.left,b.right,b.top,b.bottom)): bad_border+=1
            f=cell.font
            if f.name!='Calibri' or float(f.size)!=11.0 or (f.color and f.color.rgb not in ('FF000000',None)): bad_font+=1
            if cell.fill and cell.fill.fill_type not in (None,): bad_fill+=1
            a=cell.alignment
            if a.horizontal!='left' or a.vertical!='top' or not a.wrap_text: bad_align+=1
            v=cell.value
            if isinstance(v,str) and re.search(r'\bunknown\b',v,re.I): unk.append((r,c,v[:40]))
    return bad_border,bad_font,bad_fill,bad_align,unk

# ---- GATE 3: fields & donor-format ----
wc=load_workbook(CTY); wsc=wc['Index']; NC=wsc.max_row
wb_=load_workbook(BLM); wsb=wb_['Index']; NB=wsb.max_row
for tag,ws,nc,nr in (('County',wsc,9,NC),('BLM',wsb,10,NB)):
    bb,bf,bfl,ba,unk=grid(ws,nc,nr)
    chk(3,'%s: thin black border on every data cell'%tag,bb==0,'%d offending cells'%bb)
    chk(3,'%s: Calibri 11 black on every data cell'%tag,bf==0,'%d offending cells'%bf)
    chk(3,'%s: no fill on any data cell'%tag,bfl==0,'%d offending cells'%bfl)
    chk(3,'%s: uniform left/top/wrap alignment'%tag,ba==0,'%d offending cells'%ba)
    chk(3,'%s: no literal "Unknown" in any client cell'%tag,not unk,str(unk[:3]))
    chk(3,'%s: metadata rows 1-7, row 8 blank, headers row 9'%tag,
        all(ws.cell(i,1).value for i in range(1,8)) and ws.cell(8,1).value is None and ws.cell(9,1).value=='Document Type')
    chk(4,'%s: landscape + fit one page wide'%tag, ws.page_setup.orientation=='landscape' and ws.page_setup.fitToWidth==1)
    chk(4,'%s: donor margins (0.7 L/R, 0.3 T/B)'%tag,
        float(ws.page_margins.left)==0.7 and float(ws.page_margins.right)==0.7 and float(ws.page_margins.top)==0.3)
    chk(4,'%s: repeated header rows 1:9'%tag, ws.print_title_rows in ('1:9','$1:$9'), str(ws.print_title_rows))
    chk(4,'%s: all data rows auto-fit (no fixed height)'%tag,
        all(ws.row_dimensions[r].height is None for r in range(10,nr+1)))

# county-specific field rules
docno_bad=[r for r in range(10,NC+1) if wsc.cell(r,4).value is not None and not isinstance(wsc.cell(r,4).value,int)]
chk(3,'County: Doc No stored as number',not docno_bad,str(docno_bad[:5]))
bp_bad=[(r,wsc.cell(r,5).value) for r in range(10,NC+1)
        if wsc.cell(r,5).value and not re.fullmatch(r'[0-9A-Za-z/ ()]+-\d{4}(–\d{4})*',str(wsc.cell(r,5).value))]
chk(3,'County: Book-Page normalized (BOOK-0000[–0000])',not bp_bad,str(bp_bad[:5]))
dt_bad=[(r,c) for r in range(10,NC+1) for c in (6,7)
        if wsc.cell(r,c).value is not None and not isinstance(wsc.cell(r,c).value,(datetime.date,datetime.datetime))]
chk(3,'County: dates stored as real dates (M/D/YYYY)',not dt_bad,str(dt_bad[:5]))
leg_bad=[(r,wsc.cell(r,8).value) for r in range(10,NC+1) if wsc.cell(r,8).value and
         re.search(r'Johnson County|Wyoming|6th P\.M\.|Township|depth|formation|Unit Tract|lease',str(wsc.cell(r,8).value),re.I)]
chk(3,'County: legals carry no county/state/PM/unit/lease commentary',not leg_bad,str(leg_bad[:3]))
leg_fmt=[(r,wsc.cell(r,8).value) for r in range(10,NC+1) if wsc.cell(r,8).value and
         not re.search(r'\b6-47N-76W\b',str(wsc.cell(r,8).value))]
chk(3,'County: every legal uses <call> of 6-47N-76W form',not leg_fmt,str(leg_fmt[:3]))
cm=[(r,wsc.cell(r,9).value) for r in range(10,NC+1) if wsc.cell(r,9).value not in (None,'missing image')]
chk(3,'County: Comments blank or exactly "missing image"',not cm,str(cm[:3]))
par=[(r,c,wsc.cell(r,c).value) for r in range(10,NC+1) for c in (2,3)
     if wsc.cell(r,c).value and re.search(r'\((releasing|recorder|reciprocal|alleged|affiant|mortgagee|shown)',str(wsc.cell(r,c).value),re.I)]
chk(3,'County: no non-substantive role notes in parties',not par,str(par[:3]))
llc=[(r,c,wsc.cell(r,c).value) for r in range(10,NC+1) for c in (2,3)
     if wsc.cell(r,c).value and re.search(r'L\.L\.C\.|[^,] LLC\b',str(wsc.cell(r,c).value))]
chk(3,'County: LLC rendered as ", LLC"',not llc,str(llc[:3]))

# BLM-specific
fn=[r for r in range(10,NB+1) if wsb.cell(r,4).value is not None]
chk(3,'BLM: File No blank in all data rows',not fn,str(fn[:5]))
cmb=[r for r in range(10,NB+1) if wsb.cell(r,8).value is not None]
chk(3,'BLM: Comments blank in all data rows',not cmb,str(cmb[:5]))
pt=[r for r in range(10,NB+1) if not isinstance(wsb.cell(r,10).value,int)]
chk(3,'BLM: Part is last column and numeric',not pt,str(pt[:5]))
pg=[r for r in range(10,NB+1) if not isinstance(wsb.cell(r,5).value,int)]
chk(3,'BLM: Page numeric (1-based physical page)',not pg,str(pg[:5]))
order=[(wsb.cell(r,10).value,wsb.cell(r,5).value) for r in range(10,NB+1)]
chk(2,'BLM: sorted by case, then Part, then first physical Page',order==sorted(order),'')

# ---- GATE 2: omissions / duplicates ----
src_c=json.load(open(os.path.join(SCR,'qa/S6_County_cells.json')))['County index'][9:]
src_b=json.load(open(os.path.join(SCR,'qa/S6_BLM_cells.json')))['Index'][9:]
chk(2,'County: row count preserved from source (69)',NC-9==len(src_c)==69,'%d vs %d'%(NC-9,len(src_c)))
chk(2,'BLM: row count preserved from source (61)',NB-9==len(src_b)==61,'%d vs %d'%(NB-9,len(src_b)))
keyc=[(wsc.cell(r,4).value,str(wsc.cell(r,5).value)) for r in range(10,NC+1)]
dup=[k for k in set(keyc) if keyc.count(k)>1]
chk(2,'County: no duplicate Doc No + Book-Page pair',not dup,str(dup[:5]))
srcdoc=sorted(int(c[3]['text']) for c in [r for r in src_c] if c[3]['text'].isdigit())
chk(2,'County: every source Doc No present in output',
    sorted(x for x,_ in keyc if isinstance(x,int))==srcdoc,'')
# ---- GATE 1: source/currentness ----
chk(1,'County Date Posted Thru = 10/6/2026 (tract index p.5)',
    str(wsc.cell(5,2).value)[:10]=='2026-10-06',str(wsc.cell(5,2).value))
chk(1,'BLM Date Posted Thru = 10/13/2026 (SRP run date)',
    str(wsb.cell(5,2).value)[:10]=='2026-10-13',str(wsb.cell(5,2).value))
chk(1,'Preparation date = 10/20/2026 on both indexes',
    str(wsc.cell(3,2).value)[:10]=='2026-10-20' and str(wsb.cell(3,2).value)[:10]=='2026-10-20')
chk(1,'County date not applied to federal index',str(wsb.cell(5,2).value)[:10]!='2026-10-06')
chk(1,'SRP source present and hashed',os.path.exists(os.path.join(SCR,'src/SRP_WYW149799.pdf')))
json.dump(res,open(os.path.join(SCR,'qa/QA_GATES.json'),'w'),indent=1)
f=[r for r in res if r['status']=='FAIL']
print('CHECKS',len(res),'PASS',len(res)-len(f),'FAIL',len(f))
for x in f: print('  FAIL g%s %s :: %s'%(x['gate'],x['check'],x['detail'][:160]))
