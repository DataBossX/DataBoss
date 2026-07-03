"""Format-preserving workbook editor.

Writes cell values/formulas and adds/removes the yellow gap highlight by rewriting
only the affected worksheet XML parts inside the .xlsx zip. Everything else — media,
drawings, comments (legacy + threaded), styles, merges, print settings, tab order,
defined names — is copied byte-for-byte from the source. This is the mechanism that
lets an automated pass touch data without disturbing the examiner's layout.

Ops accepted (dict coord -> op):
    ("v", value)        set a literal value (str/number/date)
    ("f", formula, cached)  set a formula with a precomputed cached value
    ("clear",)          blank the cell content (keeps the grid/borders)
    ("unhighlight",)    remove a solid-yellow fill (re-point style to no-fill clone)
"""
from __future__ import annotations
import zipfile, shutil, re, copy, datetime
from lxml import etree
import openpyxl
from openpyxl.utils import column_index_from_string
from openpyxl.utils.datetime import to_excel

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RNS = "http://schemas.openxmlformats.org/package/2006/relationships"
ONS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
def q(t): return f"{{{NS}}}{t}"


class SurgicalEditor:
    def __init__(self, src_path: str):
        self.src = src_path
        self.zin = zipfile.ZipFile(src_path)
        self._map_sheets()
        self._load_styles()
        self.newparts: dict[str, bytes] = {}

    def _map_sheets(self):
        wbx = etree.fromstring(self.zin.read("xl/workbook.xml"))
        rels = etree.fromstring(self.zin.read("xl/_rels/workbook.xml.rels"))
        relmap = {r.get("Id"): r.get("Target")
                  for r in rels.iter(f"{{{RNS}}}Relationship")}
        self.sheetpath = {}
        for s in wbx.iter(q("sheet")):
            tgt = relmap[s.get(f"{{{ONS}}}id")]
            self.sheetpath[s.get("name")] = "xl/" + tgt.lstrip("/")

    def _load_styles(self):
        self.styles = etree.fromstring(self.zin.read("xl/styles.xml"))
        self.cellXfs = self.styles.find(q("cellXfs"))
        self.xfs = list(self.cellXfs)
        self.fills = list(self.styles.find(q("fills")))
        self._noyellow_cache = {}
        self.styles_changed = False

    def _fill_is_yellow(self, fid):
        f = self.fills[fid]
        pf = f.find(q("patternFill"))
        if pf is None:
            return False
        fg = pf.find(q("fgColor"))
        return pf.get("patternType") == "solid" and fg is not None and fg.get("rgb") == "FFFFFF00"

    def _noyellow_xf(self, sidx, target_fill=0):
        key = (sidx, target_fill)
        if key in self._noyellow_cache:
            return self._noyellow_cache[key]
        clone = copy.deepcopy(self.xfs[sidx])
        clone.set("fillId", str(target_fill))
        self.cellXfs.append(clone)
        self.xfs.append(clone)
        self.cellXfs.set("count", str(len(self.xfs)))
        self._noyellow_cache[key] = len(self.xfs) - 1
        self.styles_changed = True
        return len(self.xfs) - 1

    # ---- XML cell helpers ----
    def _root(self, sheet):
        path = self.sheetpath[sheet]
        return etree.fromstring(self.newparts.get(path) or self.zin.read(path))

    def _save_root(self, sheet, root):
        self.newparts[self.sheetpath[sheet]] = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=True)

    @staticmethod
    def _get_cell(root, coord):
        r = int(re.match(r"[A-Z]+(\d+)", coord).group(1))
        sd = root.find(q("sheetData"))
        for rowel in sd.iterfind(q("row")):
            if int(rowel.get("r")) == r:
                for cel in rowel.iterfind(q("c")):
                    if cel.get("r") == coord:
                        return cel
        return None

    def _ensure_cell(self, root, coord):
        col = re.match(r"([A-Z]+)", coord).group(1)
        rnum = int(re.match(r"[A-Z]+(\d+)", coord).group(1))
        ci = column_index_from_string(col)
        sd = root.find(q("sheetData"))
        rowel = prev = None
        for rl in sd.iterfind(q("row")):
            rn = int(rl.get("r"))
            if rn == rnum:
                rowel = rl; break
            if rn > rnum: break
            prev = rl
        if rowel is None:
            rowel = etree.Element(q("row")); rowel.set("r", str(rnum))
            idx = list(sd).index(prev) + 1 if prev is not None else 0
            sd.insert(idx, rowel)
        cel = prevc = None
        for cl in rowel.iterfind(q("c")):
            cc = column_index_from_string(re.match(r"([A-Z]+)", cl.get("r")).group(1))
            if cl.get("r") == coord:
                cel = cl; break
            if cc > ci: break
            prevc = cl
        if cel is None:
            cel = etree.Element(q("c")); cel.set("r", coord)
            sref = None
            for rr in range(rnum - 1, max(rnum - 6, 0), -1):
                e = self._get_cell(root, f"{col}{rr}")
                if e is not None and e.get("s"):
                    sref = e.get("s"); break
            if sref is None and prevc is not None and prevc.get("s"):
                sref = prevc.get("s")
            if sref:
                cel.set("s", sref)
            idx = list(rowel).index(prevc) + 1 if prevc is not None else 0
            rowel.insert(idx, cel)
        return cel

    def apply(self, sheet: str, coord: str, op: tuple):
        root = self._root(sheet)
        kind = op[0]
        if kind == "unhighlight":
            cel = self._get_cell(root, coord)
            if cel is not None:
                sidx = int(cel.get("s", "0"))
                if self._fill_is_yellow(int(self.xfs[sidx].get("fillId", "0"))):
                    cel.set("s", str(self._noyellow_xf(sidx, 0)))
            self._save_root(sheet, root)
            return
        cel = self._ensure_cell(root, coord)
        for child in list(cel):
            cel.remove(child)
        cel.attrib.pop("t", None)
        if kind == "clear":
            pass
        elif kind == "v":
            self._write_value(cel, op[1])
        elif kind == "f":
            f_el = etree.SubElement(cel, q("f")); f_el.text = op[1].lstrip("=")
            cached = op[2] if len(op) > 2 else None
            if isinstance(cached, str):
                cel.set("t", "str"); etree.SubElement(cel, q("v")).text = cached
            elif cached is not None:
                etree.SubElement(cel, q("v")).text = repr(cached)
        self._save_root(sheet, root)

    @staticmethod
    def _write_value(cel, v):
        if isinstance(v, (datetime.datetime, datetime.date)):
            etree.SubElement(cel, q("v")).text = repr(to_excel(v))
        elif isinstance(v, bool):
            cel.set("t", "b"); etree.SubElement(cel, q("v")).text = "1" if v else "0"
        elif isinstance(v, (int, float)):
            etree.SubElement(cel, q("v")).text = repr(v)
        else:
            cel.set("t", "inlineStr")
            is_el = etree.SubElement(cel, q("is"))
            t_el = etree.SubElement(is_el, q("t")); t_el.text = str(v)
            t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    def force_recalc(self):
        wbroot = etree.fromstring(self.zin.read("xl/workbook.xml"))
        calc = wbroot.find(q("calcPr")) or etree.SubElement(wbroot, q("calcPr"))
        calc.set("fullCalcOnLoad", "1")
        self.newparts["xl/workbook.xml"] = etree.tostring(
            wbroot, xml_declaration=True, encoding="UTF-8", standalone=True)

    def save(self, out_path: str):
        self.force_recalc()
        if self.styles_changed:
            self.newparts["xl/styles.xml"] = etree.tostring(
                self.styles, xml_declaration=True, encoding="UTF-8", standalone=True)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in self.zin.infolist():
                data = self.newparts.get(item.filename) or self.zin.read(item.filename)
                zi = zipfile.ZipInfo(item.filename, date_time=item.date_time)
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = item.external_attr
                zout.writestr(zi, data)
        return out_path
