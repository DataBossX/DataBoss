"""Surgical .xlsx repair — Phase 3 (xml_surgeon).

An ``.xlsx`` is a ZIP of XML parts (plus embedded drawings and media). openpyxl
round-trips lose formatting, drawings, and print settings, which is
unacceptable for a title report the Examiner will sign. So we operate on the
archive directly:

* ``ArchiveManager`` unzips every part into memory, lets callers replace or
  drop specific parts by name, and repacks — copying untouched parts byte for
  byte so embedded media and drawings are never re-encoded or dropped.

* ``CalcChainDestroyer`` removes ``xl/calcChain.xml`` (a stale calc chain is
  the usual cause of ``#REF!`` cascades) and sets ``fullCalcOnLoad="1"`` in
  ``xl/workbook.xml`` so the next open recomputes every formula. It also
  scrubs the now-dangling relationship and content-type override, so the file
  stays valid.

* ``XMLPatcher`` applies lxml edits to a single worksheet part — setting a
  cell's formula and clearing its cached value — without touching any other
  part of the file architecture.

Every write goes to a *new* path chosen by the VersionController; this module
never overwrites its input.
"""

from __future__ import annotations

import io
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lxml import etree

# SpreadsheetML namespaces.
_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_NSMAP_MAIN = {"m": _NS_MAIN}

_CALC_CHAIN_PART = "xl/calcChain.xml"
_WORKBOOK_PART = "xl/workbook.xml"
_WORKBOOK_RELS_PART = "xl/_rels/workbook.xml.rels"
_CONTENT_TYPES_PART = "[Content_Types].xml"


class SurgeonError(RuntimeError):
    """Base error for archive surgery."""


# --------------------------------------------------------------------------- #
# ArchiveManager
# --------------------------------------------------------------------------- #


@dataclass
class Archive:
    """An .xlsx unpacked into memory: ordered part-name -> bytes."""

    parts: dict[str, bytes] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)

    def has(self, name: str) -> bool:
        return name in self.parts

    def read(self, name: str) -> bytes:
        try:
            return self.parts[name]
        except KeyError as exc:
            raise SurgeonError(f"part not found in archive: {name}") from exc

    def replace(self, name: str, data: bytes) -> None:
        if name not in self.parts:
            self.order.append(name)
        self.parts[name] = data

    def drop(self, name: str) -> bool:
        if name in self.parts:
            del self.parts[name]
            self.order.remove(name)
            return True
        return False


class ArchiveManager:
    """Loads, mutates, and repacks .xlsx archives without corrupting them."""

    def load(self, path: Path) -> Archive:
        """Read every part of ``path`` into memory, preserving order."""
        archive = Archive()
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                archive.parts[info.filename] = zf.read(info.filename)
                archive.order.append(info.filename)
        return archive

    def save(self, archive: Archive, dest: Path) -> Path:
        """Write ``archive`` to ``dest``. Refuses to overwrite an existing
        file — versioning, not clobbering."""
        if dest.exists():
            raise SurgeonError(f"refusing to overwrite existing file: {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp then move, so a crash mid-write leaves no half file
        # at the real path.
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in archive.order:
                data = archive.parts[name]
                # Media/drawings compress poorly and are already compressed;
                # store them without extra deflate to avoid bloat/CPU while
                # keeping bytes identical.
                compress = (
                    zipfile.ZIP_STORED
                    if name.startswith(("xl/media/", "xl/embeddings/"))
                    else zipfile.ZIP_DEFLATED
                )
                zf.writestr(name, data, compress_type=compress)
        shutil.move(str(tmp), str(dest))
        return dest


# --------------------------------------------------------------------------- #
# CalcChainDestroyer
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CalcChainResult:
    calc_chain_removed: bool
    full_calc_on_load_set: bool
    rels_scrubbed: bool
    content_type_scrubbed: bool


class CalcChainDestroyer:
    """Removes the calc chain and forces a full recalculation on next open."""

    def destroy(self, archive: Archive) -> CalcChainResult:
        removed = archive.drop(_CALC_CHAIN_PART)
        full_calc = self._set_full_calc_on_load(archive)
        rels = self._scrub_rels(archive)
        ct = self._scrub_content_types(archive)
        return CalcChainResult(
            calc_chain_removed=removed,
            full_calc_on_load_set=full_calc,
            rels_scrubbed=rels,
            content_type_scrubbed=ct,
        )

    def _set_full_calc_on_load(self, archive: Archive) -> bool:
        if not archive.has(_WORKBOOK_PART):
            return False
        root = etree.fromstring(archive.read(_WORKBOOK_PART))
        calc_pr = root.find(f"{{{_NS_MAIN}}}calcPr")
        if calc_pr is None:
            # CT_Workbook is an ordered sequence: calcPr must precede oleSize,
            # customWorkbookViews, pivotCaches, smartTagPr/Types, webPublishing,
            # fileRecoveryPr, webPublishObjects, and extLst. Appending at the end
            # would put it after any of those and produce a schema-invalid file
            # that Excel "repairs" on open. Insert before the first such element.
            calc_pr = etree.Element(f"{{{_NS_MAIN}}}calcPr")
            anchor = None
            for tag in ("oleSize", "customWorkbookViews", "pivotCaches",
                        "smartTagPr", "smartTagTypes", "webPublishing",
                        "fileRecoveryPr", "webPublishObjects", "extLst"):
                found = root.find(f"{{{_NS_MAIN}}}{tag}")
                if found is not None:
                    anchor = found
                    break
            if anchor is not None:
                anchor.addprevious(calc_pr)
            else:
                root.append(calc_pr)
        calc_pr.set("fullCalcOnLoad", "1")
        calc_pr.set("calcId", "0")  # force a recompute; 0 == "unknown engine"
        archive.replace(_WORKBOOK_PART, self._serialize(root))
        return True

    def _scrub_rels(self, archive: Archive) -> bool:
        """Remove the workbook->calcChain relationship if present."""
        if not archive.has(_WORKBOOK_RELS_PART):
            return False
        root = etree.fromstring(archive.read(_WORKBOOK_RELS_PART))
        changed = False
        for rel in list(root):
            target = rel.get("Target", "")
            if target.endswith("calcChain.xml"):
                root.remove(rel)
                changed = True
        if changed:
            archive.replace(_WORKBOOK_RELS_PART, self._serialize(root))
        return changed

    def _scrub_content_types(self, archive: Archive) -> bool:
        """Remove the calcChain override from [Content_Types].xml."""
        if not archive.has(_CONTENT_TYPES_PART):
            return False
        root = etree.fromstring(archive.read(_CONTENT_TYPES_PART))
        changed = False
        for override in list(root):
            part = override.get("PartName", "")
            if part.endswith("/calcChain.xml"):
                root.remove(override)
                changed = True
        if changed:
            archive.replace(_CONTENT_TYPES_PART, self._serialize(root))
        return changed

    @staticmethod
    def _serialize(root: etree._Element) -> bytes:
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


# --------------------------------------------------------------------------- #
# XMLPatcher
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PatchResult:
    part: str
    cell: str
    formula: str
    created_cell: bool


class XMLPatcher:
    """Applies targeted lxml edits to a single worksheet part.

    The only mutation it performs is setting a cell's formula and clearing its
    cached ``<v>`` so the value is recomputed. It creates the cell (and its
    row) if missing, inserting each in correct column/row order so the sheet
    stays schema-valid. Nothing outside the addressed cell is touched.
    """

    def set_cell_formula(self, sheet_xml: bytes, cell_ref: str, formula: str) -> tuple[bytes, bool]:
        """Return (patched_xml, created_cell). ``formula`` is written without a
        leading '='. ``cell_ref`` is A1-style, e.g. ``"F14"``."""
        col, row = self._split_ref(cell_ref)
        root = etree.fromstring(sheet_xml)
        sheet_data = root.find(f"{{{_NS_MAIN}}}sheetData")
        if sheet_data is None:
            raise SurgeonError("worksheet has no <sheetData>")

        row_el = self._find_or_create_row(sheet_data, row)
        cell_el, created = self._find_or_create_cell(row_el, cell_ref, col)

        # Clear any cached value and inline string; drop 't' (type) so the
        # recomputed numeric result is interpreted correctly.
        for tag in ("v", "is"):
            existing = cell_el.find(f"{{{_NS_MAIN}}}{tag}")
            if existing is not None:
                cell_el.remove(existing)
        if cell_el.get("t"):
            del cell_el.attrib["t"]

        f_el = cell_el.find(f"{{{_NS_MAIN}}}f")
        if f_el is None:
            f_el = etree.SubElement(cell_el, f"{{{_NS_MAIN}}}f")
        f_el.text = formula.lstrip("=")

        patched = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=True
        )
        return patched, created

    def _find_or_create_row(self, sheet_data: etree._Element, row: int) -> etree._Element:
        for row_el in sheet_data.findall(f"{{{_NS_MAIN}}}row"):
            r = int(row_el.get("r", "0"))
            if r == row:
                return row_el
            if r > row:
                new_row = etree.Element(f"{{{_NS_MAIN}}}row", r=str(row))
                row_el.addprevious(new_row)
                return new_row
        new_row = etree.SubElement(sheet_data, f"{{{_NS_MAIN}}}row", r=str(row))
        return new_row

    def _find_or_create_cell(
        self, row_el: etree._Element, cell_ref: str, col: str
    ) -> tuple[etree._Element, bool]:
        col_idx = self._col_to_index(col)
        for cell_el in row_el.findall(f"{{{_NS_MAIN}}}c"):
            ref = cell_el.get("r", "")
            existing_col = self._split_ref(ref)[0]
            if ref == cell_ref:
                return cell_el, False
            if self._col_to_index(existing_col) > col_idx:
                new_cell = etree.Element(f"{{{_NS_MAIN}}}c", r=cell_ref)
                cell_el.addprevious(new_cell)
                return new_cell, True
        new_cell = etree.SubElement(row_el, f"{{{_NS_MAIN}}}c", r=cell_ref)
        return new_cell, True

    @staticmethod
    def _split_ref(cell_ref: str) -> tuple[str, int]:
        col = "".join(c for c in cell_ref if c.isalpha())
        digits = "".join(c for c in cell_ref if c.isdigit())
        if not col or not digits:
            raise SurgeonError(f"invalid cell reference: {cell_ref!r}")
        return col.upper(), int(digits)

    @staticmethod
    def _col_to_index(col: str) -> int:
        idx = 0
        for ch in col.upper():
            idx = idx * 26 + (ord(ch) - ord("A") + 1)
        return idx
