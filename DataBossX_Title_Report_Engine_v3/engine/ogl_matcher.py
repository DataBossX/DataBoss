"""Task 9 -- match runsheet OGL rows to the OGL / lease schedule.

Matching uses OGL number, lessor, lessee, legal, date, and book/page with a
composite confidence score. Discipline: the OGL column carries only an OGL /
lease reference; book/page and assignment recording references never land there.
Unmatched leases are flagged both ways (runsheet-not-in-schedule and
schedule-not-chained).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from rapidfuzz import fuzz

from .ingest import RawBook, RawSheet
from .models import EvidenceRow
from .parser import _find_header_row, _norm_header, _match_field
from .utils import get_logger

log = get_logger()

OGL_SHEET_HINTS = ["ogl", "lease", "lease schedule", "leases", "og"]


@dataclass
class OGLScheduleRow:
    source_row: int
    ogl_number: str = ""
    lessor: str = ""
    lessee: str = ""
    effective_date: str = ""
    recording_date: str = ""
    book_page: str = ""
    legal_description: str = ""
    royalty: str = ""
    term: str = ""
    tract: str = ""
    acres: str = ""
    status: str = ""


@dataclass
class OGLMatch:
    ogl_number: str
    runsheet_row: Optional[int]
    schedule_row: Optional[int]
    confidence: float
    status: str  # matched | unmatched_ogl | ogl_not_chained
    detail: str = ""


def _is_ogl_sheet(sheet: RawSheet) -> bool:
    n = sheet.sheet_name.lower()
    if any(h in n for h in OGL_SHEET_HINTS):
        return True
    hdr = _find_header_row(sheet)
    if hdr is None:
        return False
    headers = [_norm_header(c) for c in sheet.rows[hdr]]
    return sum(1 for h in headers if h in ("lessor", "lessee", "ogl", "ogl number")) >= 2


def parse_ogl_schedule(book: RawBook) -> List[OGLScheduleRow]:
    out: List[OGLScheduleRow] = []
    for sheet in book.sheets:
        if not _is_ogl_sheet(sheet):
            continue
        hdr = _find_header_row(sheet)
        if hdr is None:
            continue
        col_map: Dict[int, str] = {}
        for ci, cell in enumerate(sheet.rows[hdr]):
            field = _match_field(_norm_header(cell))
            if field:
                col_map[ci] = field
        for ri in range(hdr + 1, sheet.n_rows):
            raw = sheet.rows[ri]
            vals = {col_map[ci]: str(raw[ci]).strip()
                    for ci in col_map if ci < len(raw) and raw[ci] not in (None, "")}
            if not any(vals.get(f) for f in ("ogl_number", "lease_number", "lessor", "lessee")):
                continue
            out.append(OGLScheduleRow(
                source_row=ri + 1,
                ogl_number=vals.get("ogl_number") or vals.get("lease_number", ""),
                lessor=vals.get("lessor", ""), lessee=vals.get("lessee", ""),
                effective_date=vals.get("effective_date", ""),
                recording_date=vals.get("recording_date", ""),
                book_page=vals.get("book_page", ""),
                legal_description=vals.get("legal_description", ""),
                royalty=vals.get("royalty", ""), tract=vals.get("tract", ""),
                acres=vals.get("acres", ""),
            ))
    log.info("parsed %d OGL schedule rows", len(out))
    return out


def _score(rs: EvidenceRow, og: OGLScheduleRow) -> float:
    score, weight = 0.0, 0.0
    def cmp(a, b, w):
        nonlocal score, weight
        if a and b:
            weight += w
            score += w * (fuzz.token_sort_ratio(str(a).lower(), str(b).lower()) / 100.0)
    # exact OGL number match dominates
    if rs.ogl_number and og.ogl_number and \
       rs.ogl_number.replace(" ", "").upper() == og.ogl_number.replace(" ", "").upper():
        return 1.0
    cmp(rs.lessor or rs.grantor, og.lessor, 0.35)
    cmp(rs.lessee or rs.grantee, og.lessee, 0.35)
    cmp(rs.legal_description, og.legal_description, 0.15)
    cmp(rs.book_page, og.book_page, 0.1)
    cmp(rs.recording_date, og.recording_date, 0.05)
    return round(score / weight, 3) if weight else 0.0


def match_ogls(evidence: List[EvidenceRow], schedule: List[OGLScheduleRow],
               threshold: float = 0.72) -> List[OGLMatch]:
    matches: List[OGLMatch] = []
    matched_sched = set()
    ogl_rows = [r for r in evidence if r.instrument_type == "OGL" or r.ogl_number]
    for rs in ogl_rows:
        best, best_score = None, 0.0
        for og in schedule:
            s = _score(rs, og)
            if s > best_score:
                best, best_score = og, s
        if best and best_score >= threshold:
            matched_sched.add(best.source_row)
            matches.append(OGLMatch(
                ogl_number=rs.ogl_number or best.ogl_number,
                runsheet_row=rs.source_row, schedule_row=best.source_row,
                confidence=best_score, status="matched",
                detail=f"lessor≈{best.lessor}; lessee≈{best.lessee}"))
        else:
            matches.append(OGLMatch(
                ogl_number=rs.ogl_number, runsheet_row=rs.source_row,
                schedule_row=None, confidence=best_score, status="unmatched_ogl",
                detail="OGL referenced in runsheet but not found in OGL schedule"))
    # Schedule leases never chained in the runsheet.
    for og in schedule:
        if og.source_row not in matched_sched:
            matches.append(OGLMatch(
                ogl_number=og.ogl_number, runsheet_row=None,
                schedule_row=og.source_row, confidence=0.0, status="ogl_not_chained",
                detail="Lease in OGL schedule with no matching runsheet instrument"))
    return matches
