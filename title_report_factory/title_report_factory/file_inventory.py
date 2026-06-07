"""Inventory every local file before doing anything else.

Each file is hashed (for dedup) and roughly classified by container type. An
inventory record is written so there is an audit trail of exactly what was
available at run time.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .models import SourceFile
from .utils import LOG, sha256_file

_EXCEL = {".xlsx", ".xlsm", ".xls"}
_PDF = {".pdf"}
_IMAGE = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}
_TEXT = {".txt", ".csv", ".md", ".json"}


def _kind_for(ext: str) -> str:
    ext = ext.lower()
    if ext in _EXCEL:
        return "excel"
    if ext in _PDF:
        return "pdf"
    if ext in _IMAGE:
        return "image"
    if ext in _TEXT:
        return "text"
    return "other"


def inventory_files(input_dirs: List[Path]) -> List[SourceFile]:
    seen_hashes: Dict[str, str] = {}
    out: List[SourceFile] = []
    for root in input_dirs:
        if not root.exists():
            LOG.warning("Input directory missing: %s", root)
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.name.startswith("."):
                continue
            try:
                digest = sha256_file(p)
            except OSError as exc:
                LOG.error("Could not hash %s: %s", p, exc)
                continue
            note = ""
            if digest in seen_hashes:
                note = f"Duplicate of {seen_hashes[digest]} (same content hash)"
            else:
                seen_hashes[digest] = p.name
            sf = SourceFile(
                path=str(p),
                name=p.name,
                ext=p.suffix.lower(),
                size_bytes=p.stat().st_size,
                sha256=digest,
                kind=_kind_for(p.suffix),
                note=note,
            )
            out.append(sf)
    LOG.info("Inventoried %d local file(s) across %d director(ies)",
             len(out), len(input_dirs))
    return out
