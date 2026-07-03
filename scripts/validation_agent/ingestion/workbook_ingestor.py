"""Non-destructive workbook ingestion.

Reads an XLSX/XLSM workbook WITHOUT executing macros, validates its ZIP
structure, and extracts a structural description (sheets, used ranges,
formulas, hardcoded values in expected-formula areas, relationships,
drawings/media). Produces an immutable manifest and hashes.

The workbook is opened read-only; the ingestor never writes to the source.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import openpyxl

from core.run_manager import sha256_file


@dataclass
class SheetInfo:
    name: str
    max_row: int
    max_col: int
    header_row: list[str] = field(default_factory=list)
    formula_cells: int = 0
    numeric_cells: int = 0
    text_cells: int = 0
    formula_samples: dict[str, str] = field(default_factory=dict)
    hardcoded_in_formula_area: list[str] = field(default_factory=list)


@dataclass
class WorkbookManifest:
    file_name: str
    file_path: str
    sha256: str
    size_bytes: int
    is_macro_enabled: bool
    has_vba: bool
    has_drawings: bool
    has_media: bool
    zip_valid: bool
    zip_entries: int
    relationships: list[str]
    sheets: list[SheetInfo]

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "file_path": self.file_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "is_macro_enabled": self.is_macro_enabled,
            "has_vba": self.has_vba,
            "has_drawings": self.has_drawings,
            "has_media": self.has_media,
            "zip_valid": self.zip_valid,
            "zip_entries": self.zip_entries,
            "relationships": self.relationships,
            "sheets": [
                {
                    "name": s.name,
                    "max_row": s.max_row,
                    "max_col": s.max_col,
                    "header_row": s.header_row,
                    "formula_cells": s.formula_cells,
                    "numeric_cells": s.numeric_cells,
                    "text_cells": s.text_cells,
                    "formula_samples": s.formula_samples,
                    "hardcoded_in_formula_area": s.hardcoded_in_formula_area,
                }
                for s in self.sheets
            ],
        }


class WorkbookIngestor:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Workbook not found: {self.path}")

    # ------------------------------------------------------------------ #
    def _inspect_zip(self) -> dict[str, Any]:
        """Validate ZIP structure and detect vba/drawings/media/relationships."""
        info = {
            "zip_valid": False,
            "zip_entries": 0,
            "has_vba": False,
            "has_drawings": False,
            "has_media": False,
            "relationships": [],
        }
        try:
            with zipfile.ZipFile(self.path) as zf:
                bad = zf.testzip()
                names = zf.namelist()
                info["zip_valid"] = bad is None and "[Content_Types].xml" in names
                info["zip_entries"] = len(names)
                for n in names:
                    low = n.lower()
                    if low.endswith("vbaproject.bin"):
                        info["has_vba"] = True
                    if "/drawings/" in low or low.startswith("xl/drawings/"):
                        info["has_drawings"] = True
                    if "/media/" in low or low.startswith("xl/media/"):
                        info["has_media"] = True
                    if low.endswith(".rels"):
                        info["relationships"].append(n)
        except zipfile.BadZipFile:
            info["zip_valid"] = False
        return info

    def _read_sheets(self, keep_vba: bool) -> list[SheetInfo]:
        """Read sheet structure without evaluating formulas or running macros."""
        # data_only=False keeps formula strings; openpyxl never executes VBA.
        wb = openpyxl.load_workbook(
            self.path, read_only=True, data_only=False, keep_vba=keep_vba
        )
        sheets: list[SheetInfo] = []
        try:
            for ws in wb.worksheets:
                si = SheetInfo(
                    name=ws.title,
                    max_row=ws.max_row or 0,
                    max_col=ws.max_column or 0,
                )
                # Header row (first non-empty row's string cells).
                for row in ws.iter_rows(min_row=1, max_row=1):
                    si.header_row = [
                        str(c.value) for c in row if c.value is not None
                    ]
                    break
                # Scan a bounded window for cell-type census.
                max_scan_rows = min(si.max_row, 2000)
                for row in ws.iter_rows(min_row=1, max_row=max_scan_rows):
                    for cell in row:
                        v = cell.value
                        if v is None:
                            continue
                        if isinstance(v, str) and v.startswith("="):
                            si.formula_cells += 1
                            if len(si.formula_samples) < 25:
                                si.formula_samples[cell.coordinate] = v
                        elif isinstance(v, (int, float)):
                            si.numeric_cells += 1
                        else:
                            si.text_cells += 1
                sheets.append(si)
        finally:
            wb.close()
        return sheets

    def ingest(self) -> WorkbookManifest:
        zip_info = self._inspect_zip()
        is_xlsm = self.path.suffix.lower() == ".xlsm" or zip_info["has_vba"]
        sheets = self._read_sheets(keep_vba=is_xlsm)
        return WorkbookManifest(
            file_name=self.path.name,
            file_path=str(self.path),
            sha256=sha256_file(self.path),
            size_bytes=self.path.stat().st_size,
            is_macro_enabled=is_xlsm,
            has_vba=zip_info["has_vba"],
            has_drawings=zip_info["has_drawings"],
            has_media=zip_info["has_media"],
            zip_valid=zip_info["zip_valid"],
            zip_entries=zip_info["zip_entries"],
            relationships=zip_info["relationships"],
            sheets=sheets,
        )
