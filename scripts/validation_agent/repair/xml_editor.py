"""Safe XML workbook editor.

Operates ONLY on a copied, versioned workbook. Extracts the XLSX/XLSM ZIP,
edits specific cell XML nodes with lxml, preserves every unrelated entry
(drawings, media, styles, shared strings, relationships, VBA project),
removes ``xl/calcChain.xml`` after formula edits, sets ``fullCalcOnLoad``, and
repackages as a NEW version file. Hashes before and after; verifies the output
is a valid ZIP and a loadable workbook. Never repairs legal/title/source facts.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from lxml import etree

from core.run_manager import sha256_file

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


class XMLEditError(RuntimeError):
    pass


class XMLWorkbookEditor:
    def __init__(self, source_version_path: str | Path):
        self.source = Path(source_version_path)
        if not self.source.exists():
            raise FileNotFoundError(self.source)
        self.source_hash = sha256_file(self.source)
        self._tmp: Optional[Path] = None
        self._formula_edited = False
        self._changes: list[dict] = []

    # ------------------------------------------------------------------ #
    def __enter__(self) -> "XMLWorkbookEditor":
        self._tmp = Path(tempfile.mkdtemp(prefix="dbx_xml_"))
        with zipfile.ZipFile(self.source) as zf:
            self._names = zf.namelist()  # preserve original order
            zf.extractall(self._tmp)
        return self

    def __exit__(self, *exc) -> None:
        if self._tmp and self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)

    # ------------------------------------------------------------------ #
    def _sheet_xml_path(self, sheet_name: str) -> Path:
        wb_xml = self._tmp / "xl" / "workbook.xml"
        rels_xml = self._tmp / "xl" / "_rels" / "workbook.xml.rels"
        wb = etree.parse(str(wb_xml))
        rid = None
        for sheet in wb.iter(f"{{{_MAIN_NS}}}sheet"):
            if sheet.get("name") == sheet_name:
                rid = sheet.get(f"{{{_REL_NS}}}id")
                break
        if rid is None:
            raise XMLEditError(f"Sheet not found in workbook.xml: {sheet_name}")
        rels = etree.parse(str(rels_xml))
        target = None
        for rel in rels.iter(f"{{{_PKG_REL_NS}}}Relationship"):
            if rel.get("Id") == rid:
                target = rel.get("Target")
                break
        if target is None:
            raise XMLEditError(f"No relationship target for {rid}")
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        return self._tmp / target

    def set_cell_formula(self, sheet_name: str, coord: str, formula: str) -> None:
        """Replace a cell's contents with a formula (formula without '=')."""
        formula = formula.lstrip("=")
        sheet_path = self._sheet_xml_path(sheet_name)
        tree = etree.parse(str(sheet_path))
        root = tree.getroot()
        target_cell = None
        for c in root.iter(f"{{{_MAIN_NS}}}c"):
            if c.get("r") == coord:
                target_cell = c
                break
        if target_cell is None:
            raise XMLEditError(
                f"Cell {coord} not found on sheet {sheet_name}; refusing to "
                f"invent a cell."
            )
        before = etree.tostring(target_cell, encoding="unicode")
        # Remove any existing value/formula/type; a formula cell has no 't'.
        if "t" in target_cell.attrib:
            del target_cell.attrib["t"]
        for child in list(target_cell):
            target_cell.remove(child)
        f_el = etree.SubElement(target_cell, f"{{{_MAIN_NS}}}f")
        f_el.text = formula
        tree.write(str(sheet_path), xml_declaration=True, encoding="UTF-8",
                   standalone=True)
        self._formula_edited = True
        self._changes.append({"sheet": sheet_name, "cell": coord,
                              "before": before, "formula": formula})

    def _remove_calc_chain(self) -> None:
        calc = self._tmp / "xl" / "calcChain.xml"
        if calc.exists():
            calc.unlink()
        # Also drop its content-type + relationship references if present.
        ct = self._tmp / "[Content_Types].xml"
        if ct.exists():
            tree = etree.parse(str(ct))
            root = tree.getroot()
            for ov in list(root):
                if ov.get("PartName") == "/xl/calcChain.xml":
                    root.remove(ov)
            tree.write(str(ct), xml_declaration=True, encoding="UTF-8",
                       standalone=True)
        rels = self._tmp / "xl" / "_rels" / "workbook.xml.rels"
        if rels.exists():
            tree = etree.parse(str(rels))
            root = tree.getroot()
            for rel in list(root):
                if (rel.get("Target") or "").endswith("calcChain.xml"):
                    root.remove(rel)
            tree.write(str(rels), xml_declaration=True, encoding="UTF-8",
                       standalone=True)

    def _set_full_calc_on_load(self) -> None:
        wb_xml = self._tmp / "xl" / "workbook.xml"
        tree = etree.parse(str(wb_xml))
        root = tree.getroot()
        calc_pr = root.find(f"{{{_MAIN_NS}}}calcPr")
        if calc_pr is None:
            calc_pr = etree.SubElement(root, f"{{{_MAIN_NS}}}calcPr")
        calc_pr.set("fullCalcOnLoad", "1")
        calc_pr.set("calcId", "0")
        tree.write(str(wb_xml), xml_declaration=True, encoding="UTF-8",
                   standalone=True)

    # ------------------------------------------------------------------ #
    def save_as(self, dest_path: str | Path) -> dict:
        """Repackage into a NEW version file. Never overwrites."""
        dest = Path(dest_path)
        if dest.exists():
            raise FileExistsError(f"Refusing to overwrite version: {dest}")
        if self._formula_edited:
            self._remove_calc_chain()
            self._set_full_calc_on_load()

        # Rebuild the archive, preserving all surviving entries in order.
        surviving = [n for n in self._names
                     if (self._tmp / n).exists()]
        # Include any newly created files not in the original list.
        for p in self._tmp.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self._tmp).as_posix()
                if rel not in surviving:
                    surviving.append(rel)

        dest.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in surviving:
                zf.write(self._tmp / name, name)

        verify = self.verify(dest)
        return {
            "source": str(self.source),
            "source_hash": self.source_hash,
            "dest": str(dest),
            "dest_hash": sha256_file(dest),
            "changes": self._changes,
            "verified": verify["valid"],
            "verify_detail": verify,
        }

    @staticmethod
    def verify(path: str | Path) -> dict:
        """Verify the output is a valid ZIP and a loadable workbook."""
        path = Path(path)
        result = {"valid": False, "zip_ok": False, "openpyxl_ok": False,
                  "error": None}
        try:
            with zipfile.ZipFile(path) as zf:
                result["zip_ok"] = zf.testzip() is None and \
                    "[Content_Types].xml" in zf.namelist()
        except Exception as e:
            result["error"] = f"zip: {e}"
            return result
        try:
            import openpyxl
            keep_vba = path.suffix.lower() == ".xlsm"
            wb = openpyxl.load_workbook(path, read_only=True, keep_vba=keep_vba)
            wb.close()
            result["openpyxl_ok"] = True
        except Exception as e:
            result["error"] = f"openpyxl: {e}"
            return result
        result["valid"] = result["zip_ok"] and result["openpyxl_ok"]
        return result
