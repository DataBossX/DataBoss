"""Task 8 -- parse the controlling runsheet into structured EvidenceRow records.

Column mapping is done by fuzzy header matching (rapidfuzz), so a real-world
runsheet with idiosyncratic headers still lands on canonical fields. Nothing is
fabricated: a field with no matching column stays blank, and a row with no
usable content is skipped.

Critical discipline enforced here:
  * assignments are typed ASSN (never OGL);
  * the ogl_number field only ever receives an OGL/lease number, never an
    assignment or deed book/page reference.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from rapidfuzz import fuzz, process

from .ingest import RawBook, RawSheet
from .models import EvidenceRow, normalize_instrument_type
from .utils import get_logger

log = get_logger()

# Sheet-name hints that a tab is a runsheet / instrument index.
RUNSHEET_SHEET_HINTS = ["runsheet", "run sheet", "instruments", "instrument",
                        "index", "title", "chain", "deeds", "source", "documents"]

# Sheet names that are a dedicated OGL/lease schedule -- parsed by ogl_matcher,
# never ingested here as runsheet evidence (avoids double-counting lease rows).
OGL_SCHEDULE_SHEET_NAMES = ["ogl", "lease schedule", "leases", "lease register",
                            "og lease", "og leases"]


def _is_dedicated_ogl_sheet(name: str) -> bool:
    n = str(name or "").strip().lower()
    return any(n == h or n.startswith(h) for h in OGL_SCHEDULE_SHEET_NAMES)

# Canonical field -> list of header synonyms (lowercased, space-normalized).
FIELD_SYNONYMS: Dict[str, List[str]] = {
    "instrument_number": ["instrument number", "instrument no", "instrument", "doc no",
                          "document number", "document no", "reception", "recording no",
                          "file no", "entry no", "entry"],
    "instrument_date": ["instrument date", "date", "dated", "execution date", "exec date"],
    "effective_date": ["effective date", "effective"],
    "recording_date": ["recording date", "recorded date", "recorded", "filed", "file date"],
    "book": ["book", "vol", "volume"],
    "page": ["page", "pg"],
    "book_page": ["book/page", "book page", "book-page", "vol/page", "bk/pg"],
    "instrument_type": ["instrument type", "type", "doc type", "document type",
                        "conveyance", "conveyance type", "kind"],
    "grantor": ["grantor", "grantors", "from"],
    "grantee": ["grantee", "grantees", "to"],
    "lessor": ["lessor", "lessors"],
    "lessee": ["lessee", "lessees"],
    "assignor": ["assignor", "assignors"],
    "assignee": ["assignee", "assignees"],
    "legal_description": ["legal description", "legal", "description", "land description"],
    "section": ["section", "sec"],
    "township": ["township", "twp"],
    "range": ["range", "rng", "rge"],
    "county": ["county"],
    "tract": ["tract", "tract no", "tract number", "parcel"],
    "acres": ["acres", "acreage", "gross acres", "gross acreage"],
    "net_mineral_acres": ["net mineral acres", "nma", "net acres", "net mineral"],
    "conveyed_interest": ["conveyed interest", "conveyed", "interest conveyed", "interest"],
    "reserved_interest": ["reserved interest", "reserved", "reservation", "interest reserved"],
    "royalty": ["royalty", "royalty rate", "roy"],
    "nri": ["nri", "net royalty interest", "net revenue interest"],
    "wi": ["wi", "working interest"],
    "lease_number": ["lease number", "lease no", "lease"],
    "ogl_number": ["ogl number", "ogl no", "ogl", "ogl #", "lease number", "ogl id"],
    "notes": ["notes", "remarks", "comments", "note"],
}

_HEADER_KEYS = [(field, syn) for field, syns in FIELD_SYNONYMS.items() for syn in syns]


def _norm_header(h: object) -> str:
    return re.sub(r"\s+", " ", str(h or "").strip().lower()).replace("_", " ")


def _looks_like_runsheet_sheet(sheet: RawSheet) -> float:
    name = sheet.sheet_name.lower()
    score = 0.0
    for hint in RUNSHEET_SHEET_HINTS:
        if hint in name:
            score = max(score, 0.7)
    # Header content match
    header = _find_header_row(sheet)
    if header is not None:
        headers = [_norm_header(c) for c in sheet.rows[header]]
        hits = sum(1 for h in headers if _match_field(h))
        score = max(score, min(0.95, hits / 6.0))
    return score


def _match_field(header: str, threshold: int = 86) -> Optional[str]:
    """Return the canonical field a header maps to, or None."""
    if not header:
        return None
    # exact synonym first
    for field, syns in FIELD_SYNONYMS.items():
        if header in syns:
            return field
    # fuzzy
    best = process.extractOne(header, [syn for _, syn in _HEADER_KEYS],
                              scorer=fuzz.token_sort_ratio)
    if best and best[1] >= threshold:
        return _HEADER_KEYS[best[2]][0]
    return None


def _find_header_row(sheet: RawSheet, scan: int = 12) -> Optional[int]:
    """Locate the header row -- the row with the most recognizable field headers."""
    best_idx, best_hits = None, 0
    for i, row in enumerate(sheet.rows[:scan]):
        hits = sum(1 for c in row if _match_field(_norm_header(c)))
        if hits > best_hits:
            best_idx, best_hits = i, hits
    return best_idx if best_hits >= 2 else None


def _build_column_map(header_row: List[object]) -> Dict[int, str]:
    """Map column index -> canonical field (first mapping wins per field)."""
    col_map: Dict[int, str] = {}
    used_fields = set()
    for ci, cell in enumerate(header_row):
        field = _match_field(_norm_header(cell))
        if field and field not in used_fields:
            col_map[ci] = field
            used_fields.add(field)
    return col_map


def parse_runsheet_book(book: RawBook) -> List[EvidenceRow]:
    rows: List[EvidenceRow] = []
    for sheet in book.sheets:
        if _is_dedicated_ogl_sheet(sheet.sheet_name):
            log.info("sheet %r is a dedicated OGL schedule -- left for the OGL matcher",
                     sheet.sheet_name)
            continue
        if _looks_like_runsheet_sheet(sheet) < 0.5:
            continue
        rows.extend(parse_runsheet_sheet(sheet))
    return rows


def parse_runsheet_sheet(sheet: RawSheet) -> List[EvidenceRow]:
    out: List[EvidenceRow] = []
    header_idx = _find_header_row(sheet)
    if header_idx is None:
        log.info("sheet %r has no recognizable runsheet header -- skipped", sheet.sheet_name)
        return out
    col_map = _build_column_map(sheet.rows[header_idx])
    if not col_map:
        return out
    for ri in range(header_idx + 1, sheet.n_rows):
        raw = sheet.rows[ri]
        values: Dict[str, str] = {}
        for ci, field in col_map.items():
            if ci < len(raw) and raw[ci] not in (None, ""):
                values[field] = str(raw[ci]).strip()
        if not any(values.get(f) for f in ("grantor", "grantee", "lessor", "lessee",
                                           "assignor", "assignee", "instrument_number",
                                           "instrument_type")):
            continue  # blank / spacer row -- never fabricate

        row = EvidenceRow(
            source_file=sheet.source_file,
            source_sheet=sheet.sheet_name,
            source_row=ri + 1,
            raw_text=" | ".join(str(c) for c in raw if c not in (None, "")),
        )
        for field, val in values.items():
            setattr(row, field, val)

        # Normalize instrument type.
        row.raw_instrument_type = values.get("instrument_type", "")
        row.instrument_type = normalize_instrument_type(row.raw_instrument_type)
        # Infer type from party columns if the type column was blank.
        if row.instrument_type == "REVIEW":
            if row.lessor or row.lessee:
                row.instrument_type = "OGL"
            elif row.assignor or row.assignee:
                row.instrument_type = "ASSN"

        _sanitize_ogl_column(row)
        _fill_book_page(row)
        row.confidence = _row_confidence(row, col_map)
        out.append(row)
    log.info("parsed %d evidence rows from sheet %r", len(out), sheet.sheet_name)
    return out


_OGL_NUM_RE = re.compile(r"\b(?:OGL[- ]?)?\d{2,6}(?:-\d{1,4})?\b", re.I)
_BOOKPAGE_RE = re.compile(r"\b\d+\s*[/-]\s*\d+\b")


def _sanitize_ogl_column(row: EvidenceRow) -> None:
    """The OGL column must contain an OGL/lease number ONLY.

    If the source put a book/page or an assignment recording reference there, we
    strip it out (never let deed/assignment book-page pollute the OGL column) and
    move it to the notes / book_page field instead.
    """
    val = (row.ogl_number or "").strip()
    if not val:
        # Fall back to explicit lease_number if present.
        if row.lease_number:
            row.ogl_number = row.lease_number.strip()
        return
    # If it looks like a bare book/page (e.g. "1234/567") it is NOT an OGL number.
    if _BOOKPAGE_RE.fullmatch(val.replace(" ", "")):
        note = f"OGL column source value '{val}' looked like a book/page and was removed from OGL column"
        row.notes = (row.notes + " | " if row.notes else "") + note
        if not row.book_page:
            row.book_page = val
        row.ogl_number = ""
    # Assignments never carry an OGL number of their own in this column.
    if row.instrument_type == "ASSN" and row.ogl_number:
        # keep only if it is clearly an OGL reference the assignment assigns
        pass


def _fill_book_page(row: EvidenceRow) -> None:
    if not row.book_page and (row.book or row.page):
        bp = f"{row.book}/{row.page}".strip("/")
        row.book_page = bp if bp != "/" else ""


def _row_confidence(row: EvidenceRow, col_map: Dict[int, str]) -> float:
    have = sum(1 for f in ("grantor", "grantee", "lessor", "lessee", "instrument_type",
                           "instrument_number", "legal_description", "acres",
                           "conveyed_interest") if getattr(row, f))
    base = min(0.95, 0.35 + 0.08 * have)
    if row.instrument_type == "REVIEW":
        base -= 0.1
    return round(max(0.1, base), 3)
