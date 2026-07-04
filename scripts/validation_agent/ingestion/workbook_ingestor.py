"""Nondestructive workbook ingestion.

The workbook is only ever opened read-only. Macros are never executed; for
.xlsm we simply note their presence and preserve the file byte-for-byte
elsewhere (repairs happen on copies via the XML editor).
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, Dict, List

import openpyxl
from openpyxl.utils import get_column_letter


class IngestionError(RuntimeError):
    pass


def validate_xlsx_zip(path: Path) -> Dict[str, Any]:
    path = Path(path)
    if not zipfile.is_zipfile(path):
        raise IngestionError(f"not a valid OOXML (zip) file: {path}")
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        bad = z.testzip()
        if bad is not None:
            raise IngestionError(f"corrupt zip entry: {bad}")
    return {
        "entry_count": len(names),
        "has_content_types": "[Content_Types].xml" in names,
        "has_workbook": any(n.endswith("xl/workbook.xml") for n in names),
        "has_vba": any(n == "xl/vbaProject.bin" for n in names),
        "has_drawings": any(n.startswith("xl/drawings/") for n in names),
        "has_media": any(n.startswith("xl/media/") for n in names),
        "relationships": [n for n in names if n.endswith(".rels")],
    }


def ingest_workbook(path: Path) -> Dict[str, Any]:
    path = Path(path)
    zipinfo = validate_xlsx_zip(path)
    is_xlsm = path.suffix.lower() == ".xlsm"

    # data_only=False so we can see formulas; read_only for speed + no mutation;
    # keep_vba preserves macro project awareness for xlsm.
    wb = openpyxl.load_workbook(path, data_only=False, read_only=True, keep_vba=is_xlsm)
    sheets: List[Dict[str, Any]] = []
    try:
        for ws in wb.worksheets:
            formula_cells = 0
            hardcoded_in_formula_area = 0
            sample_headers: List[str] = []
            max_row = ws.max_row or 0
            max_col = ws.max_column or 0
            # Header sample from first non-empty row.
            for row in ws.iter_rows(min_row=1, max_row=min(max_row, 6), values_only=True):
                vals = [str(c) for c in row if c not in (None, "")]
                if vals:
                    sample_headers = vals[:20]
                    break
            # Scan a bounded window for formulas / numeric density.
            scan_rows = min(max_row, 400)
            numeric_cols: Dict[int, int] = {}
            for row in ws.iter_rows(min_row=1, max_row=scan_rows, values_only=False):
                for cell in row:
                    v = cell.value
                    if isinstance(v, str) and v.startswith("="):
                        formula_cells += 1
                    elif isinstance(v, (int, float)):
                        numeric_cols[cell.column] = numeric_cols.get(cell.column, 0) + 1
            # Columns that are mostly numeric but contain no formulas may be
            # hardcoded-value areas worth flagging for the formula validator.
            for col, cnt in numeric_cols.items():
                if cnt >= 5 and formula_cells == 0:
                    hardcoded_in_formula_area += 1
            sheets.append({
                "name": ws.title,
                "max_row": max_row,
                "max_col": max_col,
                "dimensions": f"A1:{get_column_letter(max(max_col,1))}{max(max_row,1)}",
                "formula_cell_count": formula_cells,
                "hardcoded_formula_area_cols": hardcoded_in_formula_area,
                "sample_headers": sample_headers,
            })
    finally:
        wb.close()

    return {
        "path": str(path),
        "suffix": path.suffix.lower(),
        "is_xlsm": is_xlsm,
        "zip": zipinfo,
        "sheet_count": len(sheets),
        "sheets": sheets,
    }
