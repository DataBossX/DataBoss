"""Shared helpers for the Grocery Report pipeline.

Design rules (from the mission non-negotiables):
- Deterministic first. AI extraction is optional and audited.
- Dependency-guarded: always emit CSV with stdlib; emit XLSX / parse PDF / OCR
  only when the optional library is installed. Never crash because a lib is
  missing — degrade and log.
- Every output carries a generation timestamp. Every fact row carries a source.
- Preserve originals. Nothing here deletes or mutates source files.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

# --- capability detection ---------------------------------------------------

def _have(mod: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(mod) is not None


CAPS = {
    "pandas": _have("pandas"),
    "openpyxl": _have("openpyxl"),
    "pypdf": _have("pypdf"),
    "pdfminer": _have("pdfminer"),
    "docx": _have("docx"),          # python-docx
    "pytesseract": _have("pytesseract"),
    "PIL": _have("PIL"),
    "rapidfuzz": _have("rapidfuzz"),
}


def caps_summary() -> str:
    return ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in CAPS.items())


# --- time / ids -------------------------------------------------------------

def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


# --- paths ------------------------------------------------------------------

def resolve_root(root: Optional[str]) -> Path:
    """Project root: explicit arg > DATABOSSX_PROJECT_ROOT env > current dir."""
    root = root or os.environ.get("DATABOSSX_PROJECT_ROOT") or "."
    return Path(root).resolve()


def output_dir(root: Path, out: Optional[str] = None) -> Path:
    d = Path(out).resolve() if out else (root / "output")
    d.mkdir(parents=True, exist_ok=True)
    (d / "extracted_text").mkdir(exist_ok=True)
    return d


def get_logger(name: str = "report_pipeline", out: Optional[Path] = None) -> logging.Logger:
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)
    if out is not None:
        fh = logging.FileHandler(out / "pipeline.log", encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)
    return log


# --- hashing ----------------------------------------------------------------

def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


# --- table writers ----------------------------------------------------------

def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def write_xlsx(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, Any]]) -> Optional[Path]:
    """Write an .xlsx. Uses openpyxl when available, otherwise a stdlib-only
    minimal OOXML writer — so .xlsx is ALWAYS produced (never silently skipped)."""
    rows = list(rows)
    if CAPS["openpyxl"]:
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(list(fieldnames))
        for r in rows:
            ws.append([r.get(k, "") for k in fieldnames])
        path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(path)
        return path

    from report_pipeline import minixlsx

    return minixlsx.write_xlsx(path, fieldnames, rows)


def write_table(
    out: Path,
    basename: str,
    fieldnames: Sequence[str],
    rows: List[Dict[str, Any]],
    xlsx: bool = True,
) -> Dict[str, Optional[str]]:
    """Write <basename>.csv (always) and <basename>.xlsx (if possible).

    Adds a trailing metadata row is avoided; instead a sidecar note is logged.
    Returns {'csv': path, 'xlsx': path-or-None}.
    """
    csv_path = write_csv(out / f"{basename}.csv", fieldnames, rows)
    xlsx_path = write_xlsx(out / f"{basename}.xlsx", fieldnames, rows) if xlsx else None
    return {"csv": str(csv_path), "xlsx": str(xlsx_path) if xlsx_path else None}


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return [dict(r) for r in csv.DictReader(fh)]
