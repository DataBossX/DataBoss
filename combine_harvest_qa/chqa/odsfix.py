"""Post-process an ODS: set exact column widths (inches) from a profile. LibreOffice widens wide XLSX columns ~4%."""
from __future__ import annotations

import os
import shutil
import tempfile
import zipfile

from lxml import etree

from .readers import NS, _q


def set_ods_column_widths(path: str, widths_in: dict[int, float]) -> None:
    tmp = tempfile.mkdtemp(prefix="odsfix_")
    try:
        with zipfile.ZipFile(path) as z:
            members = [(i, z.read(i.filename)) for i in z.infolist()]
        content = next(b for i, b in members if i.filename == "content.xml")
        root = etree.fromstring(content)
        auto = root.find(_q("office", "automatic-styles"))
        tbl = root.xpath("//table:table", namespaces=NS)[0]
        col = 0
        for cn in tbl.xpath("./table:table-column", namespaces=NS):
            rep = int(cn.get(_q("table", "number-columns-repeated"), "1"))
            if rep == 1 and (col + 1) in widths_in:
                name = f"chqa_co{col + 1}"
                st = etree.SubElement(auto, _q("style", "style"))
                st.set(_q("style", "name"), name)
                st.set(_q("style", "family"), "table-column")
                pr = etree.SubElement(st, _q("style", "table-column-properties"))
                pr.set(_q("style", "column-width"), f"{widths_in[col + 1]:.4f}in")
                pr.set(_q("fo", "break-before"), "auto")
                cn.set(_q("table", "style-name"), name)
            col += rep
        new = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        out = path + ".tmp"
        with zipfile.ZipFile(out, "w") as zo:
            for info, data in members:
                zo.writestr(info.filename, new if info.filename == "content.xml" else data,
                            compress_type=zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED)
        os.replace(out, path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def set_ods_paper(path: str, width_in: float = 11.0, height_in: float = 8.5) -> bool:
    """Add explicit paper size to the page layout when the ODS omits it (Excel-exported ODS does; LibreOffice then
    renders A4 portrait). Operates on a COPY used only for rendering. Returns True if changed."""
    with zipfile.ZipFile(path) as z:
        members = [(i, z.read(i.filename)) for i in z.infolist()]
    styles = next(b for i, b in members if i.filename == "styles.xml")
    root = etree.fromstring(styles)
    changed = False
    for pr in root.xpath("//style:page-layout/style:page-layout-properties", namespaces=NS):
        if pr.get(_q("fo", "page-width")) is None:
            pr.set(_q("fo", "page-width"), f"{width_in}in")
            pr.set(_q("fo", "page-height"), f"{height_in}in")
            changed = True
    if changed:
        new = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        out = path + ".tmp"
        with zipfile.ZipFile(out, "w") as zo:
            for info, data in members:
                zo.writestr(info.filename, new if info.filename == "styles.xml" else data,
                            compress_type=zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED)
        os.replace(out, path)
    return changed
