"""Drawing-preserving OOXML writer (Component 6).

HARD RULE: never write the workbook with openpyxl — it silently drops embedded
drawings, the Overview SVG map, and threaded comments on save. All mutations go
through zip+lxml surgery here, which repackages every part byte-for-byte except
the ones it deliberately edits, and asserts media/drawings/comments are
untouched.

Also handles the two OOXML recalc chores: dropping ``calcChain.xml`` and setting
``fullCalcOnLoad`` so downstream consumers recompute.
"""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from typing import Any, Optional, Union

from lxml import etree

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_RNS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CTNS = "http://schemas.openxmlformats.org/package/2006/content-types"
_ORNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

CellValue = Union[str, int, float, None]

_PROTECTED = ("media", "drawing", "comment", "printerSettings", "theme")


def _q(tag: str) -> str:
    return f"{{{_NS}}}{tag}"


def _col_to_num(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def _num_to_col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _split(coord: str) -> tuple[str, int]:
    m = re.match(r"([A-Z]+)(\d+)$", coord)
    if not m:
        raise ValueError(f"bad coord {coord!r}")
    return m.group(1), int(m.group(2))


class XmlWorkbook:
    """In-memory OOXML editor. Open -> set cells/fills -> save_as(new version)."""

    def __init__(self, path: Path) -> None:
        self._src = Path(path)
        self._zin = zipfile.ZipFile(self._src)
        self._names = self._zin.namelist()
        self._modified: dict[str, bytes] = {}
        self._dropped: set[str] = set()
        self._sheet_part = self._map_sheets()
        self._styles = etree.fromstring(self._zin.read("xl/styles.xml"))
        self._yellow_fill_id: Optional[int] = None

    # -- factory ---------------------------------------------------------- #
    @classmethod
    def open(cls, path: str | Path) -> "XmlWorkbook":
        return cls(Path(path))

    # -- sheet mapping ---------------------------------------------------- #
    def _map_sheets(self) -> dict[str, str]:
        wb = etree.fromstring(self._zin.read("xl/workbook.xml"))
        rels = etree.fromstring(self._zin.read("xl/_rels/workbook.xml.rels"))
        relmap = {r.get("Id"): r.get("Target")
                  for r in rels.iter(f"{{{_RNS}}}Relationship")}
        out: dict[str, str] = {}
        for sh in wb.iter(_q("sheet")):
            rid = sh.get(f"{{{_ORNS}}}id")
            target = relmap[rid]
            part = "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
            out[sh.get("name")] = part
        return out

    def _sheet_root(self, sheet: str) -> etree._Element:
        part = self._sheet_part[sheet]
        data = self._modified.get(part) or self._zin.read(part)
        return etree.fromstring(data)

    def _store_sheet(self, sheet: str, root: etree._Element) -> None:
        part = self._sheet_part[sheet]
        self._modified[part] = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=True
        )

    # -- cell writing ----------------------------------------------------- #
    def set_cell(self, sheet: str, coord: str, value: CellValue) -> None:
        root = self._sheet_root(sheet)
        sdata = root.find(_q("sheetData"))
        col_letter, rnum = _split(coord)
        self._unshare_intersecting(sdata, coord)
        row = self._get_or_make_row(sdata, rnum)
        cell = self._get_or_make_cell(row, coord, col_letter)
        for child in list(cell):
            cell.remove(child)
        cell.attrib.pop("t", None)
        if value is None:
            pass
        elif isinstance(value, bool):
            cell.set("t", "b")
            etree.SubElement(cell, _q("v")).text = str(int(value))
        elif isinstance(value, (int, float)):
            etree.SubElement(cell, _q("v")).text = repr(value)
        elif isinstance(value, str) and value.startswith("="):
            etree.SubElement(cell, _q("f")).text = value[1:]
        else:
            cell.set("t", "inlineStr")
            is_ = etree.SubElement(cell, _q("is"))
            t = etree.SubElement(is_, _q("t"))
            t.text = str(value)
            if str(value) != str(value).strip() or "\n" in str(value):
                t.set(_XML_SPACE, "preserve")
        self._store_sheet(sheet, root)

    # -- highlight (style) ------------------------------------------------ #
    def set_highlight(self, sheet: str, coord: str, on: bool) -> None:
        fill_id = self._ensure_yellow_fill() if on else 0
        root = self._sheet_root(sheet)
        sdata = root.find(_q("sheetData"))
        col_letter, rnum = _split(coord)
        row = self._get_or_make_row(sdata, rnum)
        cell = self._get_or_make_cell(row, coord, col_letter)
        s_idx = int(cell.get("s", "0"))
        cell.set("s", str(self._clone_xf_with_fill(s_idx, fill_id)))
        self._store_sheet(sheet, root)

    # -- recalc chores ---------------------------------------------------- #
    def drop_calc_chain(self) -> None:
        self._dropped.add("xl/calcChain.xml")
        ct = etree.fromstring(self._zin.read("[Content_Types].xml"))
        for ov in ct.findall(f"{{{_CTNS}}}Override"):
            if ov.get("PartName") == "/xl/calcChain.xml":
                ct.remove(ov)
        self._modified["[Content_Types].xml"] = etree.tostring(
            ct, xml_declaration=True, encoding="UTF-8", standalone=True
        )
        rels = etree.fromstring(self._zin.read("xl/_rels/workbook.xml.rels"))
        for r in list(rels.iter(f"{{{_RNS}}}Relationship")):
            if (r.get("Target") or "").endswith("calcChain.xml"):
                r.getparent().remove(r)
        self._modified["xl/_rels/workbook.xml.rels"] = etree.tostring(
            rels, xml_declaration=True, encoding="UTF-8", standalone=True
        )

    def force_full_calc(self) -> None:
        wb = etree.fromstring(self._modified.get("xl/workbook.xml")
                              or self._zin.read("xl/workbook.xml"))
        calc = wb.find(_q("calcPr"))
        if calc is None:
            calc = etree.SubElement(wb, _q("calcPr"))
        calc.set("fullCalcOnLoad", "1")
        calc.attrib.pop("calcId", None)
        self._modified["xl/workbook.xml"] = etree.tostring(
            wb, xml_declaration=True, encoding="UTF-8", standalone=True
        )

    # -- save ------------------------------------------------------------- #
    def save_as(self, dst: str | Path) -> Path:
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        self._modified["xl/styles.xml"] = etree.tostring(
            self._styles, xml_declaration=True, encoding="UTF-8", standalone=True
        )
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            # Write by filename (fresh ZipInfo) — reusing Excel's ZipInfo objects
            # copies flag bits/data-descriptor markers that corrupt the archive.
            for item in self._zin.infolist():
                if item.filename in self._dropped:
                    continue
                data = self._modified.pop(item.filename, None)
                if data is None:
                    data = self._zin.read(item.filename)
                zout.writestr(item.filename, data)
            for name, data in self._modified.items():
                zout.writestr(name, data)
        self._assert_protected_identical(dst)
        return dst

    def _assert_protected_identical(self, dst: Path) -> None:
        with zipfile.ZipFile(dst) as zo:
            names = set(zo.namelist())
            for n in self._zin.namelist():
                if n in self._dropped or n not in names:
                    continue
                if any(k in n for k in _PROTECTED):
                    if self._zin.read(n) != zo.read(n):
                        raise AssertionError(f"protected part mutated: {n}")

    # -- internals -------------------------------------------------------- #
    def _get_or_make_row(self, sdata, rnum: int):
        rows = {int(r.get("r")): r for r in sdata.findall(_q("row"))}
        if rnum in rows:
            return rows[rnum]
        row = etree.Element(_q("row"), r=str(rnum))
        lower = [n for n in rows if n < rnum]
        if lower:
            rows[max(lower)].addnext(row)
        else:
            sdata.insert(0, row)
        return row

    def _get_or_make_cell(self, row, coord: str, col_letter: str):
        for c in row.findall(_q("c")):
            if c.get("r") == coord:
                return c
        cell = etree.Element(_q("c"), r=coord)
        target = _col_to_num(col_letter)
        placed = False
        for sib in row.findall(_q("c")):
            if _col_to_num(_split(sib.get("r"))[0]) > target:
                sib.addprevious(cell)
                placed = True
                break
        if not placed:
            row.append(cell)
        return cell

    def _unshare_intersecting(self, sdata, coord: str) -> None:
        col_letter, rnum = _split(coord)
        tgt_c, tgt_r = _col_to_num(col_letter), rnum
        shared: dict[str, tuple[str, str, str]] = {}
        for c in sdata.iter(_q("c")):
            f = c.find(_q("f"))
            if f is not None and f.get("t") == "shared" and f.get("ref"):
                shared[f.get("si")] = (c.get("r"), f.text or "", f.get("ref"))
        for si, (hcoord, hform, ref) in shared.items():
            a, _, b = ref.partition(":")
            c1, r1 = _split(a)
            c2, r2 = _split(b or a)
            if not (_col_to_num(c1) <= tgt_c <= _col_to_num(c2) and r1 <= tgt_r <= r2):
                continue
            hc, hr = _split(hcoord)
            for c in sdata.iter(_q("c")):
                f = c.find(_q("f"))
                if f is None or f.get("si") != si or f.get("t") != "shared":
                    continue
                cc, rr = _split(c.get("r"))
                new = self._translate(hform, rr - hr, _col_to_num(cc) - _col_to_num(hc))
                for attr in ("t", "si", "ref"):
                    f.attrib.pop(attr, None)
                f.text = new

    @staticmethod
    def _translate(formula: str, dr: int, dc: int) -> str:
        ref = re.compile(r"(\$?)([A-Z]{1,3})(\$?)(\d+)")
        out, i, n = [], 0, len(formula)
        while i < n:
            ch = formula[i]
            if ch == '"':
                j = i + 1
                while j < n and formula[j] != '"':
                    j += 1
                out.append(formula[i:j + 1])
                i = j + 1
                continue
            m = ref.match(formula, i)
            if m and (i == 0 or not (formula[i - 1].isalnum() or formula[i - 1] in "_$.")):
                end = m.end()
                if end >= n or formula[end] != "(":
                    d1, col, d2, rownum = m.groups()
                    if not d1:
                        col = _num_to_col(_col_to_num(col) + dc)
                    if not d2:
                        rownum = str(int(rownum) + dr)
                    out.append(f"{d1}{col}{d2}{rownum}")
                    i = end
                    continue
            out.append(ch)
            i += 1
        return "".join(out)

    def _ensure_yellow_fill(self) -> int:
        if self._yellow_fill_id is not None:
            return self._yellow_fill_id
        fills = self._styles.find(_q("fills"))
        for idx, f in enumerate(fills):
            pf = f.find(_q("patternFill"))
            if pf is not None and pf.get("patternType") == "solid":
                fg = pf.find(_q("fgColor"))
                if fg is not None and fg.get("rgb") == "FFFFFF00":
                    self._yellow_fill_id = idx
                    return idx
        nf = etree.SubElement(fills, _q("fill"))
        pf = etree.SubElement(nf, _q("patternFill"), patternType="solid")
        etree.SubElement(pf, _q("fgColor"), rgb="FFFFFF00")
        etree.SubElement(pf, _q("bgColor"), indexed="64")
        fills.set("count", str(len(fills)))
        self._yellow_fill_id = len(fills) - 1
        return self._yellow_fill_id

    def _clone_xf_with_fill(self, s_idx: int, fill_id: int) -> int:
        cellXfs = self._styles.find(_q("cellXfs"))
        src = cellXfs[s_idx]
        new = etree.fromstring(etree.tostring(src))
        new.set("fillId", str(fill_id))
        new.set("applyFill", "1")
        cellXfs.append(new)
        cellXfs.set("count", str(len(cellXfs)))
        return len(cellXfs) - 1
