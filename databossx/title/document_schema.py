"""Strict title-document schema for DataBossX OCR extraction.

The OCR layer must return EXACTLY this shape. Unknown fields are null, lists
default empty, confidence is a float in [0,1], and `visible_evidence` is
required to support any non-null fact. No guessing, no auto-correction.
"""
from __future__ import annotations

from copy import deepcopy

# Canonical empty result. OCR providers must return this shape only.
OCR_SCHEMA: dict = {
    "instrument_type": None,
    "document_date": None,
    "recorded_date": None,
    "book": None,
    "page": None,
    "instrument_number": None,
    "grantors": [],
    "grantees": [],
    "legal_descriptions": [],
    "interest_conveyed": None,
    "reservations": None,
    "term_or_royalty": None,
    "notes": None,
    "confidence": 0.0,
    "uncertain_fields": [],
    "visible_evidence": [],
}

SCALAR_FIELDS = {
    "instrument_type", "document_date", "recorded_date", "book", "page",
    "instrument_number", "interest_conveyed", "reservations", "term_or_royalty", "notes",
}
LIST_FIELDS = {"grantors", "grantees", "legal_descriptions", "uncertain_fields", "visible_evidence"}


def blank_result() -> dict:
    return deepcopy(OCR_SCHEMA)
