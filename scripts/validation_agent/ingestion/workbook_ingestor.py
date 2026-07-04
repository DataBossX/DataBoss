"""
Nondestructive workbook ingestion.

Validates the XLSX/XLSM as a ZIP, reads it read-only (macros never execute),
and produces an immutable manifest describing sheets, used ranges, formula vs.
hardcoded cells, relationships, and drawing/media presence. The source file is
opened read-only; nothing is written back.
"""
from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import openpyxl


def sha256_file(path: str | Path, chunk: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


class WorkbookIntegrityError(RuntimeError):
    pass


@dataclass
class SheetInfo:
    name: str
    max_row: int
    max_col: int
    used_range: str
    formula_cells: int
    hardcoded_numeric_cells: int
    header_row: List[str] = field(default_factory=list)
    sample_first_col: List[str] = field(default_factory=list)


@dataclass
class WorkbookManifest:
    file_name: str
    file_path: str
    file_sha256: str
    is_macro_enabled: bool
    zip_valid: bool
    has_vba: bool
    has_drawings: bool
    has_media: bool
    relationship_count: int
    sheet_names: List[str]
    sheets: List[Dict[str, Any]]
    manifest_sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _validate_zip(path: Path) -> Dict[str, Any]:
    if not zipfile.is_zipfile(path):
        raise WorkbookIntegrityError(f"Not a valid XLSX/ZIP: {path}")
    info = {"has_vba": False, "has_drawings": False, "has_media": False,
            "relationship_count": 0, "bad_file": None}
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        if bad is not None:
            raise WorkbookIntegrityError(f"Corrupt ZIP entry: {bad}")
        names = z.namelist()
        if "[Content_Types].xml" not in names:
            raise WorkbookIntegrityError("Missing [Content_Types].xml — not an OOXML workbook")
        for n in names:
            if n.endswith("vbaProject.bin"):
                info["has_vba"] = True
            if "/drawings/" in n or n.startswith("xl/drawings/"):
                info["has_drawings"] = True
            if "/media/" in n or n.startswith("xl/media/"):
                info["has_media"] = True
            if n.endswith(".rels"):
                info["relationship_count"] += 1
    return info


def ingest(workbook_path: str | Path, keep_vba: Optional[bool] = None) -> WorkbookManifest:
    path = Path(workbook_path)
    if not path.exists():
        raise WorkbookIntegrityError(f"Workbook does not exist: {path}")
    zinfo = _validate_zip(path)
    is_macro = path.suffix.lower() == ".xlsm" or zinfo["has_vba"]
    if keep_vba is None:
        keep_vba = is_macro

    # Read once WITHOUT data_only to see formulas; macros are never executed by openpyxl.
    wb_f = openpyxl.load_workbook(path, read_only=True, data_only=False, keep_vba=False)
    sheets: List[SheetInfo] = []
    try:
        for ws in wb_f.worksheets:
            formula = 0
            hardcoded = 0
            header: List[str] = []
            firstcol: List[str] = []
            max_row = ws.max_row or 0
            max_col = ws.max_column or 0
            # Bounded scan to stay fast on huge sheets.
            row_cap = min(max_row, 400)
            for r_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=row_cap), start=1):
                for c in row:
                    v = c.value
                    if isinstance(v, str) and v.startswith("="):
                        formula += 1
                    elif isinstance(v, (int, float)):
                        hardcoded += 1
                if r_idx == 1:
                    header = [str(c.value).strip() if c.value is not None else "" for c in row][:40]
                if row and row[0].value is not None and len(firstcol) < 25:
                    firstcol.append(str(row[0].value).strip())
            used = f"A1:{openpyxl.utils.get_column_letter(max(max_col,1))}{max(max_row,1)}"
            sheets.append(SheetInfo(ws.title, max_row, max_col, used,
                                    formula, hardcoded, header, firstcol))
    finally:
        wb_f.close()

    manifest = WorkbookManifest(
        file_name=path.name,
        file_path=str(path),
        file_sha256=sha256_file(path),
        is_macro_enabled=is_macro,
        zip_valid=True,
        has_vba=zinfo["has_vba"],
        has_drawings=zinfo["has_drawings"],
        has_media=zinfo["has_media"],
        relationship_count=zinfo["relationship_count"],
        sheet_names=[s.name for s in sheets],
        sheets=[asdict(s) for s in sheets],
    )
    return manifest
