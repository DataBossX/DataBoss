"""Minimal, dependency-free ODS reader/writer for the CH185443 Penterra abstract indexes.

Reads the donor-format 10-column index (A..J) preserving:
  - metadata rows 1-7, blank row 8, headings row 9, data from row 10
  - per-cell style names, value-type and date-value
  - multi-paragraph cells (text:p repeats) as "\n"-joined text

Writes back a byte-valid ODS reusing the source's styles.xml / meta.xml / manifest,
so donor column widths, Calibri 11, borders, landscape geometry and print area survive.
"""
import re, zipfile, shutil, os
from xml.sax.saxutils import escape

NS_DECL = None

CELL_RE = re.compile(r'<table:table-cell\b([^>]*?)(/>|>(.*?)</table:table-cell>)', re.S)
ROW_RE  = re.compile(r'<table:table-row\b([^>]*?)>(.*?)</table:table-row>', re.S)
P_RE    = re.compile(r'<text:p\b[^>]*?(?:/>|>(.*?)</text:p>)', re.S)
ATTR_RE = re.compile(r'([\w:-]+)="([^"]*)"')

def _attrs(s):
    return dict(ATTR_RE.findall(s or ''))

def _unescape(t):
    if t is None: return ''
    t = re.sub(r'<text:s\s*/>', ' ', t)
    t = re.sub(r'<text:s\s+text:c="(\d+)"\s*/>', lambda m: ' '*int(m.group(1)), t)
    t = re.sub(r'<[^>]+>', '', t)
    return (t.replace('&lt;','<').replace('&gt;','>')
             .replace('&quot;','"').replace('&apos;',"'")
             .replace('&amp;','&'))

class Cell:
    __slots__=('text','style','vtype','dateval','raw_attrs')
    def __init__(self, text='', style=None, vtype=None, dateval=None, raw_attrs=None):
        self.text=text; self.style=style; self.vtype=vtype
        self.dateval=dateval; self.raw_attrs=raw_attrs or {}
    def __repr__(self):
        return f'Cell({self.text!r},{self.style})'

class Book:
    def __init__(self, path):
        self.path=path
        with zipfile.ZipFile(path) as z:
            self.names=z.namelist()
            self.parts={n:z.read(n) for n in self.names}
        self.content=self.parts['content.xml'].decode('utf-8')
        self._split()
        self.rows=self._parse_rows()

    def _split(self):
        m=re.search(r'(<table:table\b[^>]*>)(.*?)(</table:table>)', self.content, re.S)
        self.pre=self.content[:m.start()]
        self.table_open=m.group(1)
        self.table_body=m.group(2)
        self.table_close=m.group(3)
        self.post=self.content[m.end():]
        # keep column defs + named-expressions (everything before first row)
        r=re.search(r'<table:table-row\b', self.table_body)
        self.colhdr=self.table_body[:r.start()] if r else self.table_body
        self.rowsxml=self.table_body[r.start():] if r else ''

    def _parse_rows(self):
        out=[]
        for rm in ROW_RE.finditer(self.rowsxml):
            rattr=_attrs(rm.group(1)); cells=[]
            for cm in CELL_RE.finditer(rm.group(2)):
                a=_attrs(cm.group(1))
                rep=int(a.get('table:number-columns-repeated','1'))
                inner=cm.group(3) or ''
                ps=[_unescape(x.group(1)) for x in P_RE.finditer(inner)]
                txt='\n'.join(ps)
                c=Cell(txt,a.get('table:style-name'),a.get('office:value-type'),
                       a.get('office:date-value'),a)
                for _ in range(min(rep,64)):
                    cells.append(Cell(c.text,c.style,c.vtype,c.dateval,dict(a)))
            out.append({'attrs':rattr,'cells':cells})
        return out

    # ---- geometry helpers -------------------------------------------------
    def grid(self, ncols=10):
        g=[]
        for r in self.rows:
            row=[(r['cells'][i] if i<len(r['cells']) else Cell()) for i in range(ncols)]
            g.append(row)
        return g

    def data_rows(self, ncols=10, first_data_row=10):
        """1-indexed spreadsheet rows >= first_data_row that have any text."""
        g=self.grid(ncols)
        out=[]
        for idx,row in enumerate(g, start=1):
            if idx < first_data_row: continue
            if any((c.text or '').strip() for c in row):
                out.append((idx,row))
        return out

    # ---- writing ----------------------------------------------------------
    @staticmethod
    def cell_xml(c):
        a=[]
        if c.style: a.append(f'table:style-name="{c.style}"')
        txt=c.text or ''
        if c.vtype=='date' and c.dateval and txt:
            a.append('office:value-type="date"')
            a.append(f'office:date-value="{c.dateval}"')
        elif txt:
            a.append('office:value-type="string"')
        at=(' '+' '.join(a)) if a else ''
        if not txt:
            return f'<table:table-cell{at}><text:p></text:p></table:table-cell>'
        ps=''.join(f'<text:p>{escape(p)}</text:p>' for p in txt.split('\n'))
        return f'<table:table-cell{at}>{ps}</table:table-cell>'

    def render(self, grid):
        parts=[]
        for i,row in enumerate(grid):
            rattr=self.rows[i]['attrs'] if i<len(self.rows) else {'table:style-name':'ro1'}
            sa=' '.join(f'{k}="{v}"' for k,v in rattr.items())
            cells=''.join(self.cell_xml(c) for c in row)
            parts.append(f'<table:table-row {sa}>{cells}</table:table-row>')
        body=self.colhdr+''.join(parts)
        return self.pre+self.table_open+body+self.table_close+self.post

    def save(self, outpath, grid, title=None):
        newcontent=self.render(grid)
        meta=self.parts.get('meta.xml',b'').decode('utf-8')
        if title:
            meta=re.sub(r'<dc:title>.*?</dc:title>', f'<dc:title>{escape(title)}</dc:title>', meta, flags=re.S)
        os.makedirs(os.path.dirname(outpath), exist_ok=True)
        if os.path.exists(outpath): os.remove(outpath)
        with zipfile.ZipFile(outpath,'w') as z:
            # mimetype first, STORED, per ODF spec
            zi=zipfile.ZipInfo('mimetype'); zi.compress_type=zipfile.ZIP_STORED
            z.writestr(zi, self.parts['mimetype'])
            for n in self.names:
                if n=='mimetype': continue
                if n=='content.xml': z.writestr(n, newcontent.encode('utf-8'), zipfile.ZIP_DEFLATED)
                elif n=='meta.xml':  z.writestr(n, meta.encode('utf-8'), zipfile.ZIP_DEFLATED)
                else: z.writestr(n, self.parts[n], zipfile.ZIP_DEFLATED)
