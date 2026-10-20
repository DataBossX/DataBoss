# -*- coding: utf-8 -*-
import json, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import norm, style
from openpyxl import Workbook
SCR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SCR,'out'); os.makedirs(OUT, exist_ok=True)
def g(r,i): return (r[i]['text'] if len(r)>i and r[i]['text'] else '')

# ========================= COUNTY =========================
src = json.load(open(os.path.join(SCR,'qa/S6_County_cells.json')))['County index']
headers = [c['text'] for c in src[8]]; data = src[9:]
assert len(data)==69 and len(headers)==9
META=[('County:','Johnson'),
      ('Lands:','T47N-R76W Section 6'),
      ('Date:','10/20/2026'),
      ('Starting Date:','Inception'),
      ('Date Posted Thru:','10/6/2026'),
      ('Indexed By:','Ryan Gille'),
      ('Project:','Combine-Harvest CH185443 / AFE 210275 - Section 6')]
norm.qa(4,'Starting Date','Unknown','Inception','donor Overtime convention (S11/S13/S15 all use "Inception"); county index run from inception of records')
norm.qa(5,'Date Posted Thru','Unknown','10/6/2026','proved: original 7-page county tract index PDF, physical page 5 "Land Validated Through: 10/6/2026" (32 of 32 results, T47N R76W Sec 06); 10/8/2026 5:07 PM is the print timestamp only')
norm.qa(1,'banner','WORKING DRAFT — INCOMPLETE SOURCE INTAKE AND REVIEW','removed from client grid','not a donor metadata field; qualification carried in the unsigned certificate and QA register')
norm.qa(6,'Indexed By','Working draft — review pending','Ryan Gille','donor metadata field value')

rows=[]
for k,r in enumerate(data):
    xl=10+k
    com=g(r,8)
    if com and com.strip().lower()!='missing image':
        norm.qa(xl,'Comments',com,'blanked','client Comments permits only blank or exactly "missing image"'); com=''
    rows.append([g(r,0), norm.norm_party(g(r,1),xl,'Grantor'), norm.norm_party(g(r,2),xl,'Grantee'),
                 norm.norm_docno(g(r,3),xl), norm.norm_bookpage(g(r,4),xl),
                 norm.norm_date(g(r,5),xl,'Date of Doc'), norm.norm_date(g(r,6),xl,'Rec Date'),
                 norm.norm_legal(g(r,7),xl), com])
wb=Workbook(); ws=wb.active; ws.title='Index'
style.write_meta(ws,META,9); style.write_headers(ws,headers)
for k,row in enumerate(rows):
    xl=10+k
    for j,v in enumerate(row,1):
        style.write_cell(ws,xl,j,v, datecol=(j in (6,7)), numcol=(j==4))
    ws.row_dimensions[xl].height=None
style.set_widths(ws, style.COUNTY_W_CM); style.apply_page(ws,9,9+len(rows),fit=True)   # owner rule: one-page width
cty=os.path.join(OUT,'CH185443_S06_County_Abstract_Index_20261020.xlsx'); wb.save(cty)
json.dump(norm.QA, open(os.path.join(SCR,'qa/S6_County_QA_register.json'),'w'), indent=1)
json.dump(rows, open(os.path.join(SCR,'qa/S6_County_final_rows.json'),'w'), indent=1, default=str)
cty_qa=len(norm.QA); print('county rows',len(rows),'qa',cty_qa)

# ========================= BLM =========================
norm.QA=[]
src=json.load(open(os.path.join(SCR,'qa/S6_BLM_cells.json')))['Index']
bh=[c['text'] for c in src[8]]; bdata=src[9:]
assert len(bdata)==61
BMETA=[('County:','Johnson'),
       ('Lands:','T47N-R76W Section 6 - Federal - WYW-149799 / WYWY105544892'),
       ('Date:','10/20/2026'),
       ('Starting Date:','Inception'),
       ('Date Posted Thru:','10/13/2026'),
       ('Indexed By:','Ryan Gille'),
       ('Project:','Combine-Harvest CH185443 / AFE 210275 - WYW-149799')]
norm.qa(4,'Starting Date','(blank)','Inception','donor Overtime convention; SRP corroborates case inception - CASE ESTABLISHED 02/01/1999, lease Effective Date 02/01/1999')
norm.qa(5,'Date Posted Thru','(blank)','10/13/2026','SRP WYWY105544892 Run Date/Time 10/13/2026 16:11 PM; federal file current through SRP run date. County 10/6/2026 date deliberately NOT applied to the federal index')
LS=re.compile(r',\s*(?=(?:Lots?|All|N/2|S/2|E/2|W/2|NE/4|NW/4|SE/4|SW/4|Tract)\b)')
def blm_legal(v,row):
    s=(v or '').strip()
    if not s: return ''
    aol=s.endswith(', aol'); body=s[:-5] if aol else s
    out=[]
    for p in re.split(r'\n',body):
        out.extend([q.strip().rstrip(',') for q in LS.split(p.strip()) if q.strip()])
    txt=',\n'.join(out)+(', aol' if aol else '')
    if txt!=s: norm.qa(row,'Legal Description',s,txt,'each proved legal on its own comma-terminated line; ", aol" retained once')
    return txt
brows=[]
for k,r in enumerate(bdata):
    xl=10+k; gtee=g(r,2)
    if gtee.strip().lower()=='unknown':
        gtee='US Realm Powder River, LLC'
        norm.qa(xl,'Grantee','Unknown',gtee,'literal Unknown replaced from SRP WYWY105544892: US REALM POWDER RIVER LLC shown LESSEE 100.0000%; MERGER NAME CHANGE from Moriah Powder River LLC recognized 06/15/2020, so lessee of record at the 6/16/2022 notice. SOURCE-DERIVED from SRP - confirm against case Part 2 page 53 image at examiner review')
    brows.append([g(r,0), norm.norm_party(g(r,1),xl,'Grantor'), norm.norm_party(gtee,xl,'Grantee'),
                  None, int(g(r,4)) if g(r,4).isdigit() else g(r,4),
                  norm.norm_date(g(r,5),xl,'Date of Doc'), norm.norm_date(g(r,6),xl,'Rec Date'),
                  None, blm_legal(g(r,8),xl), int(g(r,9)) if g(r,9).isdigit() else g(r,9)])
brows.sort(key=lambda x:(x[9],x[4]))
wb=Workbook(); ws=wb.active; ws.title='Index'
style.write_meta(ws,BMETA,10); style.write_headers(ws,bh)
for k,row in enumerate(brows):
    xl=10+k
    for j,v in enumerate(row,1):
        style.write_cell(ws,xl,j,v, datecol=(j in (6,7)), numcol=(j in (5,10)))
    ws.row_dimensions[xl].height=None
style.set_widths(ws, style.BLM_W_CM); style.apply_page(ws,10,9+len(brows),fit=True)  # donor BLM: scale-to-X 1
blm=os.path.join(OUT,'CH185443_S06_BLM_WYW-149799_Abstract_Index_20261020.xlsx'); wb.save(blm)
json.dump(norm.QA, open(os.path.join(SCR,'qa/S6_BLM_QA_register.json'),'w'), indent=1)
json.dump(brows, open(os.path.join(SCR,'qa/S6_BLM_final_rows.json'),'w'), indent=1, default=str)
print('blm rows',len(brows),'qa',len(norm.QA))
