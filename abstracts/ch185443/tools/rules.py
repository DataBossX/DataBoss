"""CH185443 Overtime-donor formatting rules engine.

Deterministic, logged, reversible. Every mutation writes an evidence row to a ledger,
so nothing is silently discarded (spec section 4 / release rule).

COUNTY schema  (9 cols) : Document Type|Grantor|Grantee|Doc No|Book-Page|Date of Doc|Rec Date|Legal Description|Comments
FEDERAL schema (10 cols): Document Type|Grantor|Grantee|File No|Page|Date of Doc|Rec Date|Comments|Legal Description|Part

Rules applied (from the client instruction of 10/19/2026):
 R1  Federal "File No" (D) emptied, column RETAINED.
 R2  Federal "Page" (E) reduced to ONE number = first page of the file.
     Book-Page style refs (NNNN-NNNN) are NOT invented into page numbers; retained + flagged.
 R3  "SRP" removed from federal "Part" (J).
 R4  Comments blank except the exact string "missing image".
 R5  Legal Description: internal cross-references ("See retained operative terms ...") removed
     from the client cell; full original preserved in the ledger.
 R6  Metadata rows 1-7 normalised to one donor convention; preparation Date = 10/19/2026.
 R7  UNKNOWN is never replaced by a guess. Left as-is and reported.
"""
import re, json

PREP_DATE_TEXT = '10/19/2026'
PREP_DATE_VAL  = '2026-10-19T00:00:00'

COUNTY_HDR = ['Document Type','Grantor','Grantee','Doc No','Book-Page',
              'Date of Doc','Rec Date','Legal Description','Comments']
FEDERAL_HDR= ['Document Type','Grantor','Grantee','File No','Page','Date of Doc',
              'Rec Date','Comments','Legal Description','Part']

XREF_RE = re.compile(r'^\s*See retained operative terms\b.*$', re.I)
PAGE_ANCHOR_RE = re.compile(r'(?:\bpp?\.?|\bpages?\b)\s*(\d+)', re.I)
BOOKPAGE_RE = re.compile(r'^\s*\d{3,4}\s*-\s*\d{3,4}\s*$')
INTONLY_RE = re.compile(r'^\s*\d+\s*$')

def detect_schema(hdr):
    h=[(x or '').strip() for x in hdr]
    if h[:10]==FEDERAL_HDR: return 'federal'
    if h[:9]==COUNTY_HDR:   return 'county'
    if 'File No' in h and 'Part' in h: return 'federal'
    return 'county'

def first_page(val):
    """R2 -> (new_value, flag_or_None)."""
    v=(val or '').strip()
    if not v: return '', None
    if v.upper()=='UNKNOWN': return v, 'page UNKNOWN retained'
    m=PAGE_ANCHOR_RE.search(v)
    if m:
        n=m.group(1).lstrip('0') or '0'
        return n, None if v==n else f'page reduced to first page {n}'
    if BOOKPAGE_RE.match(v):
        return v, 'county Book-Page reference retained; no BLM case page in source'
    if INTONLY_RE.match(v):
        n=v.strip().lstrip('0') or '0'
        return n, None if v.strip()==n else 'leading zeros removed'
    return v, 'page text not reducible to a single number; retained for examiner'

def clean_comments(val):
    """R4 -> (new, flag)."""
    v=(val or '').strip()
    if not v: return '', None
    if v.lower()=='missing image': return 'missing image', None
    return '', f'comment removed: {v}'

def clean_legal(val):
    """R5 -> (new, removed_lines)."""
    if not val: return '', []
    keep,removed=[],[]
    for line in val.split('\n'):
        if XREF_RE.match(line): removed.append(line.strip())
        else: keep.append(line)
    while keep and not keep[-1].strip(): keep.pop()
    return '\n'.join(keep), removed

def clean_part(val):
    v=(val or '').strip()
    if v.upper()=='SRP': return '', 'Part "SRP" removed per client instruction'
    return v, None

META = {
 'County:'          : ('Johnson', None),
 'Indexed By:'      : ('Ryan Gille', None),
 'Project:'         : ('Abstract 210275 Combine-Harvest', None),
 'Date:'            : (PREP_DATE_TEXT, PREP_DATE_VAL),
}

def apply(book, grid, schema, bookname, ledger):
    """Mutate `grid` in place; append dicts to `ledger`."""
    ncols = 10 if schema=='federal' else 9
    def log(row,col,rule,old,new,note=''):
        ledger.append({'book':bookname,'row':row,'col':col,'rule':rule,
                       'old':old,'new':new,'note':note})

    # ---- R6 metadata rows 1-7 -------------------------------------------
    for i in range(min(7,len(grid))):
        label=(grid[i][0].text or '').strip()
        if label in META:
            new,dval=META[label]
            old=grid[i][1].text
            if old!=new:
                grid[i][1].text=new
                if dval:
                    grid[i][1].vtype='date'; grid[i][1].dateval=dval
                else:
                    grid[i][1].vtype='string'; grid[i][1].dateval=None
                log(i+1,'B','R6-metadata',old,new)
        if label in ('Starting Date:','Date Posted Thru:'):
            v=(grid[i][1].text or '').strip()
            if v.upper() in ('UNKNOWN','') or v.lower()=='unknown':
                log(i+1,'B','R7-unknown-retained',v,v,
                    'official research currentness not established; release gate')

    # ---- data rows ------------------------------------------------------
    for idx in range(9, len(grid)):
        row=grid[idx]
        if not any((c.text or '').strip() for c in row[:ncols]): continue
        rn=idx+1
        if schema=='federal':
            if (row[3].text or '').strip():
                log(rn,'D','R1-fileno-cleared',row[3].text,'' ,'column retained, value removed')
                row[3].text=''; row[3].vtype=None; row[3].dateval=None
            new,flag=first_page(row[4].text)
            if new!=(row[4].text or ''):
                log(rn,'E','R2-first-page',row[4].text,new,flag or '')
                row[4].text=new
            elif flag: log(rn,'E','R2-flag',row[4].text,row[4].text,flag)
            new,flag=clean_comments(row[7].text)
            if new!=(row[7].text or ''):
                log(rn,'H','R4-comments',row[7].text,new,flag or ''); row[7].text=new
            new,removed=clean_legal(row[8].text)
            if removed:
                log(rn,'I','R5-legal-xref',row[8].text,new,' | '.join(removed)); row[8].text=new
            new,flag=clean_part(row[9].text)
            if flag: log(rn,'J','R3-srp',row[9].text,new,flag); row[9].text=new
        else:
            new,removed=clean_legal(row[7].text)
            if removed:
                log(rn,'H','R5-legal-xref',row[7].text,new,' | '.join(removed)); row[7].text=new
            new,flag=clean_comments(row[8].text)
            if new!=(row[8].text or ''):
                log(rn,'I','R4-comments',row[8].text,new,flag or ''); row[8].text=new
    return grid
