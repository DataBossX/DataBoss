"""R8: force US Letter LANDSCAPE page geometry (11in x 8.5in) in an ODS styles.xml.

The donor index prints Letter landscape (792 x 612 pt). The candidate files declare
style:print-orientation="landscape" but omit fo:page-width/fo:page-height, so
renderers fall back to A4 portrait. This writes the explicit size.
"""
import re, zipfile, os, shutil

def fix(path):
    with zipfile.ZipFile(path) as z:
        names=z.namelist(); parts={n:z.read(n) for n in names}
    s=parts['styles.xml'].decode('utf-8')
    if 'fo:page-width' in s:
        changed=False
    else:
        s2=re.sub(r'(<style:page-layout-properties\b)',
                  r'\1 fo:page-width="11in" fo:page-height="8.5in"', s, count=1)
        changed = s2!=s; s=s2
    if not changed: return False
    parts['styles.xml']=s.encode('utf-8')
    tmp=path+'.tmp'
    with zipfile.ZipFile(tmp,'w') as z:
        zi=zipfile.ZipInfo('mimetype'); zi.compress_type=zipfile.ZIP_STORED
        z.writestr(zi,parts['mimetype'])
        for n in names:
            if n=='mimetype': continue
            z.writestr(n,parts[n],zipfile.ZIP_DEFLATED)
    shutil.move(tmp,path); return True
