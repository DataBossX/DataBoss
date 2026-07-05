"""Typed schema for every artifact the engine produces.

Pydantic models give the QA gate a contract to check against. A row that fails
the schema is never silently dropped or auto-filled -- it is surfaced as a
review flag.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

# Instrument-type normalization map (spec Eighth Task).
INSTRUMENT_NORMALIZATION = {
    "warranty deed": "WD",
    "general warranty deed": "WD",
    "special warranty deed": "WD",
    "quit claim deed": "QCD",
    "quitclaim deed": "QCD",
    "mineral deed": "MD",
    "royalty deed": "RD",
    "oil and gas lease": "OGL",
    "oil & gas lease": "OGL",
    "paid up oil and gas lease": "OGL",
    "assignment": "ASSN",
    "assignment of oil and gas lease": "ASSN",
    "assignment of oil & gas lease": "ASSN",
    "partial assignment": "ASSN",
    "release": "REL",
    "release of oil and gas lease": "REL",
    "affidavit": "AFF",
    "affidavit of heirship": "AFF",
    "probate": "PROBATE",
    "order": "ORDER",
    "final decree": "ORDER",
    "trust": "TRUST",
    "trust agreement": "TRUST",
    "mortgage": "MTG",
    "easement": "ESMT",
    "right of way": "ESMT",
    "pooling": "POOLING",
    "pooling order": "POOLING",
    "unknown": "REVIEW",
}

INSTRUMENT_CODES = set(INSTRUMENT_NORMALIZATION.values())


def normalize_instrument_type(raw: Optional[str]) -> str:
    """Map a free-text instrument type onto a canonical code. Unknown -> REVIEW."""
    if not raw:
        return "REVIEW"
    s = str(raw).strip().lower()
    if s.upper() in INSTRUMENT_CODES:
        return s.upper()
    if s in INSTRUMENT_NORMALIZATION:
        return INSTRUMENT_NORMALIZATION[s]
    # Substring heuristics (longest/most-specific first).
    for phrase in sorted(INSTRUMENT_NORMALIZATION, key=len, reverse=True):
        if phrase in s:
            return INSTRUMENT_NORMALIZATION[phrase]
    return "REVIEW"


class FileRecord(BaseModel):
    path: str
    name: str
    ext: str
    size_bytes: int = 0
    modified: str = ""
    sha256: str = ""
    role: str = "unclassified"
    confidence: float = 0.0
    notes: str = ""


class EvidenceRow(BaseModel):
    """One parsed instrument row from the controlling runsheet."""

    source_file: str = ""
    source_sheet: str = ""
    source_row: Optional[int] = None
    instrument_number: str = ""
    instrument_date: str = ""
    effective_date: str = ""
    recording_date: str = ""
    book: str = ""
    page: str = ""
    book_page: str = ""
    instrument_type: str = "REVIEW"
    raw_instrument_type: str = ""
    grantor: str = ""
    grantee: str = ""
    lessor: str = ""
    lessee: str = ""
    assignor: str = ""
    assignee: str = ""
    legal_description: str = ""
    section: str = ""
    township: str = ""
    range: str = ""
    county: str = ""
    tract: str = ""
    acres: str = ""
    net_mineral_acres: str = ""
    conveyed_interest: str = ""
    reserved_interest: str = ""
    royalty: str = ""
    nri: str = ""
    wi: str = ""
    lease_number: str = ""
    ogl_number: str = ""
    notes: str = ""
    raw_text: str = ""
    confidence: float = 0.0


class ChainEvent(BaseModel):
    tract: str
    seq: int
    instrument_number: str = ""
    instrument_type: str = ""
    instrument_date: str = ""
    grantor: str = ""
    grantee: str = ""
    action: str = ""
    before_acres: str = ""
    conveyed_acres: str = ""
    after_acres: str = ""
    retained_acres: str = ""
    ogl_reference: str = ""
    assn_reference: str = ""
    evidence: str = ""
    assumption: str = ""
    flag: str = ""
    confidence: float = 0.0
    notes: str = ""


class FinalOwner(BaseModel):
    tract: str
    owner: str
    conveyance_type: str = ""
    instrument_number: str = ""
    net_acres: str = ""
    mineral_interest: str = ""
    wi: str = ""
    royalty: str = ""
    ogl_number: str = ""
    book_page: str = ""
    status: str = "ok"
    is_assumption: bool = False
    notes: str = ""


class Assumption(BaseModel):
    tract: str
    kind: str
    statement: str
    basis: str = ""
    confidence_penalty: float = 0.0
    location: str = ""  # sheet/cell reference where highlighted


class ReviewFlag(BaseModel):
    tract: str
    severity: str  # red | yellow | green
    category: str
    message: str
    instrument_number: str = ""
    recommended_action: str = ""


class AuditEntry(BaseModel):
    timestamp: str
    tract: str
    source_file: str = ""
    source_sheet: str = ""
    source_row: Optional[int] = None
    instrument_type: str = ""
    grantor: str = ""
    grantee: str = ""
    action: str = ""
    before_acres: str = ""
    conveyed_acres: str = ""
    after_acres: str = ""
    retained_acres: str = ""
    ogl_reference: str = ""
    assn_reference: str = ""
    evidence: str = ""
    assumption: str = ""
    flag: str = ""
    confidence: float = 0.0
    notes: str = ""


class TractResult(BaseModel):
    tract: str
    control_acres: Optional[str] = None
    control_source: str = ""
    events: List[ChainEvent] = Field(default_factory=list)
    final_owners: List[FinalOwner] = Field(default_factory=list)
    assumptions: List[Assumption] = Field(default_factory=list)
    flags: List[ReviewFlag] = Field(default_factory=list)
    evidence_score: int = 0
    balanced: bool = False
    balance_note: str = ""
