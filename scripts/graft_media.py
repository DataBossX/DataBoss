#!/usr/bin/env python3
"""graft_media.py — re-inject media/drawings that openpyxl drops on save.

openpyxl rewrites an .xlsx without the images and drawing parts it cannot
round-trip. This restores them by copying the drawing + media parts from the
ORIGINAL workbook into the openpyxl OUTPUT and re-wiring:
  - [Content_Types].xml  (Default png/svg, Override per drawing)
  - xl/worksheets/_rels/sheetN.xml.rels  (drawing relationship)
  - xl/worksheets/sheetN.xml  (<drawing r:id=.../> element)

Sheet ownership of each drawing is resolved by SHEET NAME so it survives any
file renumbering. Assumes openpyxl preserves sheet order (it does).

Usage: python scripts/graft_media.py <original.xlsx> <openpyxl_output.xlsx>
The output workbook is patched in place.
"""
import re
import shutil
import sys
import zipfile

DRAW_CT = "application/vnd.openxmlformats-officedocument.drawing+xml"
DRAW_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"


def sheet_name_to_part(zf):
    """Map sheet display name -> worksheets/sheetN.xml part path."""
    wb = zf.read("xl/workbook.xml").decode("utf-8")
    rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    # robust parse, tolerant of either attribute order
    pairs = re.findall(r'<Relationship\b[^>]*?>', rels)
    rid_to_target = {}
    for p in pairs:
        rid = re.search(r'Id="([^"]+)"', p)
        tgt = re.search(r'Target="([^"]+)"', p)
        if rid and tgt:
            rid_to_target[rid.group(1)] = tgt.group(1)
    name_to_part = {}
    for m in re.finditer(r'<sheet\b[^>]*?/>', wb):
        tag = m.group(0)
        nm = re.search(r'name="([^"]+)"', tag)
        rid = re.search(r'r:id="([^"]+)"', tag)
        if nm and rid and rid.group(1) in rid_to_target:
            tgt = rid_to_target[rid.group(1)].lstrip("/")
            if not tgt.startswith("xl/"):
                tgt = "xl/" + tgt
            name_to_part[nm.group(1)] = tgt
    return name_to_part


def main(orig_path, out_path):
    with zipfile.ZipFile(orig_path) as oz:
        orig_names = set(oz.namelist())
        media = {n: oz.read(n) for n in orig_names if n.startswith("xl/media/")}
        drawings = {n: oz.read(n) for n in orig_names
                    if n.startswith("xl/drawings/") and n.endswith(".xml")}
        draw_rels = {n: oz.read(n) for n in orig_names
                     if n.startswith("xl/drawings/_rels/")}
        # which sheet name owns which drawing (via sheet rels in ORIGINAL)
        oname2part = sheet_name_to_part(oz)
        part2name = {v: k for k, v in oname2part.items()}
        sheet_drawing = {}  # sheet display name -> drawing target (e.g. drawing1.xml)
        for n in orig_names:
            m = re.match(r"xl/worksheets/_rels/(sheet\d+)\.xml\.rels", n)
            if not m:
                continue
            rels = oz.read(n).decode("utf-8")
            dm = re.search(r'Target="\.\./drawings/(drawing\d+\.xml)"', rels)
            if dm:
                part = "xl/worksheets/%s.xml" % m.group(1)
                nm = part2name.get(part)
                if nm:
                    sheet_drawing[nm] = dm.group(1)

    if not media and not drawings:
        print("nothing to graft")
        return

    with zipfile.ZipFile(out_path) as tz:
        tnames = tz.namelist()
        tdata = {n: tz.read(n) for n in tnames}
        tname2part = sheet_name_to_part(tz)

    # ---- patch [Content_Types].xml ----
    ct = tdata["[Content_Types].xml"].decode("utf-8")
    inserts = []
    if "png" not in ct and 'Extension="png"' not in ct:
        inserts.append('<Default Extension="png" ContentType="image/png"/>')
    if 'Extension="svg"' not in ct and any(m.endswith(".svg") for m in media):
        inserts.append('<Default Extension="svg" ContentType="image/svg+xml"/>')
    if 'Extension="jpeg"' not in ct and any(m.endswith((".jpg", ".jpeg")) for m in media):
        inserts.append('<Default Extension="jpeg" ContentType="image/jpeg"/>')
    if 'Extension="emf"' not in ct and any(m.endswith(".emf") for m in media):
        inserts.append('<Default Extension="emf" ContentType="image/x-emf"/>')
    for d in drawings:
        part = "/" + d
        if part not in ct:
            inserts.append('<Override PartName="%s" ContentType="%s"/>' % (part, DRAW_CT))
    if inserts:
        ct = ct.replace("</Types>", "".join(inserts) + "</Types>")
        tdata["[Content_Types].xml"] = ct.encode("utf-8")

    # ---- force full recalc on open (openpyxl writes formulas w/o cached values)
    wbxml = tdata["xl/workbook.xml"].decode("utf-8")
    if "<calcPr" in wbxml and "fullCalcOnLoad" not in wbxml:
        wbxml = re.sub(r"<calcPr\b", '<calcPr fullCalcOnLoad="1"', wbxml, count=1)
        tdata["xl/workbook.xml"] = wbxml.encode("utf-8")

    # ---- add media + drawing parts ----
    for n, b in {**media, **drawings, **draw_rels}.items():
        tdata[n] = b

    # ---- wire each drawing into its sheet (by name) ----
    for sheet_name, draw_xml in sheet_drawing.items():
        part = tname2part.get(sheet_name)
        if not part:
            print("WARN: sheet %r not found in output" % sheet_name)
            continue
        base = part.split("/")[-1].replace(".xml", "")  # sheetN
        rels_part = "xl/worksheets/_rels/%s.xml.rels" % base
        sx = tdata[part].decode("utf-8")
        existing_rels = tdata.get(rels_part, b"").decode("utf-8")
        # Idempotency: if this sheet already references a drawing (element present
        # or the target already wired in its rels), skip — re-running must not
        # append a duplicate/orphaned relationship.
        if "<drawing " in sx or ('Target="../drawings/%s"' % draw_xml) in existing_rels:
            print("skip %s -> sheet %r (already grafted)" % (draw_xml, sheet_name))
            continue
        # build/extend the sheet rels with a drawing relationship
        if rels_part in tdata:
            rels = existing_rels
            used = [int(x) for x in re.findall(r'Id="rId(\d+)"', rels)]
            rid = "rId%d" % (max(used) + 1 if used else 1)
            rel = '<Relationship Id="%s" Type="%s" Target="../drawings/%s"/>' % (
                rid, DRAW_REL, draw_xml)
            rels = rels.replace("</Relationships>", rel + "</Relationships>")
        else:
            rid = "rId1"
            rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/'
                    'package/2006/relationships">'
                    '<Relationship Id="%s" Type="%s" Target="../drawings/%s"/>'
                    '</Relationships>') % (rid, DRAW_REL, draw_xml)
        tdata[rels_part] = rels.encode("utf-8")
        # insert <drawing r:id=.../> just before </worksheet>.
        # The r: prefix must be bound: openpyxl omits xmlns:r on worksheets that
        # had no relationships, so declare it on the <worksheet> root if absent.
        if "xmlns:r=" not in sx.split(">", 1)[0]:
            sx = sx.replace(
                "<worksheet ",
                '<worksheet xmlns:r="http://schemas.openxmlformats.org/'
                'officeDocument/2006/relationships" ', 1)
        sx = sx.replace("</worksheet>", '<drawing r:id="%s"/></worksheet>' % rid)
        tdata[part] = sx.encode("utf-8")
        print("grafted %s -> sheet %r (%s) as %s" % (draw_xml, sheet_name, part, rid))

    # ---- rewrite the zip ----
    tmp = out_path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, b in tdata.items():
            zf.writestr(n, b)
    shutil.move(tmp, out_path)
    print("media graft complete:", out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
