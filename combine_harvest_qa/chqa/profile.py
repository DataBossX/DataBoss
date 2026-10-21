"""Extract machine-readable donor rules from a finished Overtime workbook (ODS or XLSX)."""
from __future__ import annotations

import collections
import json
import re
from typing import Any

from .model import Sheet, Workbook, col_letter
from .readers import read_workbook

HEADER_ROW_DEFAULT = 9


def _style_sig(c) -> dict:
    s = c.style
    return {"font": s.font_name, "size": s.font_size, "bold": s.bold, "italic": s.italic, "color": s.color,
            "fill": s.fill, "h": s.h_align, "v": s.v_align, "wrap": s.wrap, "shrink": s.shrink,
            "border": s.border, "numfmt": s.number_format}


def _most_common(items: list) -> Any:
    return collections.Counter(json.dumps(i, sort_keys=True) for i in items).most_common(1)[0][0]


def _find_header_row(sh: Sheet) -> int:
    for r in range(1, min(sh.max_row, 30) + 1):
        vals = [str(sh.get(r, c).value or "").strip() for c in range(1, sh.max_col + 1)]
        if "Document Type" in vals and "Grantor" in vals:
            return r
    return HEADER_ROW_DEFAULT


def _book_page_shapes(values: list[str]) -> dict[str, int]:
    def shape(v: str) -> str:
        return re.sub(r"[A-Za-z]", "A", re.sub(r"\d", "9", v))
    return dict(collections.Counter(shape(v) for v in values if v).most_common(12))


def extract_profile(path: str, kind: str = "index") -> dict:
    wb: Workbook = read_workbook(path)
    sh = wb.sheets[0]
    hr = _find_header_row(sh)
    ncols = max(c for (r, c), cell in sh.cells.items() if r == hr and cell.kind != "empty")
    headers = [str(sh.get(hr, c).value) for c in range(1, ncols + 1)]
    data_rows = [r for r in range(hr + 1, sh.max_row + 1)
                 if any(sh.get(r, c).kind != "empty" for c in range(1, ncols + 1))]
    prof: dict[str, Any] = {
        "tool_version": "1.0.0", "donor_file": path, "kind": kind, "format": wb.fmt,
        "sheet_name": sh.name, "sheet_count": len(wb.sheets),
        "default_font": list(wb.default_font) if wb.default_font else None,
        "header_row": hr, "first_data_row": hr + 1, "data_row_count": len(data_rows),
        "columns": [{"index": i + 1, "letter": col_letter(i + 1), "header": h,
                     "width_in": round(sh.col_widths_in.get(i + 1, 0), 3)} for i, h in enumerate(headers)],
        "print": {k: v for k, v in sh.print.__dict__.items()},
        "merged_cells": sh.merged,
    }
    meta_rows = []
    for r in range(1, hr):
        lab, val = sh.get(r, 1), sh.get(r, 2)
        meta_rows.append({"row": r, "label": lab.value, "value_kind": val.kind, "value_len": len(val.text or ""),
                          "label_style": _style_sig(lab), "value_style": _style_sig(val),
                          "height_pt": sh.row_heights_pt.get(r)})
    prof["metadata_rows"] = meta_rows
    prof["header_style"] = {headers[i]: _style_sig(sh.get(hr, i + 1)) for i in range(ncols)}
    prof["header_height_pt"] = sh.row_heights_pt.get(hr)
    body_styles, kinds, blanks, bp = {}, {}, {}, []
    for i, h in enumerate(headers):
        c = i + 1
        body_styles[h] = json.loads(_most_common([_style_sig(sh.get(r, c)) for r in data_rows]))
        kinds[h] = dict(collections.Counter(sh.get(r, c).kind for r in data_rows))
        blanks[h] = sum(1 for r in data_rows if sh.get(r, c).kind == "empty")
    prof["body_style"] = body_styles
    prof["value_kinds"] = kinds
    prof["donor_blank_counts"] = blanks
    prof["row_height_pt_values"] = sorted({sh.row_heights_pt.get(r) for r in data_rows if sh.row_heights_pt.get(r)})
    prof["row_height_rule"] = "15pt per wrapped line (optimal-height rows); donor values are multiples of 15"
    bcol = headers.index("Book-Page") + 1 if "Book-Page" in headers else None
    if bcol:
        prof["book_page_shapes"] = _book_page_shapes([sh.get(r, bcol).text for r in data_rows])
    lcol = headers.index("Legal Description") + 1 if "Legal Description" in headers else None
    if lcol:
        legs = [sh.get(r, lcol).text for r in data_rows if sh.get(r, lcol).text]
        prof["legal_aol_ratio"] = round(sum(1 for x in legs if x.rstrip().endswith(", aol")) / max(1, len(legs)), 3)
        prof["legal_samples"] = legs[:6]
    for name in ("Grantor", "Grantee"):
        if name in headers:
            c = headers.index(name) + 1
            vals = [sh.get(r, c).text for r in data_rows]
            prof[f"{name.lower()}_multiline_ratio"] = round(sum(1 for v in vals if "\n" in v) / max(1, len(vals)), 3)
    dcols = [i + 1 for i, h in enumerate(headers) if h in ("Date of Doc", "Rec Date")]
    prof["date_number_formats"] = sorted({sh.get(r, c).style.number_format or "" for r in data_rows for c in dcols
                                          if sh.get(r, c).kind == "date"})
    prof["comments_filled"] = sum(1 for r in data_rows if "Comments" in headers
                                  and sh.get(r, headers.index("Comments") + 1).kind != "empty")
    prof["cell_comments_present"] = sum(1 for cell in sh.cells.values() if cell.comment)
    return prof


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Extract donor format profile as JSON")
    ap.add_argument("donor")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--kind", default="index", choices=["index", "blm"])
    a = ap.parse_args(argv)
    prof = extract_profile(a.donor, a.kind)
    with open(a.out, "w", encoding="utf8") as f:
        json.dump(prof, f, indent=2, default=str)
    print(f"profile written: {a.out} ({prof['data_row_count']} data rows, {len(prof['columns'])} columns)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
