"""Build donor-matched candidates (XLSX + ODS) from any section workbook. Inputs are never modified.

Deterministic, fact-preserving: it re-styles and normalizes types, and logs every change. It never invents
values; blanks/placeholders it cannot resolve are reported in `needs_human`.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Optional

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .checks_content import ALLOWED_COMMENT, PLACEHOLDER
from .checks_format import expected_lines
from .readers import read_workbook, select_index_sheet

DATE_PATTERNS = ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y")
def inches_to_excel_width(inches: float) -> float:
    """Excel column width units for a target width in inches (7px digit, 5px padding, 96 dpi)."""
    return round((inches * 96.0 - 5.0) / 7.0, 2)


def parse_date(s: str) -> Optional[dt.date]:
    s = s.strip()
    for f in DATE_PATTERNS:
        try:
            d = dt.datetime.strptime(s, f).date()
            return d if d.year >= 1000 else None
        except ValueError:
            pass
    return None


def _border(spec: str) -> Border:
    if not spec:
        return Border()
    side = Side(style=spec.split(",")[0].split(":")[-1] or "thin", color="000000")
    return Border(left=side, right=side, top=side, bottom=side)


def _font(sig: dict, size: float) -> Font:
    return Font(name=sig.get("font") or "Calibri", size=sig.get("size") or size, bold=sig["bold"], italic=sig["italic"],
                color=(sig.get("color") or "#000000").lstrip("#"))


def _align(sig: dict) -> Alignment:
    return Alignment(horizontal=sig["h"], vertical=sig["v"], wrap_text=sig["wrap"], shrink_to_fit=sig["shrink"])


def conform(src: str, prof: dict, out_xlsx: str, *, sheet_name: Optional[str] = None, font_size: float = 11.0, metadata: Optional[dict[str, Any]] = None,
            make_ods: bool = True) -> dict:
    """Returns the change report. `metadata` maps row label -> value (e.g. {"Date:": date(2026,10,20)})."""
    wbin = read_workbook(src)
    sh = select_index_sheet(wbin, sheet_name)
    hr = prof["header_row"]
    headers = [c["header"] for c in prof["columns"]]
    changes: list[dict] = []
    needs_human: list[dict] = []

    def log(kind: str, ref: str, before: Any, after: Any) -> None:
        changes.append({"kind": kind, "cell": ref, "before": None if before is None else str(before), "after": None if after is None else str(after)})

    # locate header row in source (may differ) and map source columns by header text
    src_hr = next((r for r in range(1, 40) if "Document Type" in [str(sh.get(r, c).value or "").strip() for c in range(1, sh.max_col + 1)]), None)
    if src_hr is None:
        raise ValueError("source has no 'Document Type' header row; cannot map columns")
    colmap: dict[str, int] = {}
    for c in range(1, sh.max_col + 1):
        t = str(sh.get(src_hr, c).value or "").strip()
        if t in headers and t not in colmap:
            colmap[t] = c
    for h in headers:
        if h not in colmap:
            needs_human.append({"cell": f"header {h}", "issue": "column missing in source"})
    for c in range(1, sh.max_col + 1):
        t = str(sh.get(src_hr, c).value or "").strip()
        if t and t not in headers:
            log("removed_extra_column", f"{get_column_letter(c)}{src_hr}", t, None)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = prof["sheet_name"]
    # metadata block
    meta_src = {str(sh.get(r, 1).value or "").strip(): sh.get(r, 2) for r in range(1, src_hr)}
    for m in prof["metadata_rows"]:
        r, label = m["row"], m["label"]
        la, va = ws.cell(r, 1), ws.cell(r, 2)
        if not label:
            if m["height_pt"]:
                ws.row_dimensions[r].height = m["height_pt"]
            continue
        if label:
            la.value = label
        sig_l, sig_v = m["label_style"], m["value_style"]
        for cell, sig in ((la, sig_l), (va, sig_v)):
            cell.font, cell.alignment, cell.border = _font(sig, font_size), _align(sig), _border(sig["border"])
        va.number_format = sig_v["numfmt"] if sig_v["numfmt"] not in (None, "0") else "General"
        if not label:
            continue
        srcv = (metadata or {}).get(label)
        if srcv is None and label in meta_src and meta_src[label].kind != "empty":
            srcv = meta_src[label].value
        if isinstance(srcv, str) and m["value_kind"] == "date":
            d = parse_date(srcv)
            if d:
                log("date_text_to_date", f"B{r}", srcv, d)
                srcv = d
        if isinstance(srcv, str) and (PLACEHOLDER.match(srcv) or re.search(r"unknown|to be established|do not invent", srcv, re.I)) and m["value_kind"] == "date":
            log("metadata_placeholder_blanked", f"B{r}", srcv, None)
            needs_human.append({"cell": f"B{r}", "issue": f"{label} was '{srcv}' in source; blanked (not invented) - supply the real date"})
            srcv = None
        if isinstance(srcv, str) and len(srcv) > max(60, 2 * int(m.get("value_len") or 0)):
            needs_human.append({"cell": f"B{r}", "issue": f"{label} is {len(srcv)} chars (donor style is short; it will wrap/overprint). Move qualification text to the internal notes and keep the donor form"})
        if srcv in (None, ""):
            needs_human.append({"cell": f"B{r}", "issue": f"{label} has no value (not invented)"})
        else:
            va.value = srcv
        if m["height_pt"]:
            ws.row_dimensions[r].height = m["height_pt"]
    # header row
    for i, h in enumerate(headers, 1):
        cell = ws.cell(hr, i, h)
        sig = prof["header_style"][h]
        cell.font, cell.alignment, cell.border = _font(sig, font_size), _align(sig), _border(sig["border"])
        w = prof["columns"][i - 1]["width_in"]
        if w:
            ws.column_dimensions[get_column_letter(i)].width = inches_to_excel_width(w)
    ws.row_dimensions[hr].height = prof["header_height_pt"] or 30
    # body
    out_r = hr
    for r in range(src_hr + 1, sh.max_row + 1):
        if all(sh.get(r, c).kind == "empty" for c in colmap.values()):
            continue
        out_r += 1
        lines = 1
        for i, h in enumerate(headers, 1):
            cell = ws.cell(out_r, i)
            sc = sh.get(r, colmap[h]) if h in colmap else None
            val = None if sc is None or sc.kind == "empty" else sc.value
            ref = f"{get_column_letter(i)}{out_r}"
            sig = prof["body_style"][h]
            if isinstance(val, str):
                new = re.sub(r"[ \t]+\n", "\n", val.replace("\r\n", "\n").replace("\r", "\n")).strip()
                if new != val:
                    log("whitespace_normalized", ref, val, new)
                val = new
            if h in ("Date of Doc", "Rec Date") and isinstance(val, str):
                d = parse_date(val)
                if d:
                    log("date_text_to_date", ref, val, d)
                    val = d
                elif val:
                    needs_human.append({"cell": ref, "issue": f"unparseable date '{val}' kept as text"})
            if h == "Doc No" and isinstance(val, str) and val.isdigit():
                log("docno_text_to_int", ref, val, int(val))
                val = int(val)
            if h == "Comments":
                if val not in (None, "", ALLOWED_COMMENT):
                    log("comment_removed", ref, val, None)
                    needs_human.append({"cell": ref, "issue": f"comment removed from client file: '{val}'"})
                    val = None
            blank_ok = {k for k, n in prof["donor_blank_counts"].items() if n and k != "Comments"}
            if isinstance(val, str) and PLACEHOLDER.match(val):
                if h in blank_ok:
                    log("placeholder_blanked", ref, val, None)
                    needs_human.append({"cell": ref, "issue": f"{h} was '{val}'; blanked (donor allows blank {h}) - verify against the image"})
                    val = None
                else:
                    needs_human.append({"cell": ref, "issue": f"placeholder '{val}' in {h} left as-is, not invented"})
            if val is None and h not in ("Comments",) and h not in {k for k, n in prof["donor_blank_counts"].items() if n}:
                needs_human.append({"cell": ref, "issue": f"blank {h}"})
            cell.value = val
            cell.font, cell.alignment, cell.border = _font(sig, font_size), _align(sig), _border(sig["border"])
            if isinstance(val, (dt.date, dt.datetime)):
                cell.number_format = sig["numfmt"] or "m/d/yyyy"
            elif isinstance(val, int):
                cell.number_format = "0"
            lines = max(lines, expected_lines("" if val is None else (f"{val.month}/{val.day}/{val.year}" if isinstance(val, (dt.date, dt.datetime)) else str(val)), prof["columns"][i - 1]["width_in"], sig["wrap"]))
        ws.row_dimensions[out_r].height = 15.0 * lines
    # print setup mirrors donor
    p = prof["print"]
    ws.page_setup.orientation = p.get("orientation") or "landscape"
    ws.sheet_properties.pageSetUpPr = openpyxl.worksheet.properties.PageSetupProperties(fitToPage=True)
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = p.get("fit_width") or 1, 0
    ws.page_margins.left, ws.page_margins.right = p.get("margin_left") or 0.7, p.get("margin_right") or 0.7
    ws.page_margins.top, ws.page_margins.bottom = p.get("margin_top") or 0.3, p.get("margin_bottom") or 0.3
    ws.print_title_rows = None
    ws.freeze_panes = None
    os.makedirs(os.path.dirname(os.path.abspath(out_xlsx)), exist_ok=True)
    wb.save(out_xlsx)
    out_ods = None
    if make_ods and (shutil.which("soffice") or shutil.which("libreoffice")):
        exe = shutil.which("soffice") or shutil.which("libreoffice")
        prof_dir = tempfile.mkdtemp(prefix="lo_profile_")
        try:
            subprocess.run([exe, f"-env:UserInstallation=file://{prof_dir}", "--headless", "--convert-to", "ods", "--outdir",
                            os.path.dirname(os.path.abspath(out_xlsx)), out_xlsx], check=True, capture_output=True, timeout=180)
            out_ods = os.path.splitext(out_xlsx)[0] + ".ods"
            from .odsfix import set_ods_column_widths
            set_ods_column_widths(out_ods, {c["index"]: c["width_in"] for c in prof["columns"] if c["width_in"]})
        finally:
            shutil.rmtree(prof_dir, ignore_errors=True)
    rep = {"source": src, "xlsx": out_xlsx, "ods": out_ods, "rows_written": out_r - hr, "changes": changes,
           "needs_human": needs_human, "font_size_assumption": font_size,
           "note": "Candidate only. Source untouched. Blanks/placeholders are listed in needs_human, never invented."}
    with open(os.path.splitext(out_xlsx)[0] + "_changes.json", "w", encoding="utf8") as fh:
        json.dump(rep, fh, indent=2, default=str)
    return rep
