"""Pydantic validation models -- the schema every final report row must satisfy.

These mirror the canonical columns of the Roger Mills cursory report and give
the validation gate (mod:`horizon.validation`) a typed contract to check against.
A row that fails the schema is never silently dropped or auto-filled: it is
reported so the orchestrator can attempt a structural repair or escalate.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .chaining import normalize_instrument

# The canonical column order for the final report (template authority).
CANONICAL_COLUMNS = [
    "entry_no",
    "instrument_date",
    "recorded_date",
    "doc_type",
    "grantor",
    "grantee",
    "instrument_number",
    "book",
    "page",
    "legal_description",
    "gross_acres",
    "conveyed_interest",
    "retained_interest",
    "net_mineral_acres",
    "status",
    "remarks",
]

REVIEW_TAG = "Needs Examiner Review"
ESCALATED_TAG = "ESCALATED"


class TitleRow(BaseModel):
    """One validated row of a cursory title report."""

    entry_no: Optional[str] = None
    instrument_date: Optional[str] = None
    recorded_date: Optional[str] = None
    doc_type: Optional[str] = None
    grantor: str = ""
    grantee: str = ""
    instrument_number: str = ""
    book: Optional[str] = None
    page: Optional[str] = None
    legal_description: str = ""
    gross_acres: Optional[str] = None
    conveyed_interest: Optional[str] = None
    retained_interest: Optional[str] = None
    net_mineral_acres: Optional[str] = None
    status: str = "ok"
    remarks: str = ""

    @field_validator("grantor", "grantee", "legal_description", mode="before")
    @classmethod
    def _coerce_str(cls, v):
        return "" if v is None else str(v).strip()

    @property
    def instrument_key(self) -> str:
        return normalize_instrument(self.instrument_number)

    @property
    def needs_review(self) -> bool:
        return REVIEW_TAG.lower() in self.remarks.lower() or self.status != "ok"


class ValidationIssue(BaseModel):
    row_index: int
    field: str
    severity: str  # "error" | "warn" | "review" | "escalated"
    message: str


class ReportModel(BaseModel):
    """A whole report: an ordered list of rows plus its provenance."""

    section: str
    source: str = ""
    rows: List[TitleRow] = Field(default_factory=list)

    def instrument_index(self) -> dict:
        idx = {}
        for r in self.rows:
            if r.instrument_key:
                idx.setdefault(r.instrument_key, []).append(r)
        return idx
