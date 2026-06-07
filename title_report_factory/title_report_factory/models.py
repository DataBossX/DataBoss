"""Pydantic data models shared across the pipeline.

Every fact-bearing model carries a confidence score and an optional issue note,
so uncertainty travels with the data instead of being lost.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class SourceFile(BaseModel):
    """A raw file discovered during inventory."""

    path: str
    name: str
    ext: str
    size_bytes: int
    sha256: str
    kind: str = "unknown"  # excel | pdf | image | text | other
    pages: Optional[int] = None
    note: str = ""


class LegalDescription(BaseModel):
    raw: str = ""
    section: Optional[str] = None
    township: Optional[str] = None
    range: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None
    quarter_calls: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class Party(BaseModel):
    name: str
    role: str = ""  # grantor | grantee | lessor | lessee | assignor | assignee
    confidence: float = 0.0


class Document(BaseModel):
    """A classified instrument with extracted facts and provenance."""

    doc_id: str
    source_file: str
    matched_document: str = ""
    document_type: str = "Unknown"
    instrument_no: str = ""
    book_page: str = ""
    recording_date: str = ""
    execution_date: str = ""
    effective_date: str = ""
    grantors: List[str] = Field(default_factory=list)
    grantees: List[str] = Field(default_factory=list)
    legal: LegalDescription = Field(default_factory=LegalDescription)
    interest: str = ""
    lease_terms: str = ""
    royalty: str = ""
    gross_acres: str = ""
    net_acres: str = ""
    notes: str = ""
    title_effect: str = ""
    source_reference: str = ""
    text: str = ""
    text_hash: str = ""
    ocr_used: bool = False
    ocr_confidence: Optional[float] = None
    classification_confidence: Optional[float] = None
    match_confidence: Optional[float] = None
    relevance_confidence: Optional[float] = None
    issues: List[str] = Field(default_factory=list)


class ChainLink(BaseModel):
    sequence: int
    document_type: str
    grantor: str
    grantee: str
    execution_date: str
    effective_date: str
    recording_date: str
    instrument_no: str
    book_page: str
    legal: str
    interest_affected: str
    title_notes: str
    source: str
    confidence: Optional[float] = None


class CurativeIssue(BaseModel):
    issue_id: str
    category: str  # gap | ambiguity | missing_doc | ocr | conflict | assumption
    severity: str  # high | medium | low
    description: str
    related_documents: List[str] = Field(default_factory=list)
    recommendation: str = ""
    confidence: Optional[float] = None


class ReviewPass(BaseModel):
    """One independent analysis pass in the multi-AI tournament."""

    name: str
    role: str  # facts | title_effect | red_team
    document_id: str
    findings: dict = Field(default_factory=dict)
    confidence: float = 0.0
    engine: str = "heuristic"


class ReviewConsensus(BaseModel):
    document_id: str
    agreed: bool
    consensus: dict = Field(default_factory=dict)
    disagreements: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    passes: List[ReviewPass] = Field(default_factory=list)


class PipelineResult(BaseModel):
    workbook_path: str = ""
    overall_confidence_score: int = 0
    documents_reviewed_count: int = 0
    documents_downloaded_count: int = 0
    documents_ocr_count: int = 0
    index_rows_created_count: int = 0
    major_title_findings: List[str] = Field(default_factory=list)
    missing_documents: List[str] = Field(default_factory=list)
    curative_issues: List[str] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    errors_or_limitations: List[str] = Field(default_factory=list)
