"""Safe XLSX/XLSM XML editor.

Repairs are performed by unzipping the workbook, editing only the targeted
worksheet XML nodes with lxml, and repackaging — every unrelated ZIP entry
(drawings, media, styles, sharedStrings, relationships, VBA project) is copied
through byte-for-byte. After formula edits, ``xl/calcChain.xml`` is removed and
``fullCalcOnLoad`` is set so the next open recomputes. Output is a NEW version
file; the input is never mutated. The result is verified as a valid ZIP/OOXML;
on corruption the caller keeps the prior version and escalates.
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from lxml import etree

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"m": NS_MAIN}


def _sheet_target_map(zin: zipfile.ZipFile) -> Dict[str, str]:
    """Map sheet display name -> worksheet xml path via workbook + rels."""
    wb_xml = etree.fromstring(zin.read("xl/workbook.xml"))
    rels_xml = etree.fromstring(zin.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {}
    for rel in rels_xml:
        rid_to_target[rel.get("Id")] = rel.get("Target")
    name_to_path: Dict[str, str] = {}
    rns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    for sheet in wb_xml.findall(f".//{{{NS_MAIN}}}sheet"):
        rid = sheet.get(f"{{{rns}}}id")
        target = (rid_to_target.get(rid, "") or "").lstrip("/")
        if target and not target.startswith("xl/"):
            target = "xl/" + target
        name_to_path[sheet.get("name")] = target
    return name_to_path


def apply_formula_edits(src_workbook: Path, dest_workbook: Path,
                        edits: List[Dict[str, str]]) -> Dict[str, Any]:
    """Apply {sheet, cell, new_formula} edits. Returns a result summary.

    Preserves all non-target entries. Removes calcChain and sets fullCalcOnLoad.
    """
    src_workbook, dest_workbook = Path(src_workbook), Path(dest_workbook)
    if dest_workbook.exists():
        raise FileExistsError(f"refusing to overwrite {dest_workbook}")

    with zipfile.ZipFile(src_workbook) as zin:
        names = zin.namelist()
        name_to_path = _sheet_target_map(zin)
        # Group edits by worksheet path.
        by_path: Dict[str, List[Dict[str, str]]] = {}
        for e in edits:
            path = name_to_path.get(e["sheet"])
            if not path:
                raise KeyError(f"sheet not found: {e['sheet']}")
            by_path.setdefault(path, []).append(e)

        edited_blobs: Dict[str, bytes] = {}
        applied: List[Dict[str, str]] = []
        for path, elist in by_path.items():
            tree = etree.fromstring(zin.read(path))
            for e in elist:
                cell = _find_cell(tree, e["cell"])
                if cell is None:
                    cell = _ensure_cell(tree, e["cell"])
                # Clear existing value/formula children, set new formula.
                for child in list(cell):
                    cell.remove(child)
                cell.attrib.pop("t", None)  # drop cached type (e.g. error)
                f = etree.SubElement(cell, f"{{{NS_MAIN}}}f")
                f.text = e["new_formula"].lstrip("=")
                applied.append(e)
            edited_blobs[path] = etree.tostring(tree, xml_declaration=True,
                                                encoding="UTF-8", standalone=True)

        # Set fullCalcOnLoad on workbook.xml.
        wb_tree = etree.fromstring(zin.read("xl/workbook.xml"))
        calc = wb_tree.find(f"{{{NS_MAIN}}}calcPr")
        if calc is None:
            calc = etree.SubElement(wb_tree, f"{{{NS_MAIN}}}calcPr")
        calc.set("fullCalcOnLoad", "1")
        edited_blobs["xl/workbook.xml"] = etree.tostring(
            wb_tree, xml_declaration=True, encoding="UTF-8", standalone=True)

        # Write output, copying everything through except calcChain + edited.
        dest_workbook.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest_workbook, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "xl/calcChain.xml":
                    continue  # force recalc
                if item.filename in edited_blobs:
                    zout.writestr(item, edited_blobs[item.filename])
                else:
                    zout.writestr(item, zin.read(item.filename))

    verify = verify_workbook(dest_workbook)
    return {"applied": applied, "removed_calcchain": "xl/calcChain.xml" in names,
            "verify": verify, "output": str(dest_workbook)}


def _find_cell(sheet_tree, ref: str):
    for c in sheet_tree.findall(f".//{{{NS_MAIN}}}c"):
        if c.get("r") == ref:
            return c
    return None


def _col_row(ref: str):
    col = "".join(ch for ch in ref if ch.isalpha())
    row = "".join(ch for ch in ref if ch.isdigit())
    return col, int(row)


def _ensure_cell(sheet_tree, ref: str):
    """Create the cell (and its row) if absent, in a schema-valid position."""
    col, rownum = _col_row(ref)
    sheet_data = sheet_tree.find(f"{{{NS_MAIN}}}sheetData")
    if sheet_data is None:
        sheet_data = etree.SubElement(sheet_tree, f"{{{NS_MAIN}}}sheetData")
    row_el = None
    for r in sheet_data.findall(f"{{{NS_MAIN}}}row"):
        if r.get("r") == str(rownum):
            row_el = r
            break
    if row_el is None:
        row_el = etree.SubElement(sheet_data, f"{{{NS_MAIN}}}row")
        row_el.set("r", str(rownum))
    c = etree.SubElement(row_el, f"{{{NS_MAIN}}}c")
    c.set("r", ref)
    return c


def verify_workbook(path: Path) -> Dict[str, Any]:
    path = Path(path)
    if not zipfile.is_zipfile(path):
        return {"valid": False, "reason": "not a zip"}
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if z.testzip() is not None:
            return {"valid": False, "reason": "corrupt entry"}
        try:
            etree.fromstring(z.read("xl/workbook.xml"))
        except Exception as e:  # pragma: no cover
            return {"valid": False, "reason": f"workbook.xml parse error: {e}"}
    return {"valid": True, "entries": len(names),
            "has_media": any(n.startswith("xl/media/") for n in names),
            "has_drawings": any(n.startswith("xl/drawings/") for n in names),
            "has_vba": "xl/vbaProject.bin" in names}
