"""Shared data structures and confidence helpers for the title report factory."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Confidence scale (0-100) per the project quality_control spec.
# ---------------------------------------------------------------------------
def confidence_band(score: int) -> str:
    if score >= 90:
        return "Strong, clear, source-backed"
    if score >= 70:
        return "Good, minor uncertainty"
    if score >= 50:
        return "Usable but needs review"
    if score >= 25:
        return "Weak or incomplete"
    return "Unreliable or speculative"


UNKNOWN = "Unknown"
NOT_FOUND = "Not Found"
NOT_APPLICABLE = "Not Applicable"
NEEDS_REVIEW = "Needs Review"


def blank_safe(value: Any, default: str = NEEDS_REVIEW) -> Any:
    """Honor the blank_cell_rule: important cells never left empty."""
    if value is None:
        return default
    s = str(value).strip()
    if s == "" or s.lower() in {"none", "nan", "nat"}:
        return default
    return value


@dataclass
class SourceFile:
    path: str
    name: str
    kind: str          # xlsx | pdf | other
    size_bytes: int
    sha256: str
    pages: Optional[int] = None
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Instrument:
    """A single recorded instrument / index entry."""
    index_no: Optional[int] = None
    source_file: str = ""
    matched_document: str = ""
    doc_type: str = ""
    instrument_no: str = ""
    book_page: str = ""
    recording_date: str = ""
    execution_date: str = ""
    effective_date: str = ""
    grantor: str = ""
    grantee: str = ""
    legal_description: str = ""
    interest: str = ""
    lease_terms: str = ""
    royalty: str = ""
    gross_acres: str = ""
    net_acres: str = ""
    notes: str = ""
    title_effect: str = ""
    source_reference: str = ""
    ocr_confidence: int = 0
    match_confidence: int = 0
    relevance_confidence: int = 0
    # internal
    classification: str = ""
    track: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Lease:
    ogl_no: str = ""
    image_no: str = ""
    instrument_no: str = ""
    book_page: str = ""
    execution_date: str = ""
    filing_date: str = ""
    grantor: str = ""        # lessor
    grantee: str = ""        # lessee
    legal_description: str = ""
    notes: str = ""
    term: str = ""
    gross_acres: str = ""
    tracts: str = ""
    exp_date: str = ""
    net_acres: str = ""
    royalty: str = ""
    source_status: str = ""
    data_status: str = ""
    source_file: str = ""
    confidence: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Well:
    name: str = ""
    api: str = ""
    operator: str = ""
    location: str = ""
    str_label: str = ""
    formation: str = ""
    status: str = ""
    spud_date: str = ""
    completion_date: str = ""
    first_production: str = ""
    last_production: str = ""
    lease_unit: str = ""
    hbp_relevance: str = ""
    source: str = ""
    notes: str = ""
    confidence: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ChainLink:
    date: str = ""
    instrument_no: str = ""
    doc_type: str = ""
    book_page: str = ""
    grantor: str = ""
    grantee: str = ""
    legal_scope: str = ""
    chain_function: str = ""
    interest_affected: str = ""
    confidence_label: str = ""
    confidence: int = 0
    limitations: str = ""
    source: str = ""
    track: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CurativeIssue:
    issue_id: str
    severity: str            # High | Medium | Low
    category: str
    description: str
    related_instruments: str = ""
    recommended_action: str = ""
    source: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReportContext:
    """Carries everything assembled across the pipeline."""
    config: dict
    source_files: list[SourceFile] = field(default_factory=list)
    instruments: list[Instrument] = field(default_factory=list)
    leases: list[Lease] = field(default_factory=list)
    wells: list[Well] = field(default_factory=list)
    chain: list[ChainLink] = field(default_factory=list)
    curative: list[CurativeIssue] = field(default_factory=list)
    ocr_cache: dict = field(default_factory=dict)
    sources_used: list[dict] = field(default_factory=list)
    sheet_scores: dict = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    executive_summary: str = ""
