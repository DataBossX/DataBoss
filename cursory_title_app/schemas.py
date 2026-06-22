"""Pydantic schemas for validated extraction. Never let the LLM write
free-form data straight into the workbook — it goes through these gates first.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Flag vocabulary the app is allowed to emit into Review / NEED-ACTION columns.
REVIEW_FLAGS = {
    "VERIFY: OCR uncertain",
    "VERIFY: grantor/grantee spelling",
    "VERIFY: net acres calculation",
}
NEED_FLAGS = {
    "NEED: pull clearer image",
    "NEED: verify legal description",
    "NEED: confirm current ownership",
    "NEED: review lease terms",
    "NEED: determine if released/HBP",
}


class IndexRow(BaseModel):
    """One row read from the handwritten numerical index PDF.

    Everything here is LOW CONFIDENCE by default (cursive handwriting).
    """
    page_number: int
    grantor: Optional[str] = None
    grantee: Optional[str] = None
    instrument_kind: Optional[str] = None     # as written in the index ("O/L", "WD"...)
    book: Optional[str] = None
    page: Optional[str] = None
    date_filed: Optional[str] = None          # raw string; not coerced
    legal_note: Optional[str] = None          # subdivision marks / lots
    remarks: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    needs_review: bool = True
    raw_cells: dict = Field(default_factory=dict)


class DocExtraction(BaseModel):
    """Fields extracted from an actual recorded instrument (image/PDF)."""
    instrument_number: Optional[str] = None
    book_page: Optional[str] = None
    doc_type: Optional[str] = None            # normalized
    doc_type_original: Optional[str] = None   # exact source wording
    effective_date: Optional[str] = None      # instrument/execution date
    recorded_date: Optional[str] = None
    grantor: Optional[str] = None
    grantee: Optional[str] = None
    legal_description: Optional[str] = None
    section: Optional[str] = None
    township: Optional[str] = None
    range_: Optional[str] = Field(None, alias="range")
    tracts: Optional[str] = None
    classification: Optional[
        Literal["Mineral", "Leasehold", "Surface", "Royalty", "Other"]
    ] = None
    conveyance_type: Optional[str] = None
    conveyance_amount_dec: Optional[float] = None
    gross_acres: Optional[float] = None
    net_acres: Optional[float] = None         # only if explicitly determinable
    royalty: Optional[str] = None             # OGL only
    primary_term: Optional[str] = None        # OGL only
    recording_references: Optional[str] = None
    document_link: Optional[str] = None
    notes: Optional[str] = None
    review_flags: list[str] = Field(default_factory=list)
    need_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    needs_review: bool = True

    model_config = {"populate_by_name": True}

    @field_validator("review_flags")
    @classmethod
    def _valid_review(cls, v):
        bad = [f for f in v if f not in REVIEW_FLAGS]
        if bad:
            raise ValueError(f"Unknown review flag(s): {bad}")
        return v

    @field_validator("need_flags")
    @classmethod
    def _valid_need(cls, v):
        bad = [f for f in v if f not in NEED_FLAGS]
        if bad:
            raise ValueError(f"Unknown need flag(s): {bad}")
        return v


class RunsheetWrite(BaseModel):
    """A vetted set of cell values destined for ONE Runsheet row.

    Keys are logical field names (see runsheet.columns.FIELD_TO_COLUMN).
    The Excel writer maps these to columns and refuses formula columns.
    """
    row: int = Field(..., ge=2)
    values: dict[str, object] = Field(default_factory=dict)
    document_link_url: Optional[str] = None   # becomes =HYPERLINK in column K
    document_link_label: Optional[str] = None
