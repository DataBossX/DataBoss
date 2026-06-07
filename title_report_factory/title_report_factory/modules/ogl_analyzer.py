"""ogl_analyzer -- build normalized lease records from the source OGL sheet."""
from __future__ import annotations

from ..model import Lease
from . import source_reader
from .party_and_date_extractor import to_short_date
from .interest_extractor import parse_royalty, parse_acres
from .legal_description_extractor import tract_for_quarter, extract_quarter_calls


def _g(d: dict, *names, default=""):
    for n in names:
        for k in d:
            if k.strip().replace("\n", " ").lower() == n.lower():
                v = d[k]
                if v is not None and str(v).strip():
                    return v
    return default


def _lease_confidence(lease: Lease) -> int:
    """Index-only leases score lower; first-page-reviewed leases score higher."""
    status = (lease.data_status or "").lower()
    if "first-page lease terms captured" in status:
        score = 70
    elif "needs full lease abstraction" in status:
        score = 45
    else:
        score = 50
    if lease.royalty and lease.royalty.lower() not in {"not verified", ""}:
        score += 5
    if lease.execution_date:
        score += 5
    return min(score, 80)  # capped: no full image review => never "strong"


def build_leases(path: str, sheet: str, subject: dict) -> list[Lease]:
    rows = source_reader.read_sheet(path, sheet)
    dicts = source_reader.as_dicts(rows, header_row=0)
    leases: list[Lease] = []
    for d in dicts:
        legal = str(_g(d, "Legal Description", "Legal\nDescription")).strip()
        lease = Lease(
            ogl_no=str(_g(d, "OGL #", "OGL No.")).strip(),
            image_no=str(_g(d, "Image #")).strip(),
            instrument_no=str(_g(d, "Instrument")).strip(),
            book_page=str(_g(d, "Bk./Pg.", "Book/Page")).strip(),
            execution_date=to_short_date(_g(d, "Execution Date", "Execution\nDate")),
            filing_date=to_short_date(_g(d, "Filing Date", "Filing\nDate")),
            grantor=str(_g(d, "Grantor")).strip(),
            grantee=str(_g(d, "Grantee")).strip(),
            legal_description=legal,
            notes=str(_g(d, "Misc. Notes")).strip(),
            term=str(_g(d, "Term")).strip(),
            gross_acres=parse_acres(_g(d, "Gross Acres")),
            tracts=tract_for_quarter(legal) or extract_quarter_calls(legal),
            exp_date=to_short_date(_g(d, "Exp Date")) or str(_g(d, "Exp Date")).strip(),
            net_acres=parse_acres(_g(d, "Net Mineral Acres", "Net Mineral\nAcres", "Net Acres")),
            royalty=parse_royalty(_g(d, "Royalty")),
            source_status=str(_g(d, "Source Status")).strip(),
            data_status=str(_g(d, "Data Status")).strip(),
            source_file=str(_g(d, "Source File")).strip(),
        )
        if not (lease.ogl_no or lease.instrument_no):
            continue
        lease.confidence = _lease_confidence(lease)
        leases.append(lease)
    return leases
