#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roger Mills Cursory Title Report Builder  (codexv1)
===================================================

A single-file, defensive, *run-it-locally* tool that executes the full
"build the best possible updated Excel title report" mission against a real
folder tree on your machine (e.g. D:\\Desktop\\Horizon\\Roger Mills).

WHY THIS IS A LOCAL TOOL
------------------------
The cloud assistant that wrote this cannot see your D:\\ drive. So instead of
inventing data (which would be worthless and wrong for a title report), it
produced this tool for you to run *where the files actually live*.

WHAT IT DOES (matches the mission spec)
---------------------------------------
1.  Recursively inventories EVERY file under --root.
2.  Makes TIMESTAMPED BACKUPS of every original before reading (read-only on
    originals; nothing is deleted or overwritten).
3.  Classifies files: template / report workbooks / runsheet / index PDF /
    other supporting data.
4.  Analyzes every workbook (sheets, used range, headers, row counts, filled
    cells, formulas, a formatting-quality score).
5.  Runs a "tournament" to pick the BEST BASE report workbook by weighted score
    (template-closeness, completeness, cleanliness, recency, low blanks/errors).
6.  Uses Template(30).xlsx as the FORMATTING AUTHORITY: the output is a copy of
    the template workbook (preserving merged cells, fonts, colors, borders,
    column widths, row heights, formulas, page setup, print areas, freeze
    panes, headers/footers, tab order/colors) into which merged data is written.
7.  Extracts the index PDF via text -> pdfplumber -> PyMuPDF -> OCR (graceful
    fallback; writes an OCR-limitation note if no OCR engine is available).
8.  Merges the best data from ALL report workbooks, normalizes names/dates/
    document refs/legal descriptions, de-duplicates intelligently (true separate
    instruments are preserved), and verifies against the PDF/index where
    practical.
9.  Sorts rows chronologically (configurable) and writes them into the report.
9b. CHAINS OUT the interest: walks the chronological chain moving each
    instrument's conveyed interest grantor->grantee with exact rational math,
    and writes a "Chain of Title" sheet with current net mineral ownership
    (reconciled to 100%, net-mineral-acres when a single gross acreage is
    present). An unvested grantor is flagged as a gap, never invented.
10. Writes the final workbook to --output and creates all support files in
    --support-dir.
11. VALIDATES: reopens the output to prove it is not corrupted, confirms sheets
    and populated rows, and writes a validation summary.

IT NEVER INVENTS DATA. Unverified-but-supported rows are flagged in the
conflict/review outputs rather than silently trusted.

USAGE (Windows PowerShell or CMD)
---------------------------------
    py -m pip install --upgrade openpyxl pandas pdfplumber PyMuPDF pytesseract Pillow python-dateutil rapidfuzz

    py automation\\roger_mills_title_report_builder.py ^
        --root "D:\\Desktop\\Horizon\\Roger Mills" ^
        --root "D:\\Desktop\\Horizon\\Roger Mills 2" ^
        --root "D:\\Desktop\\Horizon\\Roger Mills 3" ^
        --output "D:\\Desktop\\Horizon\\rogermillsfinalreports\\31-12N-24W_Cursory_Title_Report.xlsx" ^
        --support-dir "D:\\Desktop\\Horizon\\rogermillsfinalreports\\files" ^
        --section "31-12N-24W"

--root is repeatable (one per source folder). A .env beside the roots (e.g.
D:\\Desktop\\Horizon\\.env) is auto-loaded for API keys, or pass --env-file.
Every title-like sheet in a workbook is read (Title + Tract + OGL sheets), OGL
numbers are tied out into an OGL Register sheet, and the interest is chained out
(leases are routed to the register, not the mineral chain).

Run with --dry-run first to see the plan without writing the final workbook.

Only openpyxl + pandas are strictly required. pdfplumber / PyMuPDF / pytesseract
/ rapidfuzz / python-dateutil are optional and degrade gracefully.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import io
import os
import re
import shutil
import sys
import traceback
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ----------------------------------------------------------------------------
# Optional dependency shims (degrade gracefully, never hard-crash on import)
# ----------------------------------------------------------------------------
try:
    import openpyxl
    from openpyxl.utils import get_column_letter
except Exception as exc:  # pragma: no cover - hard requirement
    print("FATAL: openpyxl is required. Install with: py -m pip install openpyxl")
    raise

try:
    import pandas as pd  # noqa: F401  (used for CSV/data convenience)
    _HAVE_PANDAS = True
except BaseException:  # optional dep may panic (e.g. broken cffi), not just raise
    _HAVE_PANDAS = False

try:
    from dateutil import parser as _dateparser  # type: ignore
    _HAVE_DATEUTIL = True
except BaseException:
    _HAVE_DATEUTIL = False

try:
    from rapidfuzz import fuzz as _fuzz  # type: ignore
    _HAVE_RAPIDFUZZ = True
except BaseException:
    _HAVE_RAPIDFUZZ = False

# PDF extraction backends (any/all optional)
try:
    import pdfplumber  # type: ignore
    _HAVE_PDFPLUMBER = True
except BaseException:
    _HAVE_PDFPLUMBER = False

try:
    import fitz  # PyMuPDF  # type: ignore
    _HAVE_PYMUPDF = True
except BaseException:
    _HAVE_PYMUPDF = False

try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
    _HAVE_OCR = True
except BaseException:
    _HAVE_OCR = False


# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------
class BuildLog:
    """Collects a human-readable build log and echoes to stdout."""

    def __init__(self) -> None:
        self._lines: List[str] = []
        self.start = _dt.datetime.now()

    def __call__(self, msg: str, level: str = "INFO") -> None:
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {level:5s} {msg}"
        self._lines.append(line)
        print(line)

    def section(self, title: str) -> None:
        bar = "=" * 70
        self(bar)
        self(title)
        self(bar)

    def dump(self, path: Path) -> None:
        header = [
            "Roger Mills Title Report Builder - build log (codexv1)",
            f"Started:  {self.start:%Y-%m-%d %H:%M:%S}",
            f"Finished: {_dt.datetime.now():%Y-%m-%d %H:%M:%S}",
            "",
        ]
        path.write_text("\n".join(header + self._lines) + "\n", encoding="utf-8")


LOG = BuildLog()


# ----------------------------------------------------------------------------
# Normalization helpers (no data invented - just cleanup/standardization)
# ----------------------------------------------------------------------------
_WS_RE = re.compile(r"\s+")
_MONTHS = (
    "january february march april may june july august september october "
    "november december"
).split()


def norm_text(value: Any) -> str:
    if value is None:
        return ""
    # An integral float from openpyxl (e.g. 456.0) must render as "456", not
    # "456.0", so an instrument/book/page number keeps a stable dedup key.
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    s = str(value).replace(" ", " ").strip()
    return _WS_RE.sub(" ", s)


def norm_name(value: Any) -> str:
    """Normalize a party (grantor/grantee) name for comparison/dedup."""
    s = norm_text(value).upper()
    s = s.replace(".", "").replace(",", " ")
    s = re.sub(r"\b(AN|A|THE)\b", " ", s)
    for token in (" AND ", " & "):
        s = s.replace(token, " & ")
    return _WS_RE.sub(" ", s).strip()


def norm_doc_ref(value: Any) -> str:
    """Normalize instrument / document / book-page references for dedup."""
    s = norm_text(value).upper()
    s = re.sub(r"[^A-Z0-9]+", "", s)
    return s


def norm_date(value: Any) -> Optional[_dt.date]:
    """Best-effort parse to a date. Returns None if unparseable (never guesses)."""
    if value is None or value == "":
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    s = norm_text(value)
    if not s:
        return None
    # Excel serials sometimes leak through as ints, but a bare 5-digit string is
    # just as likely a page/reference number. Only treat it as a serial in a
    # plausible modern-date range (~1954-2064) to avoid inventing dates from refs.
    if re.fullmatch(r"\d{5}", s) and 20000 <= int(s) <= 60000:
        try:
            base = _dt.date(1899, 12, 30)
            return base + _dt.timedelta(days=int(s))
        except Exception:
            return None
    # fuzzy=False: never fabricate a date from a messy non-date cell. But many
    # runsheet cells annotate a real date ("1/2/1990 re-recorded"); recover the
    # explicit date token by regex first, then parse THAT strictly.
    candidates = [s]
    frag = re.search(
        r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2}"
        r"|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}", s)
    if frag:
        candidates.append(frag.group(0))
    for cand in candidates:
        if _HAVE_DATEUTIL:
            try:
                return _dateparser.parse(cand, dayfirst=False, fuzzy=False).date()
            except Exception:
                pass
        for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y",
                    "%B %d, %Y", "%b %d, %Y"):
            try:
                return _dt.datetime.strptime(cand, fmt).date()
            except Exception:
                continue
    return None


def similar(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    if _HAVE_RAPIDFUZZ:
        return _fuzz.token_sort_ratio(a, b) / 100.0
    # cheap fallback: Jaccard over word sets
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# ----------------------------------------------------------------------------
# File inventory & classification
# ----------------------------------------------------------------------------
WORKBOOK_EXT = {".xlsx", ".xlsm", ".xls"}
DATA_EXT = {".csv", ".txt", ".tsv"}
DOC_EXT = {".docx", ".doc"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
PDF_EXT = {".pdf"}


@dataclass
class FileRec:
    path: Path
    rel: str
    ext: str
    size: int
    mtime: _dt.datetime
    kind: str = "other"  # template|report|runsheet|index_pdf|data|doc|image|other
    note: str = ""
    root: Optional[Path] = None  # which scan-root this file came from


def load_dotenv(path: Path) -> int:
    """Load KEY=VALUE lines from a .env file into os.environ (no override of an
    already-set variable). Returns the count loaded. Quiet if the file is
    absent. This is how the OKCountyRecords API key / other secrets reach the
    tool without being hardcoded."""
    if not path or not path.is_file():
        return 0
    loaded = 0
    try:
        # utf-8-sig strips a Windows/Notepad BOM so the first key is not stored
        # as "﻿KEY" and lost.
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):   # tolerate shell-style 'export KEY=val'
                line = line[len("export "):].lstrip()
            key, _, val = line.partition("=")
            key, val = key.strip().lstrip("﻿"), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
                loaded += 1
    except OSError:
        return loaded
    return loaded


def classify(rec: FileRec) -> str:
    name = rec.path.name.lower()
    if rec.ext in WORKBOOK_EXT:
        if "template" in name:
            return "template"
        if "runsheet" in name or "run sheet" in name:
            return "runsheet"
        if "title_report" in name or "title report" in name or "cursory" in name:
            return "report"
        return "report"  # treat unknown workbooks as candidate reports
    if rec.ext in PDF_EXT:
        if "index" in name or re.search(r"\d+[ns]-\d+[ew]", name) or "12n" in name:
            return "index_pdf"
        return "index_pdf"
    if rec.ext in DATA_EXT:
        return "data"
    if rec.ext in DOC_EXT:
        return "doc"
    if rec.ext in IMG_EXT:
        return "image"
    return "other"


def inventory(root: Path, exclude: Optional[Sequence[Path]] = None) -> List[FileRec]:
    recs: List[FileRec] = []
    # Resolve the dirs/files we must never ingest: our own support dir, the
    # output workbook, and prior-run artifacts. Re-ingesting them would grow
    # backups exponentially and merge the tool's own output back in as "source".
    excl_dirs: List[Path] = []
    excl_files: set = set()
    for e in (exclude or []):
        try:
            e = e.resolve()
        except OSError:
            continue
        # Classify by type; for a path that does not exist yet (e.g. the output
        # workbook, or a support dir not created until step 2) infer from the
        # suffix so the support dir is pruned as a directory, not a file.
        if e.is_dir() or (not e.exists() and not e.suffix):
            excl_dirs.append(e)
        else:
            excl_files.add(e)

    def _excluded(p: Path) -> bool:
        try:
            rp = p.resolve()
        except OSError:
            return True
        if rp in excl_files:
            return True
        for d in excl_dirs:
            if d == rp or d in rp.parents:
                return True
        name = p.name.lower()
        # Excel lock files and prior-run outputs/backups by naming convention.
        if name.startswith("~$") or "codexv1" in name or name.startswith("backup_"):
            return True
        return False

    for dirpath, dirs, files in os.walk(root):
        here = Path(dirpath)
        # prune excluded subtrees in-place so os.walk never descends into them.
        # Only the explicitly-excluded paths (support dir / output / artifacts)
        # are pruned -- never a source folder just because it is named "files".
        dirs[:] = [d for d in dirs if not _excluded(here / d)]
        for fn in files:
            p = here / fn
            if _excluded(p):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            rec = FileRec(
                path=p,
                rel=str(p.relative_to(root)),
                ext=p.suffix.lower(),
                size=st.st_size,
                mtime=_dt.datetime.fromtimestamp(st.st_mtime),
                root=root,
            )
            rec.kind = classify(rec)
            recs.append(rec)
    return recs


# ----------------------------------------------------------------------------
# Workbook analysis & scoring tournament
# ----------------------------------------------------------------------------
# Canonical title-report columns we try to recognize across messy headers.
CANON_FIELDS = [
    "entry_no", "instrument_date", "recorded_date", "doc_type",
    "grantor", "grantee", "book", "page", "instrument_no", "ogl",
    "legal_description", "acreage", "nma", "interest", "remarks",
]

HEADER_SYNONYMS: Dict[str, Sequence[str]] = {
    "entry_no": ("entry", "no", "item", "#", "seq", "line"),
    "instrument_date": ("instrument date", "doc date", "dated", "date of instrument", "date"),
    "recorded_date": ("recorded", "record date", "filed", "recording date"),
    "doc_type": ("type", "instrument type", "document type", "doc type", "conveyance"),
    "grantor": ("grantor", "from", "seller", "assignor", "mortgagor", "lessor"),
    "grantee": ("grantee", "to", "buyer", "assignee", "mortgagee", "lessee"),
    "book": ("book", "vol", "volume", "bk"),
    "page": ("page", "pg", "pages"),
    "instrument_no": ("instrument", "document number", "doc no", "doc #", "reception", "file no"),
    "ogl": ("ogl", "o.g.l", "lease number", "lease no", "lease id", "ogl no",
            "ogl #", "lease #", "oil and gas lease"),
    "legal_description": ("legal", "description", "land", "tract", "lands described"),
    "acreage": ("acres", "acreage", "gross acres"),
    "nma": ("nma", "net mineral", "net acres", "nra"),
    "interest": ("interest", "fraction", "decimal", "ri", "ori", "wi", "nri"),
    "remarks": ("remarks", "notes", "comments", "exceptions", "review"),
}


def match_header(cell_text: str) -> Optional[str]:
    t = norm_text(cell_text).lower()
    if not t:
        return None
    best_field, best_score = None, 0.0
    for field_name, syns in HEADER_SYNONYMS.items():
        for syn in syns:
            if syn == t:
                return field_name
            # Allow *containment* only on a word boundary (>= 2-char synonyms).
            # The boundary keeps "Notes" from matching entry_no via "no" and
            # "Total" from matching grantee via "to", while still mapping
            # abbreviated headers like "No.", "Pg.", "Bk." (the trailing dot is a
            # word boundary). 1-char synonyms ("#") match by exact header only.
            if len(syn) >= 2 and re.search(r"\b" + re.escape(syn) + r"\b", t):
                score = len(syn) / max(len(t), 1)
                if score > best_score:
                    best_field, best_score = field_name, score
    return best_field if best_score >= 0.34 else None


@dataclass
class SheetAnalysis:
    name: str
    max_row: int
    max_col: int
    header_row: int
    header_map: Dict[int, str]  # col_idx -> canon field
    data_rows: int
    filled_cells: int
    formula_cells: int
    blank_ratio: float


@dataclass
class WorkbookAnalysis:
    rec: FileRec
    sheets: List[SheetAnalysis] = field(default_factory=list)
    style_score: float = 0.0
    error: str = ""

    @property
    def best_sheet(self) -> Optional[SheetAnalysis]:
        candidates = [s for s in self.sheets if s.header_map]
        if not candidates:
            return None
        return max(candidates, key=lambda s: (len(s.header_map), s.data_rows))


def _detect_header_row(ws, scan_rows: int = 25) -> Tuple[int, Dict[int, str]]:
    best_row, best_map = 1, {}
    for r in range(1, min(scan_rows, ws.max_row) + 1):
        hmap: Dict[int, str] = {}
        for c in range(1, ws.max_column + 1):
            val = ws.cell(row=r, column=c).value
            f = match_header(val) if val is not None else None
            if f and f not in hmap.values():
                hmap[c] = f
        if len(hmap) > len(best_map):
            best_row, best_map = r, hmap
    return best_row, best_map


def analyze_workbook(rec: FileRec) -> WorkbookAnalysis:
    wa = WorkbookAnalysis(rec=rec)
    try:
        wb = openpyxl.load_workbook(rec.path, data_only=False, read_only=False)
    except Exception as exc:
        wa.error = f"load failed: {exc}"
        return wa

    style_points = 0.0
    for ws in wb.worksheets:
        try:
            header_row, header_map = _detect_header_row(ws)
            filled = formula = 0
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value not in (None, ""):
                        filled += 1
                        if isinstance(cell.value, str) and cell.value.startswith("="):
                            formula += 1
            data_rows = max(ws.max_row - header_row, 0)
            total_cells = max(ws.max_row * ws.max_column, 1)
            blank_ratio = 1.0 - (filled / total_cells)
            wa.sheets.append(SheetAnalysis(
                name=ws.title, max_row=ws.max_row, max_col=ws.max_column,
                header_row=header_row, header_map=header_map,
                data_rows=data_rows, filled_cells=filled,
                formula_cells=formula, blank_ratio=blank_ratio,
            ))
            # crude style richness proxy
            if ws.merged_cells.ranges:
                style_points += min(len(list(ws.merged_cells.ranges)), 20) * 0.5
            if getattr(ws, "freeze_panes", None):
                style_points += 2
            dims = getattr(ws, "column_dimensions", {})
            style_points += min(sum(1 for d in dims.values() if d.width), 30) * 0.2
        except Exception as exc:
            LOG(f"  sheet '{ws.title}' analysis error: {exc}", "WARN")
    wa.style_score = style_points
    wb.close()
    return wa


def score_report(wa: WorkbookAnalysis, newest_mtime: float, oldest_mtime: float) -> float:
    """Weighted tournament score for choosing the best base report workbook."""
    if wa.error or not wa.best_sheet:
        return -1.0
    s = wa.best_sheet
    # completeness: recognized columns + data rows
    completeness = len(s.header_map) / len(CANON_FIELDS)
    volume = min(s.data_rows / 50.0, 1.0)
    cleanliness = 1.0 - min(s.blank_ratio, 1.0)
    style = min(wa.style_score / 30.0, 1.0)
    span = max(newest_mtime - oldest_mtime, 1.0)
    recency = (wa.rec.mtime.timestamp() - oldest_mtime) / span
    # filename hints that this is an explicitly "best/updated" build
    name = wa.rec.path.name.lower()
    name_bonus = 0.0
    for kw, pts in (("updated", 0.06), ("best", 0.08), ("final", 0.05), ("v2", 0.03)):
        if kw in name:
            name_bonus += pts
    return (0.34 * completeness + 0.20 * volume + 0.16 * cleanliness
            + 0.14 * style + 0.10 * recency + name_bonus)


# ----------------------------------------------------------------------------
# Row extraction & merge
# ----------------------------------------------------------------------------
@dataclass
class TitleRow:
    data: Dict[str, str]
    source: str
    source_row: int

    def key(self) -> str:
        """Dedup key: prefer an explicit instrument/book-page, fall back to a
        normalized (grantor|grantee|date|type) signature."""
        inst = norm_doc_ref(self.data.get("instrument_no", ""))
        bp = norm_doc_ref(self.data.get("book", "") + self.data.get("page", ""))
        if inst:
            return f"INST:{inst}"
        if bp and bp not in ("", "0"):
            return f"BP:{bp}"
        sig = "|".join((
            norm_name(self.data.get("grantor", "")),
            norm_name(self.data.get("grantee", "")),
            str(norm_date(self.data.get("instrument_date", "")) or
                norm_date(self.data.get("recorded_date", "")) or ""),
            norm_text(self.data.get("doc_type", "")).upper(),
        ))
        return f"SIG:{sig}"


def _is_title_sheet(s: SheetAnalysis) -> bool:
    """A sheet carries title/chain rows if it has parties or an instrument ref.

    This is what lets a multi-sheet workbook (a Title sheet, several Tract
    sheets, an OGL sheet) contribute every relevant sheet -- not just one 'best'
    sheet. A pure legals/acreage tract sheet with no parties/instrument is not
    treated as a chain source (we don't 'go off the tract sheets' for the chain).
    """
    fields = set(s.header_map.values())
    has_parties = "grantor" in fields and "grantee" in fields
    has_ogl = "ogl" in fields
    # Require parties (a real conveyance table) or an OGL column (the lease
    # sheet). Book/Page alone does NOT qualify -- tract sheets carry Book/Page
    # for the tract's source but are legals/acreage, not chain rows, so this is
    # how we avoid "going off the tract sheets" for the chain.
    return bool(s.header_map) and (has_parties or has_ogl)


def extract_rows(wa: WorkbookAnalysis) -> List[TitleRow]:
    """Extract title rows from EVERY title-like sheet in the workbook."""
    rows: List[TitleRow] = []
    sheets = [s for s in wa.sheets if _is_title_sheet(s)]
    if not sheets:
        bs = wa.best_sheet
        sheets = [bs] if bs else []
    if not sheets:
        return rows
    try:
        # Stream with iter_rows (not random .cell()) and do NOT rely on
        # ws.max_row, which is None/unreliable in read-only mode.
        wb = openpyxl.load_workbook(wa.rec.path, data_only=True, read_only=True)
        for s in sheets:
            if s.name not in wb.sheetnames:
                continue
            ws = wb[s.name]
            rownum = 0
            for row_cells in ws.iter_rows(min_row=1):
                rownum += 1
                if rownum <= s.header_row:
                    continue
                data: Dict[str, str] = {}
                for col_idx, field_name in s.header_map.items():
                    idx = col_idx - 1
                    val = row_cells[idx].value if 0 <= idx < len(row_cells) else None
                    data[field_name] = norm_text(val)
                if any(v for v in data.values()):
                    rows.append(TitleRow(data=data,
                                         source=f"{wa.rec.path.name}#{s.name}",
                                         source_row=rownum))
        wb.close()
    except Exception as exc:
        LOG(f"  extract failed for {wa.rec.path.name}: {exc}", "WARN")
    return rows


def collect_ogl_register(merged: List["TitleRow"]) -> List[Dict[str, str]]:
    """Build an OGL register from every merged row carrying an OGL number:
    OGL # -> lessor/lessee (grantor/grantee), book/page or instrument, legal.
    De-duplicated by normalized OGL number."""
    seen: Dict[str, Dict[str, str]] = {}
    for row in merged:
        ogl = norm_text(row.data.get("ogl", ""))
        if not ogl:
            continue
        key = norm_doc_ref(ogl)
        if key in seen:
            continue
        d = row.data
        ref = (f"Bk {d.get('book','')}/Pg {d.get('page','')}"
               if d.get("book") and d.get("page")
               else (f"Inst {d.get('instrument_no','')}"
                     if d.get("instrument_no") else ""))
        seen[key] = {
            "ogl": ogl,
            "lessor": d.get("grantor", ""),
            "lessee": d.get("grantee", ""),
            "source": ref,
            "legal": d.get("legal_description", ""),
            "interest": d.get("interest", ""),
        }
    return list(seen.values())


def merge_rows(all_rows: List[List[TitleRow]]) -> Tuple[List[TitleRow], List[Dict[str, str]], List[Dict[str, str]]]:
    """Merge rows from many workbooks.

    Returns (merged_rows, audit_records, conflict_records).
    Conflicts = same key, differing field values across sources.
    """
    bucket: Dict[str, List[TitleRow]] = {}
    audit: List[Dict[str, str]] = []
    for source_rows in all_rows:
        for row in source_rows:
            k = row.key()
            bucket.setdefault(k, []).append(row)

    merged: List[TitleRow] = []
    conflicts: List[Dict[str, str]] = []
    for k, group in bucket.items():
        # field-by-field, pick the most complete / most common value
        chosen: Dict[str, str] = {}
        for fld in CANON_FIELDS:
            values = [norm_text(g.data.get(fld, "")) for g in group]
            non_empty = [v for v in values if v]
            if not non_empty:
                chosen[fld] = ""
                continue
            # majority vote, tie-broken by longest (most descriptive)
            counts: Dict[str, int] = {}
            for v in non_empty:
                counts[v] = counts.get(v, 0) + 1
            best_val = sorted(non_empty, key=lambda v: (counts[v], len(v)), reverse=True)[0]
            chosen[fld] = best_val
            distinct = {v for v in non_empty}
            if len(distinct) > 1:
                conflicts.append({
                    "key": k,
                    "field": fld,
                    "chosen": best_val,
                    "alternatives": " | ".join(sorted(distinct - {best_val})),
                    "sources": " ; ".join(f"{g.source}:r{g.source_row}" for g in group),
                })
        merged_row = TitleRow(data=chosen, source=";".join(sorted({g.source for g in group})),
                              source_row=group[0].source_row)
        merged.append(merged_row)
        audit.append({
            "key": k,
            "n_sources": str(len(group)),
            "sources": " ; ".join(sorted({g.source for g in group})),
            "grantor": chosen.get("grantor", ""),
            "grantee": chosen.get("grantee", ""),
            "doc_type": chosen.get("doc_type", ""),
            "instrument_no": chosen.get("instrument_no", ""),
            "book": chosen.get("book", ""),
            "page": chosen.get("page", ""),
        })

    # chronological sort (rows with no parseable date sink to the end, stable)
    def sort_key(row: TitleRow):
        d = (norm_date(row.data.get("instrument_date", "")) or
             norm_date(row.data.get("recorded_date", "")))
        return (0, d) if d else (1, _dt.date.max)

    merged.sort(key=sort_key)
    return merged, audit, conflicts


# ----------------------------------------------------------------------------
# PDF / index extraction (text -> pdfplumber -> PyMuPDF -> OCR)
# ----------------------------------------------------------------------------
def extract_pdf_text(pdf_path: Path) -> Tuple[str, str]:
    """Returns (text, method). Empty text + 'none' if all backends fail."""
    if _HAVE_PDFPLUMBER:
        try:
            chunks = []
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page in pdf.pages:
                    chunks.append(page.extract_text() or "")
            text = "\n".join(chunks).strip()
            if text:
                return text, "pdfplumber"
        except Exception as exc:
            LOG(f"  pdfplumber failed: {exc}", "WARN")
    if _HAVE_PYMUPDF:
        try:
            text_chunks = []
            doc = fitz.open(str(pdf_path))
            for page in doc:
                text_chunks.append(page.get_text())
            text = "\n".join(text_chunks).strip()
            if text:
                return text, "pymupdf"
            # image-based: try OCR per page render
            if _HAVE_OCR:
                ocr_chunks = []
                for page in doc:
                    pix = page.get_pixmap(dpi=300)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_chunks.append(pytesseract.image_to_string(img))
                ocr_text = "\n".join(ocr_chunks).strip()
                if ocr_text:
                    return ocr_text, "pymupdf+ocr"
        except Exception as exc:
            LOG(f"  PyMuPDF/OCR failed: {exc}", "WARN")
    return "", "none"


def verify_against_index(merged: List[TitleRow], index_text: str) -> Dict[str, bool]:
    """Mark each merged row 'verified' if its instrument/book-page or party names
    appear in the index text. Never fabricates - only confirms presence."""
    verified: Dict[str, bool] = {}
    haystack = re.sub(r"[^A-Za-z0-9]+", "", index_text).upper()
    if not haystack:
        return verified
    for row in merged:
        k = row.key()
        inst = norm_doc_ref(row.data.get("instrument_no", ""))
        bp = norm_doc_ref(row.data.get("book", "") + row.data.get("page", ""))
        ok = False
        if inst and len(inst) >= 4 and inst in haystack:
            ok = True
        elif bp and len(bp) >= 3 and bp in haystack:
            ok = True
        else:
            g = norm_doc_ref(row.data.get("grantor", ""))[:12]
            if g and len(g) >= 6 and g in haystack:
                ok = True
        verified[k] = ok
    return verified


# ----------------------------------------------------------------------------
# Interest chain-out (running mineral ownership from the merged chain)
# ----------------------------------------------------------------------------
_SOVEREIGN_ROOTS = {
    "US PATENT", "USA", "UNITED STATES", "UNITED STATES OF AMERICA", "PATENT",
    "STATE OF OKLAHOMA", "STATE", "SOVEREIGN", "US GOVERNMENT", "GOVERNMENT",
}


def parse_interest_fraction(text: Any) -> Optional[Fraction]:
    """Parse a runsheet interest value into an exact fraction of the estate.

    Accepts ``1/2``, ``0.25``, ``12.5%``, ``1/8 RI`` (leading token wins).
    Returns None if unparseable or clearly not a mineral fraction (>1).
    """
    t = norm_text(text)
    if not t:
        return None
    m = re.search(r"(\d+\s*/\s*\d+|\d*\.\d+|\d+(?:\.\d+)?)\s*(%?)", t)
    if not m:
        return None
    num, pct = m.group(1), m.group(2)
    try:
        if "/" in num:
            a, b = num.split("/")
            frac = Fraction(int(a.strip()), int(b.strip()))
        else:
            frac = Fraction(num)
    except (ValueError, ZeroDivisionError):
        return None
    if pct == "%":
        frac = frac / 100
    if frac < 0 or frac > 1:
        return None
    return frac


def chain_out_interest(merged: List["TitleRow"]) -> Dict[str, Any]:
    """Walk the chronological chain, moving the interest each instrument conveys
    from grantor to grantee with exact rational math. Never invents a holding:
    an unvested grantor is flagged as a gap.
    """
    ownership: Dict[str, Fraction] = {}
    links: List[Dict[str, Any]] = []
    warnings: List[str] = []
    name_notes: List[str] = []
    gap_count = 0

    for i, row in enumerate(merged, start=1):
        d = row.data
        # A lease (OGL) grants leasehold, not fee-mineral ownership, so it must
        # NOT walk the mineral chain -- it belongs in the OGL register. Detect a
        # lease row by doc type or an OGL number without a mineral instrument.
        dtype = norm_text(d.get("doc_type", "")).lower()
        has_ogl = bool(norm_text(d.get("ogl", "")))
        has_mineral_ref = bool(d.get("book") or d.get("instrument_no"))
        # Word-boundary match so "Release of Lien"/"Partial Release" (which
        # contain the substring "lease") are NOT mistaken for a lease.
        if (re.search(r"\blease\b", dtype) or re.search(r"\bogl\b", dtype)
                or (has_ogl and not has_mineral_ref)):
            continue
        grantor = norm_name(d.get("grantor", ""))
        grantee = norm_name(d.get("grantee", ""))
        interest = parse_interest_fraction(d.get("interest", ""))
        link = {
            "order": i,
            "date": d.get("instrument_date", "") or d.get("recorded_date", ""),
            "doc_type": d.get("doc_type", ""),
            "grantor": grantor, "grantee": grantee,
            "interest": interest,
            "ref": (f"Bk {d.get('book','')}/Pg {d.get('page','')}"
                    if d.get("book") and d.get("page")
                    else (f"Inst {d.get('instrument_no','')}"
                          if d.get("instrument_no") else "")),
            "legal": d.get("legal_description", ""),
            "remarks": d.get("remarks", ""),
        }
        links.append(link)

        if not grantee:
            warnings.append(f"Row {i}: blank grantee; interest not moved.")
            continue
        if grantor and grantor == grantee:
            warnings.append(f"Row {i}: grantor==grantee ({grantor}); correction, "
                            f"no interest moved.")
            continue
        if interest is None:
            warnings.append(f"Row {i} ({grantor}->{grantee}): interest "
                            f"'{norm_text(d.get('interest',''))}' unparseable; "
                            f"ledger not advanced.")
            continue

        is_root = grantor in _SOVEREIGN_ROOTS or not ownership
        if is_root:
            if grantor not in _SOVEREIGN_ROOTS:
                ownership[grantor] = ownership.get(grantor, Fraction(1))
                ownership[grantee] = ownership.get(grantee, Fraction(0)) + interest
                ownership[grantor] = ownership[grantor] - interest
            else:
                ownership[grantee] = ownership.get(grantee, Fraction(0)) + interest
            continue

        prev = ownership.get(grantor)
        if prev is None:
            # Tolerate minor name variance (a middle initial, a spelling
            # difference across sources) before declaring a vesting gap: match
            # the grantor to a currently-vested party by fuzzy similarity.
            match = _best_vested_match(grantor, ownership)
            if match is not None:
                name_notes.append(f"Row {i}: grantor '{grantor}' reconciled to "
                                  f"vested party '{match}' (name variance).")
                grantor = match
                prev = ownership.get(grantor)
        if prev is None:
            gap_count += 1
            warnings.append(f"Row {i}: grantor '{grantor}' not previously vested "
                            f"(chain gap -- examiner review).")
            ownership[grantee] = ownership.get(grantee, Fraction(0)) + interest
            ownership[grantor] = -interest
            continue
        ownership[grantee] = ownership.get(grantee, Fraction(0)) + interest
        ownership[grantor] = prev - interest

    ownership = {k: v for k, v in ownership.items() if v != 0}
    total = sum(ownership.values(), Fraction(0))
    reconciles = (bool(ownership) and gap_count == 0 and total == Fraction(1)
                  and all(v > 0 for v in ownership.values()))

    # A single consistent gross acreage lets us report net mineral acres.
    gross = _single_gross_acreage(merged)
    return {"links": links, "ownership": ownership, "warnings": warnings,
            "name_notes": name_notes, "gap_count": gap_count, "total": total,
            "reconciles": reconciles, "gross_acres": gross}


def _name_core_tokens(name: str) -> set:
    """Significant name tokens, dropping single-letter middle initials."""
    return {t for t in name.split() if len(t) > 1}


def _name_match(a: str, b: str) -> bool:
    """True when two party names denote the same person despite minor variance
    (a middle initial, a suffix) -- conservative, so distinct parties are kept
    apart. Works without rapidfuzz (uses a surname-anchored token subset plus a
    character-ratio fallback for spelling variants)."""
    if a == b:
        return True
    ta, tb = _name_core_tokens(a), _name_core_tokens(b)
    ap, bp = a.split(), b.split()
    if ta and tb and (ta <= tb or tb <= ta) and ap and bp and ap[-1] == bp[-1]:
        # e.g. "ALICE J JONES" vs "ALICE JONES" (same surname, initial dropped).
        return True
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.90


def _best_vested_match(name: str, ownership: Dict[str, Fraction]) -> Optional[str]:
    """Return a currently-vested owner (positive balance) whose name matches
    ``name`` under :func:`_name_match`. A genuinely different grantor still
    surfaces as a gap; only name variance is reconciled."""
    for key, bal in ownership.items():
        if bal > 0 and key != name and _name_match(name, key):
            return key
    return None


def _single_gross_acreage(merged: List["TitleRow"]) -> Optional[float]:
    vals = set()
    for row in merged:
        raw = norm_text(row.data.get("acreage", ""))
        m = re.search(r"\d+(?:\.\d+)?", raw.replace(",", ""))
        if m:
            vals.add(round(float(m.group(0)), 4))
    return next(iter(vals)) if len(vals) == 1 else None


def _frac_str(v: Optional[Fraction]) -> str:
    if v is None:
        return "-"
    return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"


def write_chain_sheet(wb, chain: Dict[str, Any], section: str) -> None:
    """Add a 'Chain of Title' analysis sheet with the chained-out ownership."""
    name = "Chain of Title"
    if name in wb.sheetnames:
        del wb[name]
    ws = wb.create_sheet(title=name)
    r = 1
    ws.cell(row=r, column=1,
            value=f"{section} - Roger Mills County - Chained-Out Interest")
    r += 2

    ws.cell(row=r, column=1, value="CHAIN OF TITLE")
    r += 1
    headers = ["#", "Date", "Doc Type", "Grantor", "Grantee",
               "Interest Conveyed", "Book/Page/Inst", "Legal", "Remarks"]
    for c, h in enumerate(headers, start=1):
        ws.cell(row=r, column=c, value=h)
    r += 1
    for link in chain["links"]:
        vals = [link["order"], link["date"], link["doc_type"], link["grantor"],
                link["grantee"], _frac_str(link["interest"]), link["ref"],
                link["legal"], link["remarks"]]
        for c, v in enumerate(vals, start=1):
            ws.cell(row=r, column=c, value=v)
        r += 1
    r += 1

    ws.cell(row=r, column=1, value="CURRENT NET MINERAL OWNERSHIP (chained out)")
    r += 1
    gross = chain.get("gross_acres")
    own_headers = ["Owner", "Interest", "Decimal", "Percent"]
    if gross is not None:
        own_headers.append("Net Mineral Acres")
    for c, h in enumerate(own_headers, start=1):
        ws.cell(row=r, column=c, value=h)
    r += 1
    for owner, frac in sorted(chain["ownership"].items(),
                              key=lambda kv: (-float(kv[1]), kv[0])):
        vals = [owner, _frac_str(frac), round(float(frac), 6),
                f"{float(frac) * 100:.4f}%"]
        if gross is not None:
            vals.append(round(float(frac) * gross, 4))
        for c, v in enumerate(vals, start=1):
            ws.cell(row=r, column=c, value=v)
        r += 1
    r += 1

    recon = ("Ownership reconciles to 100%." if chain["reconciles"]
             else f"Ownership does NOT cleanly reconcile (sums to "
                  f"{_frac_str(chain['total'])}"
                  + ("; contains a chain-gap deficit"
                     if chain["gap_count"] else "") + ").")
    ws.cell(row=r, column=1, value=recon)
    r += 1
    if gross is not None:
        ws.cell(row=r, column=1,
                value=f"Net mineral acres = ownership x {gross} gross acres.")
        r += 1
    if chain.get("name_notes"):
        r += 1
        ws.cell(row=r, column=1, value="NAME RECONCILIATIONS (variance tolerated):")
        r += 1
        for n in chain["name_notes"]:
            ws.cell(row=r, column=1, value=n)
            r += 1
    if chain["warnings"]:
        r += 1
        ws.cell(row=r, column=1, value="EXAMINER REVIEW (chain notes):")
        r += 1
        for w in chain["warnings"]:
            ws.cell(row=r, column=1, value=w)
            r += 1


def write_ogl_sheet(wb, ogl_register: List[Dict[str, str]], section: str) -> None:
    """Add an 'OGL Register' sheet tying each OGL number to its lease details."""
    name = "OGL Register"
    if name in wb.sheetnames:
        del wb[name]
    ws = wb.create_sheet(title=name)
    ws.cell(row=1, column=1, value=f"{section} - OGL Register (from OGL sheet)")
    headers = ["OGL #", "Lessor", "Lessee", "Interest", "Book/Page/Inst", "Legal"]
    for c, h in enumerate(headers, start=1):
        ws.cell(row=3, column=c, value=h)
    r = 4
    for o in ogl_register:
        vals = [o["ogl"], o["lessor"], o["lessee"], o["interest"], o["source"],
                o["legal"]]
        for c, v in enumerate(vals, start=1):
            ws.cell(row=r, column=c, value=v)
        r += 1
    if not ogl_register:
        ws.cell(row=4, column=1,
                value="(no OGL numbers found in an OGL/lease column)")


# ----------------------------------------------------------------------------
# Output: copy template formatting, write data, save
# ----------------------------------------------------------------------------
def build_output(template_path: Path, output_path: Path, merged: List[TitleRow],
                 verified: Dict[str, bool], section: str) -> Tuple[str, int]:
    """Copy the template workbook (preserving styling) and write merged rows into
    the data sheet. Returns (data_sheet_name, rows_written)."""
    # openpyxl load+save preserves: merged cells, fonts, fills, borders, number
    # formats, column widths, row heights, formulas, print areas, page setup,
    # freeze panes, header/footer, sheet order and tab colors.
    wb = openpyxl.load_workbook(template_path, data_only=False)

    # find the sheet/header row in the template that looks like the data table
    target_ws = None
    header_row = 1
    header_map: Dict[int, str] = {}
    best = -1
    for ws in wb.worksheets:
        hr, hmap = _detect_header_row(ws)
        if len(hmap) > best:
            best, target_ws, header_row, header_map = len(hmap), ws, hr, hmap
    if target_ws is None or not header_map:
        # template has no recognizable table - create a clean one rather than guess
        target_ws = wb.active
        header_row = 1
        header_map = {}

    LOG(f"  template data sheet: '{target_ws.title}' (header row {header_row}, "
        f"{len(header_map)} mapped columns)")

    # capture a "style template" row = the first data row beneath the header so
    # new rows inherit the template's per-column cell styling.
    style_row_idx = header_row + 1
    col_to_field = dict(header_map)
    field_to_col = {v: k for k, v in col_to_field.items()}

    # if template had no headers, lay down our canonical headers in row 1
    if not field_to_col:
        for i, fld in enumerate(CANON_FIELDS, start=1):
            target_ws.cell(row=1, column=i, value=fld.replace("_", " ").title())
            field_to_col[fld] = i
        header_row, style_row_idx = 1, 2

    from copy import copy as _copy

    # Snapshot the style-row styling BEFORE any unmerge. A merged style band
    # keeps its styling only in the anchor cell, so resolve each column to its
    # anchor now; otherwise the unmerge below would leave most columns default.
    style_snap: Dict[int, Dict[str, Any]] = {}
    for col in field_to_col.values():
        cell = target_ws.cell(row=style_row_idx, column=col)
        src = cell
        if isinstance(cell, openpyxl.cell.cell.MergedCell):
            for rng in target_ws.merged_cells.ranges:
                if (rng.min_row <= style_row_idx <= rng.max_row
                        and rng.min_col <= col <= rng.max_col):
                    src = target_ws.cell(row=rng.min_row, column=rng.min_col)
                    break
        try:
            style_snap[col] = {
                "font": _copy(src.font), "fill": _copy(src.fill),
                "border": _copy(src.border), "alignment": _copy(src.alignment),
                "number_format": src.number_format,
                "protection": _copy(src.protection),
            }
        except Exception:
            style_snap[col] = {}

    def apply_style(dst_cell, col):
        snap = style_snap.get(col)
        if not snap:
            return
        try:
            dst_cell.font = snap["font"]
            dst_cell.fill = snap["fill"]
            dst_cell.border = snap["border"]
            dst_cell.alignment = snap["alignment"]
            dst_cell.number_format = snap["number_format"]
            dst_cell.protection = snap["protection"]
        except Exception:
            pass

    # Unmerge any merged ranges in the region we are about to write so that
    # assigning cell values cannot raise on a read-only MergedCell (common in
    # hand-formatted templates). Header/banner merges above the data stay intact.
    data_top = header_row + 1
    for rng in list(getattr(target_ws, "merged_cells", []).ranges
                    if getattr(target_ws, "merged_cells", None) else []):
        if rng.max_row >= data_top:
            try:
                target_ws.unmerge_cells(str(rng))
            except Exception:
                pass

    def _safe_set(cell_row: int, cell_col: int, value):
        try:
            c = target_ws.cell(row=cell_row, column=cell_col, value=value)
            return c
        except (AttributeError, ValueError):
            return None  # merged/locked target -- skip rather than abort

    write_row = header_row + 1
    rows_written = 0
    for row in merged:
        k = row.key()
        for fld, col in field_to_col.items():
            value = row.data.get(fld, "")
            cell = _safe_set(write_row, col, value or None)
            if cell is not None and write_row != style_row_idx:
                apply_style(cell, col)
        # verification flag in remarks column if present
        if "remarks" in field_to_col and not verified.get(k, False):
            rc = target_ws.cell(row=write_row, column=field_to_col["remarks"])
            existing = norm_text(rc.value)
            flag = "[REVIEW: not found in index]"
            if not isinstance(rc, openpyxl.cell.cell.MergedCell):
                rc.value = (existing + " " + flag).strip() if existing else flag
        write_row += 1
        rows_written += 1

    # stamp the section + generation note in an unobtrusive header cell if blank
    try:
        title_cell = target_ws.cell(row=1, column=1)
        if not norm_text(title_cell.value):
            title_cell.value = f"{section} - Roger Mills County - Cursory Title Report"
    except Exception:
        pass

    # Chain out the interest into a dedicated analysis sheet (the explicit ask:
    # actually chain out ownership, don't just copy the interest column).
    try:
        chain = chain_out_interest(merged)
        write_chain_sheet(wb, chain, section)
        LOG(f"  chain-out: {len(chain['ownership'])} owner(s), "
            f"reconciles={chain['reconciles']}, gaps={chain['gap_count']}")
    except Exception as exc:  # never let the analysis sheet block the main report
        LOG(f"  chain-out sheet skipped: {exc}", "WARN")
    try:
        ogl_register = collect_ogl_register(merged)
        write_ogl_sheet(wb, ogl_register, section)
        LOG(f"  OGL register: {len(ogl_register)} lease number(s)")
    except Exception as exc:
        LOG(f"  OGL register sheet skipped: {exc}", "WARN")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    wb.close()
    return target_ws.title, rows_written


# ----------------------------------------------------------------------------
# Backups
# ----------------------------------------------------------------------------
def backup_originals(recs: List[FileRec], support_dir: Path,
                     roots: Optional[Sequence[Path]] = None) -> Path:
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = support_dir / f"backup_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    # Stable index per distinct root path so same-basename roots (D:\A\Roger
    # Mills vs D:\B\Roger Mills) get distinct backup namespaces, not a collision.
    root_index = {str(r): i for i, r in enumerate(roots or [])}
    copied = 0
    failed: List[str] = []
    for rec in recs:
        try:
            prefix = ""
            if rec.root is not None:
                i = root_index.get(str(rec.root), 0)
                prefix = f"{i:02d}_{rec.root.name}"
            dest = backup_dir / prefix / rec.rel if prefix else backup_dir / rec.rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(rec.path, dest)  # copy2 preserves mtime; originals untouched
            copied += 1
        except Exception as exc:
            failed.append(rec.rel)
            LOG(f"  backup failed for {rec.rel}: {exc}", "WARN")
    LOG(f"Backed up {copied}/{len(recs)} originals -> {backup_dir}")
    if failed:
        # The safety promise is "every original is backed up before reading."
        # If some could not be copied (locked/OneDrive), say so prominently.
        LOG(f"WARNING: {len(failed)} original(s) were NOT backed up (locked/"
            f"in use): {', '.join(failed[:10])}"
            + (" ..." if len(failed) > 10 else ""), "ERROR")
    return backup_dir


# ----------------------------------------------------------------------------
# Support file writers
# ----------------------------------------------------------------------------
def write_inventory_csv(path: Path, recs: List[FileRec], analyses: Dict[str, WorkbookAnalysis]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["relative_path", "kind", "ext", "size_bytes", "modified",
                    "sheets", "best_header_cols", "data_rows", "style_score", "error"])
        for rec in sorted(recs, key=lambda r: r.rel.lower()):
            wa = analyses.get(str(rec.path))
            sheets = best_cols = data_rows = style = ""
            err = ""
            if wa:
                sheets = "|".join(s.name for s in wa.sheets)
                bs = wa.best_sheet
                best_cols = str(len(bs.header_map)) if bs else "0"
                data_rows = str(bs.data_rows) if bs else "0"
                style = f"{wa.style_score:.1f}"
                err = wa.error
            w.writerow([rec.rel, rec.kind, rec.ext, rec.size,
                        rec.mtime.strftime("%Y-%m-%d %H:%M:%S"),
                        sheets, best_cols, data_rows, style, err])


def write_audit_csv(path: Path, audit: List[Dict[str, str]], verified: Dict[str, bool]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        cols = ["key", "n_sources", "sources", "grantor", "grantee", "doc_type",
                "instrument_no", "book", "page", "index_verified"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for rec in audit:
            rec = dict(rec)
            rec["index_verified"] = "YES" if verified.get(rec["key"], False) else "NO"
            w.writerow(rec)


def score_report_quality(merged: List["TitleRow"], chain: Dict[str, Any],
                         ogl_register: List[Dict[str, str]],
                         verified: Dict[str, bool],
                         conflicts: List[Dict[str, str]]) -> Tuple[float, List[str]]:
    """Score the finished report 0-100 across examiner-ready dimensions.

    This is the measurable "how good is it" that turns 'loop till perfect' into a
    concrete target: each run prints the score and the weakest dimension, so
    successive runs (or a human fixing sources) can see the number climb.
    """
    n = len(merged)
    if n == 0:
        return 0.0, ["No rows merged -- nothing to score."]

    sourced = sum(1 for r in merged
                  if (r.data.get("book") and r.data.get("page"))
                  or r.data.get("instrument_no"))
    fill = sum(sum(1 for f in CANON_FIELDS if norm_text(r.data.get(f, "")))
               / len(CANON_FIELDS) for r in merged) / n
    verified_n = sum(1 for r in merged if verified.get(r.key(), False))
    gaps = chain.get("gap_count", 0)
    chain_integrity = 1.0 if chain.get("reconciles") else max(0.0, 1.0 - 0.2 * gaps)
    conflict_score = max(0.0, 1.0 - min(1.0, len(conflicts) / n))

    dims = [
        ("Rows traceable to a source (Book/Page or Inst#)", sourced / n, 30),
        ("Field completeness", fill, 20),
        ("Chain integrity (reconciles / no gaps)", chain_integrity, 25),
        ("Rows verified vs index/API", verified_n / n, 15),
        ("Low field-conflict rate", conflict_score, 10),
    ]
    score = sum(ratio * weight for _, ratio, weight in dims)
    lines = [f"REPORT QUALITY SCORE: {score:.1f} / 100"]
    for label, ratio, weight in sorted(dims, key=lambda d: d[1]):
        lines.append(f"  [{ratio * 100:5.1f}%] {label}  (weight {weight})")
    lines.append(f"  OGL numbers tied out: {len(ogl_register)}")
    weakest = min(dims, key=lambda d: d[1])
    lines.append(f"  Biggest improvement lever: {weakest[0]} "
                 f"({weakest[1] * 100:.0f}%).")
    return round(score, 1), lines


def write_conflicts_xlsx(path: Path, conflicts: List[Dict[str, str]]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Conflicts"
    headers = ["key", "field", "chosen", "alternatives", "sources"]
    ws.append(headers)
    for c in ws[1]:
        c.font = openpyxl.styles.Font(bold=True)
    for rec in conflicts:
        ws.append([rec.get(h, "") for h in headers])
    ws.freeze_panes = "A2"
    for i, h in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(14, min(60, len(h) + 10))
    if not conflicts:
        ws.append(["(no field-level conflicts detected across sources)"])
    wb.save(path)
    wb.close()


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------
def validate_output(output_path: Path, data_sheet: str, expected_rows: int) -> Tuple[bool, List[str]]:
    notes: List[str] = []
    ok = True
    if not output_path.exists():
        return False, [f"Output file missing: {output_path}"]
    try:
        wb = openpyxl.load_workbook(output_path, data_only=False)
        notes.append(f"Reopened OK. Sheets: {wb.sheetnames}")
        if data_sheet not in wb.sheetnames:
            ok = False
            notes.append(f"Expected data sheet '{data_sheet}' not found.")
        else:
            ws = wb[data_sheet]
            populated = sum(1 for row in ws.iter_rows()
                            if any(c.value not in (None, "") for c in row))
            notes.append(f"Data sheet '{data_sheet}' populated rows: {populated}")
            if expected_rows and populated < 2:
                ok = False
                notes.append("Data sheet appears empty despite merged rows.")
        # broken-formula heuristic
        broken = 0
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str) and c.value.startswith("=#"):
                        broken += 1
        notes.append(f"Suspect broken formulas: {broken}")
        wb.close()
    except Exception as exc:
        ok = False
        notes.append(f"Reopen FAILED (possible corruption): {exc}")
    return ok, notes


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Roger Mills Cursory Title Report builder (codexv1)")
    ap.add_argument("--root", required=True, action="append",
                    help="Root folder to scan recursively (repeatable: pass --root "
                         "once per source folder, e.g. 'Roger Mills', 'Roger Mills 2')")
    ap.add_argument("--output", required=True, help="Final .xlsx output path")
    ap.add_argument("--support-dir", required=True, help="Folder for support files")
    ap.add_argument("--section", default="31-12N-24W", help="Target section label")
    ap.add_argument("--template", default="", help="Explicit template .xlsx (else auto-detect)")
    ap.add_argument("--env-file", default="", help="Path to a .env with API keys "
                    "(else auto-detected near the roots)")
    ap.add_argument("--dry-run", action="store_true", help="Analyze & plan only; do not write final workbook")
    args = ap.parse_args(argv)

    # De-duplicate roots (resolved) so passing the same folder twice does not
    # double-inventory / double-back-up every file.
    roots: List[Path] = []
    _seen_roots = set()
    for r in args.root:
        rp = Path(r)
        try:
            key = str(rp.resolve())
        except OSError:
            key = str(rp)
        if key not in _seen_roots:
            _seen_roots.add(key)
            roots.append(rp)
    output_path = Path(args.output)
    support_dir = Path(args.support_dir)

    missing = [str(r) for r in roots if not r.exists()]
    if missing:
        print(f"FATAL: root folder(s) do not exist: {', '.join(missing)}")
        print("Are you running this on the machine where the files live?")
        return 2
    support_dir.mkdir(parents=True, exist_ok=True)

    # Load .env (API keys) -- explicit, else auto-detect near the roots / parents.
    env_candidates = ([Path(args.env_file)] if args.env_file else [])
    for r in roots:
        env_candidates += [r / ".env", r.parent / ".env"]
    env_loaded = 0
    for cand in env_candidates:
        env_loaded = load_dotenv(cand)
        if env_loaded:
            LOG(f"Loaded {env_loaded} var(s) from {cand}")
            break

    LOG.section(f"Roger Mills Title Report Builder - section {args.section}")
    LOG(f"Roots:       {', '.join(str(r) for r in roots)}")
    LOG(f"Output:      {output_path}")
    LOG(f"Support dir: {support_dir}")
    LOG(f"Capabilities: pandas={_HAVE_PANDAS} dateutil={_HAVE_DATEUTIL} "
        f"rapidfuzz={_HAVE_RAPIDFUZZ} pdfplumber={_HAVE_PDFPLUMBER} "
        f"pymupdf={_HAVE_PYMUPDF} ocr={_HAVE_OCR}")

    # 1. inventory each root (never ingest our own support dir / output / artifacts)
    LOG.section("1. Inventory")
    recs: List[FileRec] = []
    for r in roots:
        recs += inventory(r, exclude=[support_dir, output_path])
    LOG(f"Found {len(recs)} files across {len(roots)} root(s).")
    for kind in ("template", "report", "runsheet", "index_pdf", "data", "doc", "image", "other"):
        n = sum(1 for r in recs if r.kind == kind)
        if n:
            LOG(f"  {kind:10s}: {n}")

    # 2. backups (skip in dry-run)
    if not args.dry_run:
        LOG.section("2. Timestamped backups")
        backup_originals(recs, support_dir, roots=roots)
    else:
        LOG("DRY-RUN: skipping backups.")

    # 3. analyze workbooks
    LOG.section("3. Analyze workbooks")
    analyses: Dict[str, WorkbookAnalysis] = {}
    for rec in recs:
        if rec.ext in WORKBOOK_EXT:
            wa = analyze_workbook(rec)
            analyses[str(rec.path)] = wa
            bs = wa.best_sheet
            LOG(f"  {rec.rel}: sheets={len(wa.sheets)} "
                f"best_cols={(len(bs.header_map) if bs else 0)} "
                f"rows={(bs.data_rows if bs else 0)} style={wa.style_score:.1f} "
                f"{('ERR ' + wa.error) if wa.error else ''}")

    # template selection
    template_rec = None
    if args.template:
        template_rec = next((r for r in recs if r.path.name.lower() == Path(args.template).name.lower()
                             or str(r.path).lower() == args.template.lower()), None)
    if template_rec is None:
        # Only real, openable templates: .xlsx/.xlsm, no ~$ lock stubs. Prefer an
        # exact "template(30)"-style name, then newest, for a deterministic pick.
        templates = [r for r in recs if r.kind == "template"
                     and r.ext in (".xlsx", ".xlsm")
                     and not r.path.name.startswith("~$")]
        templates.sort(key=lambda r: ("template(" not in r.path.name.lower(),
                                      -r.mtime.timestamp()))
        template_rec = templates[0] if templates else None

    # 4. tournament: pick best base report workbook
    LOG.section("4. Best-base tournament")
    report_analyses = [analyses[str(r.path)] for r in recs
                       if r.kind in ("report",) and str(r.path) in analyses]
    if recs:
        newest = max(r.mtime.timestamp() for r in recs)
        oldest = min(r.mtime.timestamp() for r in recs)
    else:
        newest = oldest = _dt.datetime.now().timestamp()
    scored = sorted(
        ((score_report(wa, newest, oldest), wa) for wa in report_analyses),
        key=lambda t: t[0], reverse=True,
    )
    for sc, wa in scored:
        LOG(f"  score={sc:6.3f}  {wa.rec.rel}")
    best_base = scored[0][1] if scored and scored[0][0] >= 0 else None

    if template_rec is None and best_base is not None:
        LOG("No Template(*) workbook found; using best-base report as formatting authority.", "WARN")
        template_rec = best_base.rec
    if template_rec is None:
        LOG("FATAL: no template and no usable report workbook found. Cannot build.", "ERROR")
        LOG.dump(support_dir / "build_log_codexv1.txt")
        return 3
    LOG(f"Formatting authority: {template_rec.rel}")
    if best_base:
        LOG(f"Best base data workbook: {best_base.rec.rel}")

    # 5. extract + merge rows from ALL report AND runsheet workbooks. The
    # runsheet is the primary chain-of-title source, so its rows must feed the
    # merge and the interest chain-out -- not just "report"-named workbooks.
    LOG.section("5. Extract & merge data")
    data_analyses = [analyses[str(r.path)] for r in recs
                     if r.kind in ("report", "runsheet") and str(r.path) in analyses]
    all_rows: List[List[TitleRow]] = []
    for wa in data_analyses:
        rows = extract_rows(wa)
        if rows:
            LOG(f"  {wa.rec.rel} [{wa.rec.kind}]: {len(rows)} rows")
            all_rows.append(rows)
    merged, audit, conflicts = merge_rows(all_rows)
    LOG(f"Merged unique records: {len(merged)}  | field conflicts: {len(conflicts)}")

    # 6. PDF / index verification
    LOG.section("6. Index PDF verification")
    index_text, method = "", "none"
    index_pdf = next((r for r in recs if r.kind == "index_pdf"), None)
    if index_pdf:
        LOG(f"Index PDF: {index_pdf.rel}")
        index_text, method = extract_pdf_text(index_pdf.path)
        LOG(f"Extraction method: {method}; chars={len(index_text)}")
        if method == "none":
            LOG("No PDF text/OCR available - rows will be marked unverified.", "WARN")
    else:
        LOG("No index PDF found.", "WARN")
    verified = verify_against_index(merged, index_text)
    n_verified = sum(1 for v in verified.values() if v)
    LOG(f"Rows verified against index: {n_verified}/{len(merged)}")

    # 6b. quality scorecard (the measurable target for 'loop till perfect')
    quality_chain = chain_out_interest(merged)
    quality_ogl = collect_ogl_register(merged)
    quality_score, quality_lines = score_report_quality(
        merged, quality_chain, quality_ogl, verified, conflicts)
    LOG.section("6b. Report quality")
    for ln in quality_lines:
        LOG(ln)

    # 7. build output
    data_sheet = ""
    rows_written = 0
    build_ok = False
    if args.dry_run:
        LOG.section("7. DRY-RUN: skipping final workbook write")
    else:
        LOG.section("7. Build final workbook")
        try:
            data_sheet, rows_written = build_output(
                template_rec.path, output_path, merged, verified, args.section)
            build_ok = True
            LOG(f"Wrote {rows_written} rows to sheet '{data_sheet}' -> {output_path}")
        except PermissionError as exc:
            LOG(f"Build failed (output not writable -- is it open in Excel/"
                f"OneDrive?): {exc}", "ERROR")
        except Exception as exc:
            LOG(f"Build failed: {exc}\n{traceback.format_exc()}", "ERROR")

    # 8. support files
    LOG.section("8. Support files")
    write_inventory_csv(support_dir / "source_inventory_codexv1.csv", recs, analyses)
    write_audit_csv(support_dir / "merge_audit_codexv1.csv", audit, verified)
    write_conflicts_xlsx(support_dir / "conflicts_review_codexv1.xlsx", conflicts)
    LOG("Wrote source_inventory_codexv1.csv, merge_audit_codexv1.csv, conflicts_review_codexv1.xlsx")

    # 9. validation
    LOG.section("9. Validation")
    val_lines: List[str] = []
    val_ok = True
    if not args.dry_run:
        if not build_ok:
            # Never let validation "PASS" by reopening a STALE prior output.
            val_ok = False
            val_lines = ["Build did not complete; the new report was NOT written "
                         "this run. Any existing output file is STALE."]
            LOG("VALIDATION: FAIL - build did not complete (output not written).",
                "ERROR")
        else:
            val_ok, notes = validate_output(output_path, data_sheet, rows_written)
            val_lines = notes
            for n in notes:
                LOG(f"  {n}")
            LOG(f"VALIDATION: {'PASS' if val_ok else 'FAIL - see notes'}")
    else:
        val_lines = ["DRY-RUN: final workbook not written; validation skipped."]

    # validation summary file
    summary = [
        "Roger Mills Title Report - final validation summary (codexv1)",
        f"Generated: {_dt.datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Section: {args.section}",
        "",
        f"Source files reviewed:   {len(recs)}",
        f"Workbooks analyzed:      {len(analyses)}",
        f"Report workbooks merged: {len(all_rows)}",
        f"Unique records merged:   {len(merged)}",
        f"Rows written to output:  {rows_written}",
        f"Field-level conflicts:   {len(conflicts)}",
        f"Index extraction method: {method}",
        f"Rows verified vs index:  {n_verified}/{len(merged)}",
        f"Formatting authority:    {template_rec.rel if template_rec else '(none)'}",
        f"Best base workbook:      {best_base.rec.rel if best_base else '(none)'}",
        f"Output workbook:         {output_path}",
        "",
        *quality_lines,
        "",
        "OCR / PDF note:",
    ]
    if method == "none":
        summary.append("  PDF text extraction and OCR were unavailable or returned no text.")
        summary.append("  Install pdfplumber/PyMuPDF and a Tesseract OCR engine to enable")
        summary.append("  full index verification, then re-run. Rows are currently marked")
        summary.append("  [REVIEW: not found in index] where they could not be confirmed.")
    else:
        summary.append(f"  Index extracted via '{method}'. {n_verified} rows confirmed present.")
    summary += ["", "Validation:", *[f"  {l}" for l in val_lines], "",
                "HUMAN REVIEW NEEDED:",
                "  - Any rows flagged [REVIEW: not found in index].",
                "  - All field conflicts in conflicts_review_codexv1.xlsx.",
                "  - Spot-check legal descriptions / acreage against the index PDF."]
    (support_dir / "final_validation_summary_codexv1.txt").write_text(
        "\n".join(summary) + "\n", encoding="utf-8")
    LOG("Wrote final_validation_summary_codexv1.txt")

    # build log last (captures everything above)
    LOG.dump(support_dir / "build_log_codexv1.txt")

    # final console report
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(f"Final workbook:        {output_path if not args.dry_run else '(dry-run, not written)'}")
    print(f"Support files in:      {support_dir}")
    print("  - source_inventory_codexv1.csv")
    print("  - merge_audit_codexv1.csv")
    print("  - conflicts_review_codexv1.xlsx")
    print("  - build_log_codexv1.txt")
    print("  - final_validation_summary_codexv1.txt")
    print(f"Source files reviewed: {len(recs)}")
    print(f"Records merged:        {len(merged)}  (written: {rows_written})")
    print(f"Conflicts found:       {len(conflicts)}")
    print(f"Index verified rows:   {n_verified}/{len(merged)}  (method: {method})")
    print(f"Report quality score:  {quality_score}/100")
    print("Human review:          see final_validation_summary_codexv1.txt")
    # Exit code reflects reality: non-zero on a failed build/validation so an
    # unattended caller (scheduled task) is not told a stale/absent report is fine.
    exit_code = 0 if (args.dry_run or (build_ok and val_ok)) else 2
    if exit_code != 0:
        print(f"\nRESULT: FAILED (exit {exit_code}) -- see build_log_codexv1.txt")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
