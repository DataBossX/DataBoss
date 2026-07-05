"""Stage 4 -- match leases in the runsheet to rows on the OGL sheet.

The OGL sheet is the authority for lease numbers. This module builds an index of
OGL records (by lessor, lessee, legal, date, book/page, and OGL number) and
attaches the authoritative OGL number to each lease/assignment evidence row,
using fuzzy matching on parties + exact matching on book/page when available.

Only genuine OGL-style references ever populate the ``lease_number`` field
(rule #7); a book/page pair is never treated as an OGL number (rule #8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from rapidfuzz import fuzz

from .audit import AuditLog
from .models import ConveyanceType, EvidenceRow

MATCH_THRESHOLD = 82


@dataclass
class OGLRecord:
    ogl_number: Optional[str]
    lessor: str
    lessee: str
    legal: str
    date: Optional[str]
    book_page: Optional[str]
    source_sheet: str
    source_row: Optional[int]


def build_ogl_index(ogl_rows: List[EvidenceRow]) -> List[OGLRecord]:
    index: List[OGLRecord] = []
    for ev in ogl_rows:
        index.append(OGLRecord(
            ogl_number=ev.lease_number,
            lessor=ev.grantor, lessee=ev.grantee, legal=ev.legal_description,
            date=ev.instrument_date, book_page=ev.book_page,
            source_sheet=ev.source_sheet, source_row=ev.source_row,
        ))
    return index


def _score(ev: EvidenceRow, rec: OGLRecord) -> int:
    score = 0
    if ev.book_page and rec.book_page and _norm(ev.book_page) == _norm(rec.book_page):
        score += 50  # book/page identity is decisive
    score += int(0.30 * fuzz.token_sort_ratio(_norm(ev.grantor), _norm(rec.lessor)))
    score += int(0.20 * fuzz.token_sort_ratio(_norm(ev.grantee), _norm(rec.lessee)))
    if ev.instrument_date and rec.date and ev.instrument_date == rec.date:
        score += 15
    if ev.lease_number and rec.ogl_number and ev.lease_number == rec.ogl_number:
        score += 40
    return score


def _norm(s) -> str:
    return " ".join(str(s or "").upper().replace(".", "").replace(",", " ").split())


def match_leases(evidence: List[EvidenceRow], ogl_index: List[OGLRecord],
                 audit: AuditLog) -> int:
    """Attach authoritative OGL numbers to lease/assignment rows.

    Returns the count of rows that could NOT be matched (become review flags).
    """
    if not ogl_index:
        return 0
    unmatched = 0
    for ev in evidence:
        if ev.conveyance_type not in (ConveyanceType.LEASE, ConveyanceType.ASSIGNMENT):
            continue
        best, best_score = None, MATCH_THRESHOLD - 1
        for rec in ogl_index:
            s = _score(ev, rec)
            if s > best_score:
                best, best_score = rec, s
        if best and best.ogl_number:
            if ev.lease_number != best.ogl_number:
                before = ev.lease_number or "(none)"
                ev.lease_number = best.ogl_number
                audit.record("MATCH lease to OGL sheet", tract=ev.tract,
                             source_sheet=ev.source_sheet, source_row=ev.source_row,
                             before=f"OGL {before}", after=f"OGL {best.ogl_number}",
                             evidence=f"matched OGL row [{best.source_sheet} "
                                      f"r{best.source_row}] score={best_score}")
        else:
            unmatched += 1
            audit.record("UNMATCHED lease -- no OGL record", tract=ev.tract,
                         source_sheet=ev.source_sheet, source_row=ev.source_row,
                         before=ev.lease_number or "(none)", after="(unmatched)",
                         evidence=_ev(ev), flag="unmatched_ogl")
    return unmatched


def _ev(ev: EvidenceRow) -> str:
    return f"{ev.grantor} -> {ev.grantee}; Bk/Pg {ev.book_page or '?'}"
