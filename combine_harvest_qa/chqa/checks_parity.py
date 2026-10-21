"""ODS vs XLSX (and any pair) cell-level parity: values, types and style signature."""
from __future__ import annotations

from .findings import Report
from .profile import _style_sig
from .readers import read_workbook

STYLE_KEYS = ("font", "bold", "h", "v", "wrap", "border", "numfmt", "color", "fill")


def check_parity(a_path: str, b_path: str, rep: Report) -> None:
    a, b = read_workbook(a_path).sheets[0], read_workbook(b_path).sheets[0]
    rep.inputs["pair"] = [a_path, b_path]
    if a.name != b.name:
        rep.add("sheet_name", "error", b_path, "sheet names differ", expected=a.name, actual=b.name)
    keys = sorted(set(a.cells) | set(b.cells))
    for r, c in keys:
        x, y = a.get(r, c), b.get(r, c)
        if x.kind == "empty" and y.kind == "empty":
            sx, sy = _style_sig(x), _style_sig(y)
            diff = [k for k in ("border",) if sx[k] != sy[k]]
        else:
            diff = []
        ref = x.ref
        if (x.kind, x.value) != (y.kind, y.value):
            rep.add("value_mismatch", "error", b_path, "value/type differs between formats", cell=ref, expected=f"{x.kind}:{x.value!r}", actual=f"{y.kind}:{y.value!r}")
        if x.kind != "empty" or y.kind != "empty":
            sx, sy = _style_sig(x), _style_sig(y)
            for k in STYLE_KEYS:
                if sx[k] != sy[k]:
                    rep.add("style_mismatch", "error", b_path, f"{k} differs between formats", cell=ref, expected=str(sx[k]), actual=str(sy[k]))
        for k in diff:
            rep.add("style_mismatch", "error", b_path, f"{k} differs on empty cell", cell=ref)
    for c in set(a.col_widths_in) | set(b.col_widths_in):
        wa, wb_ = a.col_widths_in.get(c), b.col_widths_in.get(c)
        if wa and wb_ and abs(wa - wb_) > 0.05:
            rep.add("width_mismatch", "warn", b_path, "column width differs between formats", cell=str(c), expected=f"{wa:.3f}in", actual=f"{wb_:.3f}in")
