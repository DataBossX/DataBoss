import sys, zipfile, json
from xml.etree import ElementTree as ET
NS={'o':'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
    't':'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
    'x':'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
def q(p,t): return '{%s}%s'%(NS[p],t)
def cell_text(c):
    parts=[]
    for p in c.findall(q('x','p')):
        seg=[]
        def walk(e):
            if e.text: seg.append(e.text)
            for ch in e:
                tag=ch.tag.split('}')[-1]
                if tag=='s':
                    seg.append(' '*int(ch.get(q('x','c') ,'1') or 1))
                elif tag=='line-break':
                    seg.append('\n')
                else:
                    walk(ch)
                if ch.tail: seg.append(ch.tail)
        walk(p)
        parts.append(''.join(seg))
    return '\n'.join(parts)
def read(path):
    z=zipfile.ZipFile(path); root=ET.fromstring(z.read('content.xml'))
    out={}
    for tb in root.iter(q('t','table')):
        name=tb.get(q('t','name')); rows=[]
        def rowiter(el):
            for ch in el:
                if ch.tag==q('t','table-row'): yield ch
                elif ch.tag in (q('t','table-header-rows'), q('t','table-row-group'), q('t','table-rows')):
                    for g in rowiter(ch): yield g
        for r in rowiter(tb):
            rr=int(r.get(q('t','number-rows-repeated'),'1') or 1)
            cells=[]
            for c in list(r):
                if c.tag not in (q('t','table-cell'), q('t','covered-table-cell')): continue
                cr=int(c.get(q('t','number-columns-repeated'),'1') or 1)
                vt=c.get(q('o','value-type')); v=c.get(q('o','value')); dv=c.get(q('o','date-value'))
                txt=cell_text(c)
                val={'text':txt,'vtype':vt,'num':v,'date':dv}
                for _ in range(min(cr,1024)): cells.append(val)
            while cells and not cells[-1]['text'] and not cells[-1]['num'] and not cells[-1]['date']: cells.pop()
            for _ in range(min(rr,1024)): rows.append(cells)
        while rows and not any(c['text'] or c['num'] or c['date'] for c in rows[-1]): rows.pop()
        out[name]=rows
    return out
if __name__=='__main__':
    d=read(sys.argv[1])
    json.dump(d, open(sys.argv[2],'w'), indent=1)
    for k,v in d.items(): print(k, len(v), 'rows; maxcols', max((len(r) for r in v), default=0))
