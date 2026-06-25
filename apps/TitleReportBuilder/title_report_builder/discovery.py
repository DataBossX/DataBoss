"""Recursive source discovery + manifest (path, type, size, mtime, sha256)."""
from __future__ import annotations
import hashlib
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

SKIP_DIRS = {".venv", "venv", "node_modules", "__pycache__", ".git", ".cache", ".tmp"}
HANDLED = {
    ".xlsx", ".xlsm", ".xls", ".csv", ".tsv", ".pdf", ".txt", ".md", ".docx",
    ".doc", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".json", ".xml", ".html",
}


@dataclass
class SourceFile:
    relative_path: str
    absolute_path: str
    file_type: str
    size: int
    modified_time: str
    sha256: str
    extraction_method: str
    status: str
    notes: str = ""


def _method_for(ext: str) -> str:
    return {
        ".xlsx": "openpyxl", ".xlsm": "openpyxl", ".xls": "openpyxl",
        ".csv": "pandas", ".tsv": "pandas",
        ".pdf": "pymupdf+ocr", ".png": "ocr", ".jpg": "ocr", ".jpeg": "ocr",
        ".tif": "ocr", ".tiff": "ocr", ".webp": "ocr",
        ".txt": "text", ".md": "text", ".json": "text", ".xml": "text",
        ".html": "text", ".docx": "python-docx", ".doc": "python-docx",
    }.get(ext, "skip")


def discover(root: str | os.PathLike, recurse: bool = True) -> list[SourceFile]:
    root = Path(root)
    out: list[SourceFile] = []
    walker = os.walk(root) if recurse else [(str(root), [], [f.name for f in Path(root).iterdir() if f.is_file()])]
    for dirpath, dirnames, filenames in walker:
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            fp = Path(dirpath) / name
            ext = fp.suffix.lower()
            try:
                data = fp.read_bytes()
            except Exception:
                continue
            st = fp.stat()
            out.append(SourceFile(
                relative_path=str(fp.relative_to(root)),
                absolute_path=str(fp.resolve()),
                file_type=ext.lstrip("."),
                size=st.st_size,
                modified_time=datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                sha256=hashlib.sha256(data).hexdigest(),
                extraction_method=_method_for(ext),
                status="found" if ext in HANDLED else "skipped(unhandled)",
            ))
    return out


def write_manifest(files: list[SourceFile], csv_path: str | os.PathLike) -> None:
    import csv as _csv
    fields = list(asdict(files[0]).keys()) if files else [f.name for f in SourceFile.__dataclass_fields__.values()]
    with open(csv_path, "w", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for f in files:
            w.writerow(asdict(f))
