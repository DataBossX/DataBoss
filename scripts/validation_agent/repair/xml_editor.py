"""XMLWorkbookEditor -- non-destructive, ZIP/XML-level workbook repair.

Excel .xlsx files are ZIP packages of XML parts.  Repairs are applied by
rewriting *only* the specific XML nodes that need to change and copying every
other package entry (drawings, media, embedded objects, VBA) byte-for-byte, so
nothing unrelated is disturbed (Golden Law: preserve the artifact).

For each applied repair the editor:
    * injects the exact formula into the target ``<c>`` cell in the sheet XML,
    * strips ``xl/calcChain.xml`` (and its content-type / relationship refs) so
      the stale dependency chain cannot fight the new formula, and
    * sets ``fullCalcOnLoad="1"`` in ``xl/workbook.xml`` so the next open (or
      the LibreOffice headless pass) recomputes everything.

The source version is opened read-only; the result is written to a brand new
vN+1 file.  Existing versions are never mutated.
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models import RepairAction

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_CALC_CHAIN = "xl/calcChain.xml"


@dataclass
class RepairApplyResult:
    ok: bool
    dest_path: Optional[str]
    applied: list[str] = field(default_factory=list)
    applied_actions: list[RepairAction] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    error: Optional[str] = None


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _col_letters(coord: str) -> str:
    return "".join(ch for ch in coord if ch.isalpha()).upper()


def _row_number(coord: str) -> int:
    digits = "".join(ch for ch in coord if ch.isdigit())
    return int(digits) if digits else 0


def _col_index(col: str) -> int:
    idx = 0
    for ch in col:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx


class XMLWorkbookEditor:
    def apply_repairs(self, src_path: str | Path, dest_path: str | Path,
                      actions: list[RepairAction]) -> RepairApplyResult:
        from lxml import etree  # lazy import

        src = Path(src_path)
        dest = Path(dest_path)
        if not src.is_file():
            return RepairApplyResult(False, None, error=f"Source missing: {src}")
        if not actions:
            # Nothing to do; still produce the next version faithfully.
            shutil.copy2(src, dest)
            return RepairApplyResult(True, str(dest), applied=[],
                                     skipped=["no actions"])

        try:
            with zipfile.ZipFile(src) as zin:
                names = zin.namelist()
                parts: dict[str, bytes] = {n: zin.read(n) for n in names}
        except zipfile.BadZipFile as exc:
            return RepairApplyResult(False, None, error=f"Corrupt source zip: {exc}")

        result = RepairApplyResult(True, str(dest))

        # Map sheet display names -> worksheet part path.
        sheet_part = self._sheet_name_to_part(parts, etree)

        # Group actions by sheet.
        by_sheet: dict[str, list[RepairAction]] = {}
        for act in actions:
            by_sheet.setdefault(act.location.sheet, []).append(act)

        for sheet_name, sheet_actions in by_sheet.items():
            part = sheet_part.get(sheet_name)
            if not part or part not in parts:
                for a in sheet_actions:
                    result.skipped.append(f"{sheet_name}!{a.location.cell}: sheet part not found")
                continue
            new_xml, applied, applied_actions, skipped = self._edit_sheet(
                parts[part], sheet_actions, etree)
            parts[part] = new_xml
            result.applied.extend(applied)
            result.applied_actions.extend(applied_actions)
            result.skipped.extend(skipped)

        # Strip calcChain.xml + its references.
        if _CALC_CHAIN in parts:
            del parts[_CALC_CHAIN]
            parts["[Content_Types].xml"] = self._strip_calcchain_contenttype(
                parts.get("[Content_Types].xml", b""), etree)
            rels_key = "xl/_rels/workbook.xml.rels"
            if rels_key in parts:
                parts[rels_key] = self._strip_calcchain_rel(parts[rels_key], etree)

        # Force full recalculation on load.
        if "xl/workbook.xml" in parts:
            parts["xl/workbook.xml"] = self._set_full_calc(parts["xl/workbook.xml"], etree)

        # Repackage preserving all other entries.
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
                # Keep [Content_Types].xml first, as Excel expects.
                ordered = ["[Content_Types].xml"] + \
                    [n for n in names if n not in ("[Content_Types].xml", _CALC_CHAIN)]
                for name in ordered:
                    if name in parts:
                        zout.writestr(name, parts[name])
        except OSError as exc:
            return RepairApplyResult(False, None, error=f"Repack failed: {exc}")

        if not result.applied:
            result.ok = False
            result.error = "No repairs could be applied to any cell."
        return result

    # -- workbook.xml part mapping -----------------------------------------
    def _sheet_name_to_part(self, parts: dict[str, bytes], etree) -> dict[str, str]:
        mapping: dict[str, str] = {}
        wb = parts.get("xl/workbook.xml")
        rels = parts.get("xl/_rels/workbook.xml.rels")
        if not wb or not rels:
            return mapping
        wb_root = etree.fromstring(wb)
        rel_root = etree.fromstring(rels)
        rid_to_target: dict[str, str] = {}
        for rel in rel_root.findall(_q(_PKG_REL_NS, "Relationship")):
            rid_to_target[rel.get("Id")] = rel.get("Target")
        sheets_el = wb_root.find(_q(_MAIN_NS, "sheets"))
        if sheets_el is None:
            return mapping
        for sheet in sheets_el.findall(_q(_MAIN_NS, "sheet")):
            name = sheet.get("name")
            rid = sheet.get(_q(_REL_NS, "id"))
            target = rid_to_target.get(rid, "")
            if not target:
                continue
            target = target.lstrip("/")
            part = target if target.startswith("xl/") else f"xl/{target}"
            mapping[name] = part
        return mapping

    # -- sheet cell editing -------------------------------------------------
    def _edit_sheet(self, xml: bytes, actions: list[RepairAction], etree):
        root = etree.fromstring(xml)
        sheet_data = root.find(_q(_MAIN_NS, "sheetData"))
        applied: list[str] = []
        applied_actions: list[RepairAction] = []
        skipped: list[str] = []
        if sheet_data is None:
            return (xml, applied, applied_actions,
                    [f"{a.location.cell}: no sheetData" for a in actions])

        for act in actions:
            coord = act.location.cell or ""
            body = self._formula_body(act)
            if not coord or not body:
                skipped.append(f"{coord}: nothing to write")
                continue
            cell = self._find_or_create_cell(sheet_data, coord, etree)
            # A formula cell derives its type from the computed result. Any prior
            # cached type marker (s/str/inlineStr but also e/b/n) is now stale --
            # drop it unconditionally so a repaired #REF! cell isn't left t="e".
            if "t" in cell.attrib:
                del cell.attrib["t"]
            for child in list(cell):
                cell.remove(child)
            f_el = etree.SubElement(cell, _q(_MAIN_NS, "f"))
            f_el.text = body
            applied.append(f"{act.location.sheet}!{coord} <- ={body}")
            applied_actions.append(act)

        return (etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                               standalone=True), applied, applied_actions, skipped)

    @staticmethod
    def _formula_body(act: RepairAction) -> str:
        val = act.new_formula.strip()
        if act.action_type == "normalize_fraction":
            return val.lstrip("=")  # "1/8" -> Excel evaluates the division
        return val[1:] if val.startswith("=") else val

    def _find_or_create_cell(self, sheet_data, coord: str, etree):
        target_row = _row_number(coord)
        row_el = None
        for r in sheet_data.findall(_q(_MAIN_NS, "row")):
            if int(r.get("r", "0")) == target_row:
                row_el = r
                break
        if row_el is None:
            row_el = etree.Element(_q(_MAIN_NS, "row"))
            row_el.set("r", str(target_row))
            self._insert_row_in_order(sheet_data, row_el, target_row)
        for c in row_el.findall(_q(_MAIN_NS, "c")):
            if c.get("r") == coord:
                return c
        # Insert new cell keeping column order.
        cell = etree.SubElement(row_el, _q(_MAIN_NS, "c"))
        cell.set("r", coord)
        self._sort_row_cells(row_el)
        return cell

    @staticmethod
    def _insert_row_in_order(sheet_data, row_el, target_row: int) -> None:
        """Insert <row> so sheetData stays ascending by row number (Excel
        rejects out-of-order rows as a corrupt record)."""
        for existing in sheet_data.findall(_q(_MAIN_NS, "row")):
            if int(existing.get("r", "0")) > target_row:
                existing.addprevious(row_el)
                return
        sheet_data.append(row_el)

    @staticmethod
    def _sort_row_cells(row_el) -> None:
        cells = list(row_el)
        cells.sort(key=lambda c: _col_index(_col_letters(c.get("r", "A1"))))
        for c in cells:
            row_el.remove(c)
        for c in cells:
            row_el.append(c)

    # -- calcChain + calcPr surgery ----------------------------------------
    @staticmethod
    def _strip_calcchain_contenttype(xml: bytes, etree) -> bytes:
        if not xml:
            return xml
        root = etree.fromstring(xml)
        for override in root.findall(_q(_CT_NS, "Override")):
            if override.get("PartName") == "/xl/calcChain.xml":
                root.remove(override)
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                              standalone=True)

    @staticmethod
    def _strip_calcchain_rel(xml: bytes, etree) -> bytes:
        root = etree.fromstring(xml)
        for rel in root.findall(_q(_PKG_REL_NS, "Relationship")):
            target = (rel.get("Target") or "").lstrip("/")
            if target.endswith("calcChain.xml"):
                root.remove(rel)
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                              standalone=True)

    # CT_Workbook child sequence: everything that must precede <calcPr>.
    # calcPr must sit after these and before oleSize/customWorkbookViews/...
    _BEFORE_CALCPR = ("fileVersion", "fileSharing", "workbookPr",
                      "workbookProtection", "bookViews", "sheets",
                      "functionGroups", "externalReferences", "definedNames")

    @classmethod
    def _set_full_calc(cls, xml: bytes, etree) -> bytes:
        root = etree.fromstring(xml)
        calc_pr = root.find(_q(_MAIN_NS, "calcPr"))
        if calc_pr is None:
            calc_pr = etree.Element(_q(_MAIN_NS, "calcPr"))
            calc_pr.set("calcId", "0")
            # Insert in schema-valid position, not at the end (Excel is strict
            # about CT_Workbook child order; misplacement triggers repair).
            insert_at = len(root)
            before = {_q(_MAIN_NS, t) for t in cls._BEFORE_CALCPR}
            for idx, child in enumerate(root):
                if child.tag in before:
                    insert_at = idx + 1
            root.insert(insert_at, calc_pr)
        calc_pr.set("fullCalcOnLoad", "1")
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                              standalone=True)
