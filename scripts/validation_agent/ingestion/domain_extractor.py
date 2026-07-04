"""Best-effort domain extraction from a workbook.

This turns raw cells into (a) a de-duplicated set of recording references
(book/page + instrument numbers) for the source finder, and (b) light structural
facts (tract legals/acreage, well API/status) where the layout makes them
unambiguous.

Honesty rules:
  * Where a value cannot be parsed unambiguously it is left ``None`` so the
    validators ESCALATE rather than the extractor guessing.
  * The extractor NEVER computes or invents ownership fractions, net acres,
    conveyed/retained interest, or HBP support. Those remain examiner inputs.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import openpyxl

BOOK_PAGE_RE = re.compile(r"\b(\d{3,4})\s*/\s*(\d{1,4})\b")
INSTRUMENT_RE = re.compile(r"\b(\d{4}-\d{5,6})\b")
API_RE = re.compile(r"\b(35-\d{3}-\d{5})\b")
TRACT_RE = re.compile(r"\bTRACT\s*0*([0-9]{1,2})\s*[:\-]", re.IGNORECASE)
ACRES_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*acres", re.IGNORECASE)


def _iter_string_cells(workbook_path: Path):
    wb = openpyxl.load_workbook(workbook_path, data_only=True, read_only=True)
    try:
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                for v in row:
                    if isinstance(v, str) and v.strip():
                        yield ws.title, v
    finally:
        wb.close()


def extract_references(workbook_path: Path) -> Dict[str, List[str]]:
    books, insts = set(), set()
    for _sheet, text in _iter_string_cells(workbook_path):
        for m in BOOK_PAGE_RE.finditer(text):
            books.add(f"{m.group(1)}/{m.group(2)}")
        for m in INSTRUMENT_RE.finditer(text):
            insts.add(m.group(1))
    return {"book_page": sorted(books), "instrument_number": sorted(insts)}


def extract_well(workbook_path: Path) -> Optional[Dict[str, Any]]:
    api = None
    status = None
    for _sheet, text in _iter_string_cells(workbook_path):
        m = API_RE.search(text)
        if m and not api:
            api = m.group(1)
        low = text.lower()
        if "active" in low and status is None:
            status = "active_claimed"
        if "inactive" in low:
            status = "inactive_claimed"
    if not api:
        return None
    # HBP support is never asserted by the extractor; production evidence must be
    # supplied from OTC by the examiner/source layer.
    return {"name": "well of record", "api": api, "occ_status": status,
            "hbp_supported": None, "production_evidence": None}


def extract_tracts(workbook_path: Path) -> List[Dict[str, Any]]:
    """Detect tract headers + containing-acreage where present. Owners/interest
    are intentionally NOT extracted (cannot be done safely across layouts)."""
    tracts: Dict[int, Dict[str, Any]] = {}
    pending: Optional[int] = None
    for _sheet, text in _iter_string_cells(workbook_path):
        tm = TRACT_RE.search(text)
        if tm:
            pending = int(tm.group(1))
            tracts.setdefault(pending, {"tract": pending, "gross_acres": None,
                                        "owners": None, "conveyances": None})
        elif pending is not None:
            am = ACRES_RE.search(text)
            if am and "containing" in text.lower():
                tracts[pending]["gross_acres"] = am.group(1)
                pending = None
    return [tracts[k] for k in sorted(tracts)]


def extract_domain(workbook_path: Path) -> Dict[str, Any]:
    workbook_path = Path(workbook_path)
    refs = extract_references(workbook_path)
    tracts = extract_tracts(workbook_path)
    well = extract_well(workbook_path)
    return {
        "references": refs,
        "reference_count": len(refs["book_page"]) + len(refs["instrument_number"]),
        # tracts have no owner/interest data -> conservation/chain gates ESCALATE,
        # which is the correct, non-fabricating behavior.
        "tracts": tracts or None,
        "well": well,
        "instruments": [{"book_page": bp} for bp in refs["book_page"]]
                       + [{"instrument_number": i} for i in refs["instrument_number"]] or None,
    }
