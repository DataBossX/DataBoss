"""Parity checks: ODS-vs-XLSX cell comparison, and PDF page counts.

CLI:
  python -m peaches.parity <a.ods> <b.xlsx> <out_json>
  python -m peaches.parity --pdf <file.pdf> <out_json>
"""
from __future__ import annotations

import json
import os
import sys

try:
    import pymupdf as _pdf
except ImportError:
    import fitz as _pdf

from . import wb

MAX_MISMATCHES_LISTED = 200


def pdf_page_count(path):
    doc = _pdf.open(path)
    try:
        return doc.page_count
    finally:
        doc.close()


def compare_workbooks(path_a, path_b):
    _na, grid_a = wb.read_index_sheet(path_a)
    _nb, grid_b = wb.read_index_sheet(path_b)
    rows = max(len(grid_a), len(grid_b))
    mismatches = []
    mismatch_count = 0
    cells_compared = 0
    for r in range(rows):
        row_a = grid_a[r] if r < len(grid_a) else []
        row_b = grid_b[r] if r < len(grid_b) else []
        cols = max(len(row_a), len(row_b))
        for c in range(cols):
            va = row_a[c].strip() if c < len(row_a) else ""
            vb = row_b[c].strip() if c < len(row_b) else ""
            cells_compared += 1
            if va != vb:
                mismatch_count += 1
                if len(mismatches) < MAX_MISMATCHES_LISTED:
                    mismatches.append({
                        "row": r + 1, "col": c + 1, "a": va, "b": vb})
    return {
        "a": os.path.basename(path_a),
        "b": os.path.basename(path_b),
        "rows_a": len(grid_a),
        "rows_b": len(grid_b),
        "cells_compared": cells_compared,
        "mismatch_count": mismatch_count,
        "mismatches": mismatches,
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--pdf":
        if len(argv) != 3:
            print("usage: python -m peaches.parity --pdf <file.pdf> <out_json>",
                  file=sys.stderr)
            return 2
        result = {"pdf": os.path.basename(argv[1]),
                  "pages": pdf_page_count(argv[1])}
        out = argv[2]
    elif len(argv) == 3:
        result = compare_workbooks(argv[0], argv[1])
        out = argv[2]
    else:
        print("usage: python -m peaches.parity <a> <b> <out_json> | "
              "--pdf <file.pdf> <out_json>", file=sys.stderr)
        return 2
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print("parity -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
