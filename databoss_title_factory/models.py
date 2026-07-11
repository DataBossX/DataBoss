"""Strict evidence and instrument schemas for DataBoss Title Factory."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    coordinate_space: Literal["pixels", "pdf_points"] = "pixels"


class OCRBlock(BaseModel):
    text: str
    normalized_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: Optional[BoundingBox] = None
    block_number: Optional[int] = None
    paragraph_number: Optional[int] = None
    line_number: Optional[int] = None
    word_number: Optional[int] = None


class FieldProvenance(BaseModel):
    project_id: str
    source_file: str
    source_file_hash: str
    source_page: Optional[int] = None
    source_image_number: Optional[str] = None
    source_bounding_box: Optional[BoundingBox] = None
    derived_image_path: Optional[str] = None
    preprocessing_recipe: Optional[str] = None
    extraction_method: str
    extraction_model: str
    raw_text_snippet: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_support_score: float = Field(ge=0.0, le=1.0)
    review_status: Literal[
        "DIRECT_SOURCE_SUPPORT",
        "PAGE_LEVEL_SUPPORT",
        "UNREADABLE",
        "UNSUPPORTED",
        "HUMAN_REVIEW",
    ]


class InstrumentRecord(BaseModel):
    """Evidence-first record; absent values stay ``None``."""

    model_config = ConfigDict(extra="allow")

    project_id: str
    record_id: str
    source_file: str
    source_file_hash: str
    source_page: Optional[int] = None
    source_image_number: Optional[str] = None
    source_bounding_box: Optional[BoundingBox] = None
    extraction_method: str
    extraction_model: str
    extraction_timestamp: dt.datetime
    grantor_verbatim: Optional[str] = None
    grantor_normalized: Optional[str] = None
    grantee_verbatim: Optional[str] = None
    grantee_normalized: Optional[str] = None
    instrument_type_verbatim: Optional[str] = None
    instrument_type_normalized: Optional[str] = None
    instrument_number: Optional[str] = None
    execution_date: Optional[str] = None
    acknowledgment_date: Optional[str] = None
    recording_date: Optional[str] = None
    book: Optional[str] = None
    page: Optional[str] = None
    reception_number: Optional[str] = None
    legal_description_verbatim: Optional[str] = None
    legal_description_normalized: Optional[str] = None
    section: Optional[str] = None
    township: Optional[str] = None
    range: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None
    tract_candidates: list[str] = Field(default_factory=list)
    interest_language_verbatim: Optional[str] = None
    interest_fraction: Optional[str] = None
    gross_acres: Optional[str] = None
    net_acres: Optional[str] = None
    royalty: Optional[str] = None
    term: Optional[str] = None
    primary_term: Optional[str] = None
    extension_term: Optional[str] = None
    depth_language: Optional[str] = None
    formations: list[str] = Field(default_factory=list)
    reservations: Optional[str] = None
    exceptions: Optional[str] = None
    assignments: list[str] = Field(default_factory=list)
    related_instruments: list[str] = Field(default_factory=list)
    marginal_notations: Optional[str] = None
    raw_text_snippet: str = ""
    unreadable_fields: list[str] = Field(default_factory=list)
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    source_support_score: float = Field(ge=0.0, le=1.0)
    review_status: str
    reviewer_notes: Optional[str] = None
    assumption_flag: bool = False
    assumption_text: Optional[str] = None
    conflict_flag: bool = False
    conflict_ids: list[str] = Field(default_factory=list)
    field_provenance: dict[str, FieldProvenance] = Field(default_factory=dict)
    value_states: dict[str, Literal[
        "ABSENT", "UNREADABLE", "NOT_APPLICABLE", "INFERRED",
        "ASSUMED", "EXTERNALLY_RESEARCHED", "SOURCE_VERIFIED",
    ]] = Field(default_factory=dict)


class CandidateEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    candidate_id: str
    pass_name: str
    provider: str = "local"
    model: str
    prompt_version: str
    source_hash: str
    deterministic: bool = True
    raw_response_path: Optional[str] = None
    parsed_response_path: Optional[str] = None
    validation_errors: list[str] = Field(default_factory=list)
    token_metadata: dict[str, Any] = Field(default_factory=dict)
    cost_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: dt.datetime
    status: str
