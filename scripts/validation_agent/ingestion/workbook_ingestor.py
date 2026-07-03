"""WorkbookIngestor -- safe, non-destructive reading of an .xlsx workbook.

The workbook is treated as evidence: it is opened read-only, never recalculated
here, and macros are never executed.  We read the file at two levels:

    * ZIP/XML level -- to prove structural integrity (Gate 1) and enumerate the
      package parts without trusting any application to open it.
    * Cell level via openpyxl -- once for formula strings, once for the last
      cached values -- so downstream validators can compare "what the sheet
      claims to compute" against "what value is actually stored".

openpyxl is imported lazily so the rest of the package (and its unit tests)
does not hard-depend on it being installed.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

REQUIRED_ZIP_PARTS = ("[Content_Types].xml", "xl/workbook.xml")


@dataclass
class CellData:
    coord: str
    row: int
    col: int
    formula: Optional[str]      # e.g. "=SUM(B2:B11)"  (None if not a formula)
    value: Any                  # last cached computed value (may be None)

    @property
    def is_formula(self) -> bool:
        return self.formula is not None


@dataclass
class RawSheet:
    name: str
    index: int
    max_row: int
    max_col: int
    headers: list[str]
    cells: dict[str, CellData] = field(default_factory=dict)

    def column_values(self, col_letter: str) -> list[CellData]:
        return sorted(
            (c for c in self.cells.values() if _col_letters(c.coord) == col_letter),
            key=lambda c: c.row,
        )


@dataclass
class IngestResult:
    path: Path
    sha256: str
    zip_ok: bool
    zip_parts: list[str]
    integrity_error: Optional[str]
    sheets: list[RawSheet] = field(default_factory=list)

    @property
    def readable(self) -> bool:
        return self.zip_ok and self.integrity_error is None


def _col_letters(coord: str) -> str:
    return "".join(ch for ch in coord if ch.isalpha())


class WorkbookIngestor:
    def check_zip_integrity(self, path: Path) -> tuple[bool, list[str], Optional[str]]:
        """Validate the .xlsx ZIP container and required OOXML parts."""
        if not path.is_file():
            return False, [], f"File does not exist: {path}"
        try:
            with zipfile.ZipFile(path) as zf:
                bad = zf.testzip()
                if bad is not None:
                    return False, [], f"Corrupt ZIP entry: {bad}"
                names = zf.namelist()
        except zipfile.BadZipFile as exc:
            return False, [], f"Not a valid ZIP/XLSX: {exc}"
        missing = [p for p in REQUIRED_ZIP_PARTS if p not in names]
        if missing:
            return False, names, f"Missing required OOXML parts: {missing}"
        return True, names, None

    def ingest(self, path: str | Path, sha256: str) -> IngestResult:
        p = Path(path)
        zip_ok, parts, err = self.check_zip_integrity(p)
        result = IngestResult(path=p, sha256=sha256, zip_ok=zip_ok,
                              zip_parts=parts, integrity_error=err)
        if not zip_ok:
            return result
        try:
            result.sheets = self._read_sheets(p)
        except Exception as exc:  # noqa: BLE001 -- surfaced as an integrity error
            result.integrity_error = f"Failed to parse workbook cells: {exc}"
            result.zip_ok = False
        return result

    def _read_sheets(self, path: Path) -> list[RawSheet]:
        from openpyxl import load_workbook  # lazy import

        # Formula view: cell.value holds the formula string for formula cells.
        wb_f = load_workbook(path, read_only=True, data_only=False, keep_vba=False)
        # Cached-value view: cell.value holds the last computed value.
        wb_v = load_workbook(path, read_only=True, data_only=True, keep_vba=False)

        sheets: list[RawSheet] = []
        try:
            for index, name in enumerate(wb_f.sheetnames):
                ws_f = wb_f[name]
                ws_v = wb_v[name]
                cells: dict[str, CellData] = {}
                headers: list[str] = []

                for r_f, r_v in zip(ws_f.iter_rows(), ws_v.iter_rows()):
                    for cell_f, cell_v in zip(r_f, r_v):
                        raw = cell_f.value
                        if raw is None and cell_v.value is None:
                            continue
                        formula: Optional[str] = None
                        if isinstance(raw, str) and raw.startswith("="):
                            formula = raw
                        cells[cell_f.coordinate] = CellData(
                            coord=cell_f.coordinate,
                            row=cell_f.row,
                            col=cell_f.column,
                            formula=formula,
                            value=cell_v.value,
                        )
                    if not headers and any(c.value is not None for c in r_v):
                        headers = [
                            str(c.value).strip() if c.value is not None else ""
                            for c in r_v
                        ]

                sheets.append(RawSheet(
                    name=name,
                    index=index,
                    max_row=ws_f.max_row or 0,
                    max_col=ws_f.max_column or 0,
                    headers=headers,
                    cells=cells,
                ))
        finally:
            wb_f.close()
            wb_v.close()
        return sheets
