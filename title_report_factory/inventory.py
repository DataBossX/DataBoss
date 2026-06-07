"""Inventory local source files for a title-report run.

Walks a source directory and classifies every file into a SourceFile record.
Pure-stdlib so it runs anywhere; OCR/Excel parsing happen downstream.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from .models import SourceFile

EXCEL_EXT = {".xlsx", ".xlsm", ".xls"}
PDF_EXT = {".pdf"}
IMAGE_EXT = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp", ".gif"}
TEXT_EXT = {".txt", ".csv", ".md", ".json"}


def _classify_ext(ext: str) -> str:
    ext = ext.lower()
    if ext in EXCEL_EXT:
        return "Excel"
    if ext in PDF_EXT:
        return "PDF"
    if ext in IMAGE_EXT:
        return "Image"
    if ext in TEXT_EXT:
        return "Text"
    return "Other"


def inventory_sources(source_dir: str) -> List[SourceFile]:
    """Return a SourceFile per relevant file under ``source_dir``.

    Returns an empty list (not an error) when the directory is missing or
    empty — callers must handle the no-input case honestly.
    """
    root = Path(source_dir)
    if not root.exists():
        return []

    found: List[SourceFile] = []
    counter = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("~$"):  # Excel lock files
            continue
        stype = _classify_ext(path.suffix)
        if stype == "Other" and path.suffix.lower() not in {""}:
            # Keep unknown types listed but flagged.
            pass
        counter += 1
        found.append(
            SourceFile(
                source_id=f"S{counter:03d}",
                source_type=stype,
                file_name=path.name,
                where_found=str(path.parent),
                pages="Unknown",
                ocr_status="Pending" if stype in ("PDF", "Image") else "N/A",
                extraction_status="Pending",
                limitations="",
                confidence=0,
            )
        )
    return found
