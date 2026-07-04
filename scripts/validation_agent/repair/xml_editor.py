"""
Safe XLSX/XLSM XML editor.

Operates only on a COPY. Reads every ZIP entry, applies targeted edits to
specific XML parts, and rewrites the archive preserving all unrelated entries
byte-for-byte (drawings, media, styles, sharedStrings, rels, vbaProject.bin).
After formula edits it removes xl/calcChain.xml and sets fullCalcOnLoad so the
consumer recalculates. Output is validated as a ZIP; on any failure the prior
version is kept and the caller escalates.

lxml is used when present; the stdlib ElementTree is the fallback.
"""
from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

try:
    from lxml import etree as ET
    _HAVE_LXML = True
except Exception:  # pragma: no cover
    import xml.etree.ElementTree as ET
    _HAVE_LXML = False

CALC_CHAIN = "xl/calcChain.xml"
WORKBOOK_XML = "xl/workbook.xml"
NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


class XmlEditError(RuntimeError):
    pass


class SafeXlsxEditor:
    """Reads a workbook's ZIP entries into memory; edits parts; repackages."""

    def __init__(self, source_path: str | Path):
        self.source_path = Path(source_path)
        if not zipfile.is_zipfile(self.source_path):
            raise XmlEditError(f"Not a ZIP workbook: {self.source_path}")
        self.entries: Dict[str, bytes] = {}
        self.order: List[str] = []
        self._load()
        self.formula_edited = False

    def _load(self) -> None:
        with zipfile.ZipFile(self.source_path) as z:
            for name in z.namelist():
                self.entries[name] = z.read(name)
                self.order.append(name)

    # ---- sheet-name -> XML part resolution (via workbook rels) ----
    def sheet_part_for(self, sheet_name: str) -> Optional[str]:
        wb_xml = self.entries.get(WORKBOOK_XML)
        rels = self.entries.get("xl/_rels/workbook.xml.rels")
        if not wb_xml or not rels:
            return None
        wroot = ET.fromstring(wb_xml)
        rid = None
        RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        for sh in wroot.iter("{%s}sheet" % NS_MAIN):
            if (sh.get("name") or "").strip() == sheet_name.strip():
                rid = sh.get("{%s}id" % RNS)
                break
        if rid is None:
            return None
        rroot = ET.fromstring(rels)
        for rel in rroot.iter("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
            if rel.get("Id") == rid:
                target = rel.get("Target")
                if target.startswith("/"):
                    return target.lstrip("/")
                return "xl/" + target.replace("../", "")
        return None

    # ---- targeted edits ----
    def set_sheet_cell_formula(self, sheet_xml_name: str, cell_ref: str, formula: str) -> bool:
        """
        Set a cell to a formula in the given sheet part (e.g. 'xl/worksheets/sheet2.xml').
        Returns True if the cell node was found and updated.
        """
        if sheet_xml_name not in self.entries:
            raise XmlEditError(f"Sheet part not found: {sheet_xml_name}")
        data = self.entries[sheet_xml_name]
        root = ET.fromstring(data)
        ns = {"m": NS_MAIN}
        found = False
        # find <c r="cell_ref">
        for c in root.iter("{%s}c" % NS_MAIN):
            if c.get("r") == cell_ref:
                # remove existing value/formula children
                for child in list(c):
                    c.remove(child)
                if "t" in c.attrib:
                    del c.attrib["t"]  # numeric result of a formula
                f = ET.SubElement(c, "{%s}f" % NS_MAIN)
                f.text = formula.lstrip("=")
                found = True
                break
        if found:
            self.entries[sheet_xml_name] = ET.tostring(root, xml_declaration=True,
                                                        encoding="UTF-8", standalone=True) \
                if _HAVE_LXML else ET.tostring(root, encoding="UTF-8", xml_declaration=True)
            self.formula_edited = True
        return found

    def remove_calc_chain(self) -> bool:
        if CALC_CHAIN in self.entries:
            del self.entries[CALC_CHAIN]
            self.order = [n for n in self.order if n != CALC_CHAIN]
            return True
        return False

    def set_full_calc_on_load(self) -> bool:
        if WORKBOOK_XML not in self.entries:
            return False
        root = ET.fromstring(self.entries[WORKBOOK_XML])
        calc = root.find("{%s}calcPr" % NS_MAIN)
        if calc is None:
            calc = ET.SubElement(root, "{%s}calcPr" % NS_MAIN)
        calc.set("fullCalcOnLoad", "1")
        self.entries[WORKBOOK_XML] = ET.tostring(root, xml_declaration=True,
                                                 encoding="UTF-8", standalone=True) \
            if _HAVE_LXML else ET.tostring(root, encoding="UTF-8", xml_declaration=True)
        return True

    # ---- repackage ----
    def save_as(self, dest_path: str | Path) -> Dict[str, str]:
        dest = Path(dest_path)
        if dest.exists():
            raise XmlEditError(f"Refusing to overwrite existing version: {dest}")
        before_hash = sha256_file(self.source_path)
        if self.formula_edited:
            self.remove_calc_chain()
            self.set_full_calc_on_load()
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        # Preserve original ordering; append any newly added entries at the end.
        names = [n for n in self.order if n in self.entries]
        for n in self.entries:
            if n not in names:
                names.append(n)
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for n in names:
                z.writestr(n, self.entries[n])
        # Validate the produced archive.
        if not zipfile.is_zipfile(tmp):
            tmp.unlink(missing_ok=True)
            raise XmlEditError("Produced file is not a valid ZIP; keeping prior version")
        with zipfile.ZipFile(tmp) as z:
            if z.testzip() is not None or "[Content_Types].xml" not in z.namelist():
                tmp.unlink(missing_ok=True)
                raise XmlEditError("Produced workbook failed structure check; rollback")
        shutil.move(str(tmp), str(dest))
        after_hash = sha256_file(dest)
        return {"before_sha256": before_hash, "after_sha256": after_hash,
                "dest": str(dest), "entries": str(len(names))}

    # ---- introspection (for tests) ----
    def entry_names(self) -> List[str]:
        return list(self.entries.keys())
