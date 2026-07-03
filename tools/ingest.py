"""Ingest notice-list rows from CSV (stdlib) or XLSX (openpyxl if available).

The DSU / OFFSET notice lists ship as Excel workbooks. openpyxl is not required
for CSV ingest, so this stays runnable in a bare stdlib environment; XLSX support
activates automatically when openpyxl is installed.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List


def load_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def load_xlsx(path: Path, sheet: str | None = None) -> List[Dict[str, object]]:
    try:
        import openpyxl  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "openpyxl is required for .xlsx ingest but is not installed. "
            "Export the sheet to CSV, or install openpyxl."
        ) from exc
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet] if sheet else wb.active
    rows = ws.iter_rows(values_only=True)
    header = [str(h) if h is not None else "" for h in next(rows)]
    out: List[Dict[str, object]] = []
    for r in rows:
        out.append({header[i]: r[i] for i in range(len(header))})
    return out


def load_rows(path: Path | str, sheet: str | None = None) -> List[Dict[str, object]]:
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        return load_xlsx(p, sheet)
    if p.suffix.lower() == ".csv":
        return load_csv(p)
    raise ValueError(f"Unsupported ingest format: {p.suffix}")
