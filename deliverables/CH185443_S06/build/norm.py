# -*- coding: utf-8 -*-
"""CH185443 Section 6 - normalization rules (owner instruction 2026-10-20)."""
import re, math

QA = []          # (row, field, original, action, reason)
def qa(r,f,o,a,why): QA.append({'row':r,'field':f,'original':o,'action':a,'reason':why})

# ---------- Doc No -> integer ----------
def norm_docno(v, row):
    s=(v or '').strip()
    if not s: return None
    if s.lower() in ('unknown','n/a','none'):
        qa(row,'Doc No',s,'blanked','literal Unknown removed; document number not proved')
        return None
    if re.fullmatch(r'\d+', s):
        return int(s)            # drops source leading zeros per rule
    qa(row,'Doc No',s,'kept as text','non-numeric document number; preserved verbatim')
    return s

# ---------- Book-Page -> 0399-0142 ----------
BP = re.compile(r'^(?P<book>.+?)-(?P<rest>\d{1,4}(?:\s*(?:–|—|-|/|through)\s*\d{1,4})*)$')
def norm_bookpage(v, row):
    s=(v or '').strip()
    if not s: return ''
    if s.lower()=='unknown':
        qa(row,'Book-Page',s,'blanked','literal Unknown removed; book-page not proved in supplied image')
        return ''
    m=BP.match(s)
    if not m:
        qa(row,'Book-Page',s,'kept as-is','did not match book-folio pattern; preserved verbatim')
        return s
    book=m.group('book').strip(); rest=m.group('rest')
    book_n = book.zfill(4) if re.fullmatch(r'\d+',book) else book   # preserve A060/67MR/86A70/R/W32/0224 (Mining)
    folios=[f.zfill(4) for f in re.findall(r'\d{1,4}', rest)]
    out = book_n+'-'+'–'.join(folios)
    if out!=s: qa(row,'Book-Page',s,out,'normalized to 4-digit book-folio with en-dash span')
    return out

# ---------- Dates ----------
def norm_date(v,row,field):
    s=(v or '').strip()
    if not s: return ''
    if s.lower()=='unknown':
        qa(row,field,s,'blanked','literal Unknown removed; date not proved on instrument face - OPEN RESEARCH ITEM')
        return ''
    m=re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})',s)
    if m: return '%d/%d/%s'%(int(m.group(1)),int(m.group(2)),m.group(3))
    qa(row,field,s,'kept as-is','unrecognized date format')
    return s

# ---------- Parties ----------
NULL_PARTY = {
 'no grantee named in supplied notice':'notice of location names no grantee; true null, not a research gap',
 'no grantee named in supplied corner record':'corner record names no grantee; true null, not a research gap',
 'unknown':'literal Unknown removed; grantee not proved in supplied image - OPEN RESEARCH ITEM',
}
# parenthetical notes that are provenance/argument, not legal capacity -> strip
STRIP_PARENS = [
 r'\(recorder header\)', r'\(reciprocal\)',
 r'\(reciprocal mortgage/lien/security interests\)',
 r'\(reciprocal contractual and lien/security rights\)',
 r'\(alleged debtor; no title transfer established\)',
 r'\(mortgagee\)', r'\(affiant\)',
 r'\(mortgagor, grantor and debtor\)',
 r'\(Unit Operator and working-interest subscriber\)',
 r'\(working-interest subscriber\)',
 r'\(shown Unit Operator and working-interest subscriber\)',
 r'\(shown working-interest subscriber\)',
]
def norm_party(v,row,field):
    s=(v or '').strip()
    if not s: return ''
    if s.strip().lower() in NULL_PARTY:
        qa(row,field,s,'blanked',NULL_PARTY[s.strip().lower()]); return ''
    out=s
    for pat in STRIP_PARENS:
        if re.search(pat,out,re.I):
            out=re.sub(pat,'',out,flags=re.I).strip().rstrip(',').strip()
            qa(row,field,s,out,'removed non-substantive role/provenance note')
    out=re.sub(r'\(shown ','(',out)                      # "(shown Unit Operator)" -> "(Unit Operator)"
    out=re.sub(r'\bL\.L\.C\.','LLC',out)                 # L.L.C. -> LLC
    out=re.sub(r'\bL\. ?L\. ?C\b\.?','LLC',out)
    out=re.sub(r'(?<![,])\s+LLC\b', r', LLC', out)       # ensure ", LLC"
    out=re.sub(r'\s+,',',',out)
    out=re.sub(r',\s*,',',',out)
    out='\n'.join(ln.strip().rstrip(',')+',' if ln.strip() and i<len(out.split('\n'))-1 else ln.strip()
                   for i,ln in enumerate(out.split('\n')))
    out=re.sub(r'[ \t]+\n','\n',out); out=re.sub(r'\n[ \t]+','\n',out)
    out=re.sub(r'[ \t]{2,}',' ',out).strip()
    if out!=s and not any(q['row']==row and q['field']==field for q in QA):
        qa(row,field,s,out,'party formatting normalized')
    return out

# ---------- Legal descriptions ----------
AOL=', aol'
LEGAL_MAP = {
 'NW/4, Section 6, T47N, R76W, Johnson County, Wyoming':'NW/4 of 6-47N-76W',
 'South 1/16 Corner, Section 6, T47N, R76W, 6th P.M.; Johnson County, Wyoming':'South 1/16 Corner of 6-47N-76W',
 'T47N, R76W, Section 6: Lots 3, 4, 5, 6, 7; additional lands in Sections 7, 19, 30, 31 and T47N, R77W':'Lots 3, 4, 5, 6, 7 of 6-47N-76W, aol',
 'Lots 3, 4, 5, 6, 7, Section 6, T47N R76W; aol':'Lots 3, 4, 5, 6, 7 of 6-47N-76W, aol',
 'Lots 3, 4, 5, 6, 7, Section 6, T47N R76W, Johnson County, Wyoming; aol':'Lots 3, 4, 5, 6, 7 of 6-47N-76W, aol',
 'Lots 3, 4, 5, 6, 7 of Section 6, T47N, R76W, Johnson County, Wyoming; other lands':'Lots 3, 4, 5, 6, 7 of 6-47N-76W, aol',
 'Lots 1, 2, S/2 NE/4, SE/4 NW/4, E/2 SW/4, SE/4 of Section 6, T47N, R76W, Johnson County, Wyoming; other lands':'Lots 1, 2, S/2 NE/4, SE/4 NW/4, E/2 SW/4, SE/4 of 6-47N-76W, aol',
 'E/2, SE/4 NW/4, E/2 SW/4 of Section 6, T47N, R76W, Johnson County, Wyoming; other lands':'E/2, SE/4 NW/4, E/2 SW/4 of 6-47N-76W, aol',
 'Section 6 within Sections 1–36, T47N R76W; aol':'All of 6-47N-76W, aol',
 'Section 6 within Johnson County Sections 5–8,17–20,29–32, T47N R76W; aol':'All of 6-47N-76W, aol',
 'Section 6 within Johnson County T47N R76W Sections 5–8,17–20,29–32; aol':'All of 6-47N-76W, aol',
 'All of 6-47N-76W within stated Unit Tract 11, aol':'All of 6-47N-76W, aol',
 'Lode mining claims in 6-47N-76W, aol':'6-47N-76W, aol',
 'Source location written as Section(s) "6-31", Township 47 North, Range 76 West; Johnson County, Wyoming':'6-47N-76W, aol',
}
SRC_LOC = re.compile(r'^source location Section\(s\) "(?P<secs>[\d\- ]+)", Township 47N, Range 76W, Johnson County, Wyoming\. Exact aliquot/target allocation Unknown\.$', re.I)

def norm_legal(v,row):
    s=(v or '').strip()
    if not s: return ''
    if s in LEGAL_MAP:
        out=LEGAL_MAP[s]
        qa(row,'Legal Description',s,out,'normalized to <call> of 6-47N-76W[, aol]; county/state/unit/claim commentary removed')
        return out
    m=SRC_LOC.match(s)
    if m:
        secs=[x for x in re.split(r'-',m.group('secs').strip()) if x]
        out='6-47N-76W'+(AOL if len(secs)>1 else '')
        qa(row,'Legal Description',s,out,
           'lode location notice: section call retained; county/state commentary removed; aliquot NOT proved on face - OPEN RESEARCH ITEM (aliquot)')
        return out
    return s

# ---------- row height ----------
def px_per_char(): return 7.0
def wrap_lines(text, width_in):
    if text is None: return 1
    chars = max(int((width_in*96.0 - 6)/px_per_char()), 4)
    n=0
    for para in str(text).split('\n'):
        n += max(1, math.ceil(len(para)/chars))
    return max(n,1)
