"""Format conformance of a candidate workbook against a donor profile (cell-level)."""
from __future__ import annotations

import math

from .findings import Report
from .model import Sheet, col_letter, display_text
from .profile import _style_sig
from .readers import read_workbook, select_index_sheet

WIDTH_TOL_IN = 0.03
HEIGHT_TOL_PT = 0.5
STYLE_KEYS = ("font", "bold", "italic", "color", "fill", "h", "v", "wrap", "shrink", "border", "numfmt")


def _same(k: str, got, want, kind: str) -> bool:
    if k == "numfmt":
        if kind not in ("date", "int", "float"):
            return True            # number format is irrelevant on text/empty cells (donor stores N0 on text)
        norm = lambda v: None if v in (None, "General") else v
        if kind in ("int", "float"):
            return norm(got) in (None, "0") and norm(want) in (None, "0") or norm(got) == norm(want)
        return norm(got) == norm(want)
    return got == want


def expected_lines(text: str, width_in: float, wrap: bool) -> int:
    if not text:
        return 1
    if not wrap:
        return text.count("\n") + 1
    cpl = max(1, int((width_in * 72 - 8.0) / 4.8))   # calibrated on the Section 11 donor: 453/476 rows exact
    return sum(max(1, math.ceil(len(seg) / cpl)) for seg in text.split("\n"))


def check_format(path: str, prof: dict, rep: Report, sheet_name: str | None = None) -> Sheet | None:
    wb = read_workbook(path)
    rep.inputs.setdefault("files", []).append(path)
    if len(wb.sheets) != prof["sheet_count"]:
        rep.add("sheet_count", "error", path, "unexpected number of sheets", expected=str(prof["sheet_count"]), actual=str(len(wb.sheets)))
    sh = select_index_sheet(wb, sheet_name)
    if sh.name != prof["sheet_name"]:
        rep.add("sheet_name", "error", path, "sheet name differs from donor", sheet=sh.name, expected=prof["sheet_name"], actual=sh.name)
    hr = prof["header_row"]
    headers = [c["header"] for c in prof["columns"]]
    # metadata labels + styles
    for m in prof["metadata_rows"]:
        r = m["row"]
        lab, val = sh.get(r, 1), sh.get(r, 2)
        if (lab.value or "") != (m["label"] or ""):
            rep.add("metadata_label", "error", path, "metadata label differs", sheet=sh.name, cell=lab.ref, expected=str(m["label"]), actual=str(lab.value))
        for cell, sig in ((lab, m["label_style"]), (val, m["value_style"])):
            if cell.kind == "empty" and cell is val:
                continue            # style of an empty value cell is moot; a missing value is reported as metadata_date_type
            got = _style_sig(cell)
            for k in STYLE_KEYS:
                if not _same(k, got[k], sig[k], cell.kind):
                    rep.add("metadata_style", "error", path, f"{k} differs", sheet=sh.name, cell=cell.ref, expected=str(sig[k]), actual=str(got[k]))
        if m["value_kind"] == "date" and val.kind != "date":
            rep.add("metadata_date_type", "error", path, "metadata date is not a real date", sheet=sh.name, cell=val.ref, expected="date", actual=val.kind)
        h = sh.row_heights_pt.get(r)
        if m["height_pt"] and h and abs(h - m["height_pt"]) > HEIGHT_TOL_PT:
            rep.add("row_height", "warn", path, "metadata row height differs", sheet=sh.name, cell=f"row {r}", expected=str(m["height_pt"]), actual=str(h))
    # header row
    got_headers = [str(sh.get(hr, c).value) for c in range(1, len(headers) + 1)]
    if got_headers != headers:
        for i, (g, e) in enumerate(zip(got_headers, headers), 1):
            if g != e:
                rep.add("column_order", "error", path, "header/column order differs", sheet=sh.name, cell=f"{col_letter(i)}{hr}", expected=e, actual=g)
    extra = [c for c in range(len(headers) + 1, sh.max_col + 1) if any(sh.get(r, c).kind != "empty" for r in range(1, sh.max_row + 1))]
    for c in extra:
        rep.add("extra_column", "error", path, "extra client-facing column present", sheet=sh.name, cell=f"{col_letter(c)}{hr}", actual=str(sh.get(hr, c).value))
    for i, h in enumerate(headers, 1):
        got = _style_sig(sh.get(hr, i))
        for k in STYLE_KEYS:
            if not _same(k, got[k], prof["header_style"][h][k], sh.get(hr, i).kind):
                rep.add("header_style", "error", path, f"{k} differs", sheet=sh.name, cell=f"{col_letter(i)}{hr}", expected=str(prof["header_style"][h][k]), actual=str(got[k]))
        want_w = prof["columns"][i - 1]["width_in"]
        got_w = sh.col_widths_in.get(i)
        if want_w and (got_w is None or abs(got_w - want_w) > WIDTH_TOL_IN):
            rep.add("column_width", "error", path, "column width differs", sheet=sh.name, cell=col_letter(i), expected=f"{want_w:.3f}in", actual="none" if got_w is None else f"{got_w:.3f}in")
    # body
    for r in range(hr + 1, sh.max_row + 1):
        for i, h in enumerate(headers, 1):
            cell = sh.get(r, i)
            got = _style_sig(cell)
            for k in STYLE_KEYS:
                if not _same(k, got[k], prof["body_style"][h][k], cell.kind):
                    rep.add("cell_style", "error", path, f"{k} differs", sheet=sh.name, cell=cell.ref, expected=str(prof["body_style"][h][k]), actual=str(got[k]))
        hgt = sh.row_heights_pt.get(r)
        if hgt is not None:
            need = max(expected_lines(display_text(sh.get(r, i)), prof["columns"][i - 1]["width_in"], prof["body_style"][h]["wrap"]) for i, h in enumerate(headers, 1))
            if abs(hgt - 15.0 * need) > 15.0 + HEIGHT_TOL_PT:
                rep.add("row_height", "warn", path, "row height differs from autofit expectation by more than one line", sheet=sh.name, cell=f"row {r}", expected=f"{15.0 * need:.0f}pt", actual=f"{hgt}pt")
    # print setup
    p, dp = sh.print, prof["print"]
    for k in ("orientation", "margin_top", "margin_bottom", "margin_left", "margin_right", "fit_width"):
        want, got = dp.get(k), getattr(p, k)
        if want is None:
            continue
        bad = (abs(want - got) > 0.011) if isinstance(want, float) and got is not None else want != got
        if got is None or bad:
            rep.add("print_setup", "error", path, f"print {k} differs", sheet=sh.name, expected=str(want), actual=str(got))
    if not dp.get("title_rows") and p.title_rows:
        rep.add("print_titles", "error", path, "donor repeats no heading rows; candidate does", sheet=sh.name, expected="none", actual=str(p.title_rows))
    if not dp.get("freeze") and p.freeze:
        rep.add("freeze_panes", "error", path, "donor has no freeze panes", sheet=sh.name, expected="none", actual=str(p.freeze))
    for m in sh.merged:
        rep.add("merged_cells", "error", path, "donor has no merged cells", sheet=sh.name, cell=m)
    return sh
