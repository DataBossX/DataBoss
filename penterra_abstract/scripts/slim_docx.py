#!/usr/bin/env python3
"""Drop the legacy Word-2010 stylesWithEffects part and the template thumbnail
from a python-docx output, cleaning the matching relationship and content-type
entries so the package stays valid."""
import re, shutil, sys, zipfile
from pathlib import Path

DROP_PARTS = {"word/stylesWithEffects.xml", "docProps/thumbnail.jpeg"}
DROP_RELTYPES = ("stylesWithEffects", "thumbnail")

def clean_rels(xml: str) -> str:
    out = re.sub(
        r'<Relationship\b[^>]*?(?:' + "|".join(DROP_RELTYPES) + r')[^>]*?/>',
        "", xml, flags=re.I)
    return out

def clean_content_types(xml: str) -> str:
    xml = re.sub(r'<Override\b[^>]*stylesWithEffects[^>]*/>', "", xml, flags=re.I)
    xml = re.sub(r'<Override\b[^>]*thumbnail[^>]*/>', "", xml, flags=re.I)
    xml = re.sub(r'<Default\b[^>]*Extension="jpeg"[^>]*/>', "", xml, flags=re.I)
    return xml

def slim(path: Path) -> tuple[int, int]:
    src = zipfile.ZipFile(path)
    before = path.stat().st_size
    tmp = path.with_suffix(".slim")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for info in src.infolist():
            if info.filename in DROP_PARTS:
                continue
            data = src.read(info.filename)
            if info.filename.endswith(".rels"):
                data = clean_rels(data.decode("utf-8")).encode("utf-8")
            elif info.filename == "[Content_Types].xml":
                data = clean_content_types(data.decode("utf-8")).encode("utf-8")
            out.writestr(info.filename, data)
    src.close()
    shutil.move(tmp, path)
    return before, path.stat().st_size

if __name__ == "__main__":
    for p in sys.argv[1:]:
        p = Path(p)
        b, a = slim(p)
        print(f"{p.name}: {b} -> {a} bytes")
