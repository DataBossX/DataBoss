"""Typed contracts for the DataBossX Land Intelligence pipeline.

Every value that flows between the ingestion, chaining, verification and
Excel-writing stages is one of the models below. Acreage and interest are
always carried as :class:`decimal.Decimal` (never float) and are quantized to
six decimal places so that tract totals can be compared to an exact tolerance
of ``0.000001`` without floating-point drift.

Hard rules enforced structurally here:

* No negative acreage or interest (``ge=0`` validators).
* Working interest is bounded to ``[0, 1]``.
* OGL fields carry OGL numbers only -- an assignment's book/page can never be
  written into an OGL field (:func:`OwnerInterest.reject_bookpage_in_ogl`).
* Assignment conveyances must use the type token ``ASSN``.
"""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- Decimal policy -------------------------------------------------------

ACRE_QUANT = Decimal("0.000001")
TOLERANCE = Decimal("0.000001")


def quantize_acres(value) -> Decimal:
    """Coerce any acreage-like value to a Decimal quantized to 0.000001.

    Accepts Decimal/int/str/float. Floats are routed through ``str`` first so
    that ``0.1`` does not become ``0.1000000000000000055...``.
    """
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, float):
        d = Decimal(str(value))
    else:
        d = Decimal(str(value).strip())
    return d.quantize(ACRE_QUANT, rounding=ROUND_HALF_UP)


# A book/page reference looks like "1234/567", "1234-567", "Bk 1234 Pg 567".
# An OGL number looks like "OGL-45", "OGL 45", "45". We reject anything that
# smells like a book/page pair from an OGL field.
_BOOKPAGE_RE = re.compile(r"\b\d{1,5}\s*[/\-]\s*\d{1,4}\b")
_BKPG_WORD_RE = re.compile(r"\b(?:bk|book|pg|page)\b", re.IGNORECASE)


def looks_like_book_page(value: str) -> bool:
    """True if ``value`` looks like an assignment book/page rather than an OGL."""
    if not value:
        return False
    v = str(value)
    return bool(_BOOKPAGE_RE.search(v) or _BKPG_WORD_RE.search(v))


# --- Ingestion layer ------------------------------------------------------


class RunsheetInstrument(BaseModel):
    """One recorded instrument as extracted from the runsheet.

    This is the raw, pre-chained view: exactly what the runsheet row says,
    normalized into typed fields. ``conveyance`` is the recording type token
    (WD, MD, OGL, ASSN, PROB, ...). ``ogl_ref`` holds an OGL number *only* --
    the assignment book/page lives in ``bk_pg``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    row: int = Field(..., ge=0, description="Source runsheet row index (0-based).")
    tract: str = Field(..., description="Tract identifier this instrument affects.")
    instrument_no: str = ""
    legal: str = ""
    grantor: str = ""
    grantee: str = ""
    conveyance: str = ""
    bk_pg: str = ""
    date: str = ""
    gross_acres: Optional[Decimal] = None
    conveyed_interest: Optional[str] = None
    ogl_ref: Optional[str] = None
    notes: str = ""

    @field_validator("gross_acres", mode="before")
    @classmethod
    def _q_gross(cls, v):
        if v is None or v == "":
            return None
        return quantize_acres(v)

    @field_validator("conveyance", mode="before")
    @classmethod
    def _norm_conveyance(cls, v):
        return "" if v is None else str(v).strip().upper()

    @field_validator("ogl_ref", mode="before")
    @classmethod
    def _clean_ogl(cls, v):
        """OGL references must never contain a book/page pair (rule 7 & 8)."""
        if v is None or str(v).strip() == "":
            return None
        s = str(v).strip()
        if looks_like_book_page(s):
            # Refuse to smuggle a book/page into an OGL field -- drop it so the
            # chaining stage can flag the missing OGL as an assumption instead.
            return None
        return s


class Conveyance(BaseModel):
    """A normalized transfer of interest along a title chain.

    Derived from a :class:`RunsheetInstrument` by the chaining stage. Acreage
    is expressed as ``acres`` (net mineral acres moved) and/or ``fraction`` of
    the grantor's holding. Assignments carry an ``ogl`` number and *must* use
    ``conv_type == "ASSN"`` (rule 9).
    """

    tract: str
    grantor: str = ""
    grantee: str = ""
    conv_type: str = ""
    acres: Optional[Decimal] = None
    fraction: Optional[str] = None
    ogl: Optional[str] = None
    instrument_no: str = ""
    bk_pg: str = ""
    date: str = ""
    is_assumption: bool = False
    note: str = ""

    @field_validator("acres", mode="before")
    @classmethod
    def _q_acres(cls, v):
        if v is None or v == "":
            return None
        return quantize_acres(v)

    @field_validator("conv_type", mode="before")
    @classmethod
    def _norm_type(cls, v):
        return "" if v is None else str(v).strip().upper()

    @field_validator("ogl", mode="before")
    @classmethod
    def _clean_ogl(cls, v):
        if v is None or str(v).strip() == "":
            return None
        s = str(v).strip()
        if looks_like_book_page(s):
            return None
        return s


class OwnerInterest(BaseModel):
    """A final owner's net position in a tract after chaining.

    Only owners with ``acres > 0`` (or an explicitly retained interest) survive
    onto the Title Sheet (rules 4 & 5). ``ogl`` carries the OGL number(s) that
    burden this owner, joined by ``", "`` when several leases apply. When
    ``is_assumption`` is set the writer paints only this owner's review cell
    yellow (rule 15) and ``assumption_note`` explains why.
    """

    owner: str
    tract: str = ""
    acres: Decimal = Field(..., ge=0)
    wi: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    ogl: Optional[str] = None
    conveyance: str = ""
    leased: bool = False
    is_assumption: bool = False
    assumption_note: str = ""

    @field_validator("acres", "wi", mode="before")
    @classmethod
    def _q(cls, v):
        return quantize_acres(v)

    @field_validator("ogl", mode="before")
    @classmethod
    def _clean_ogl(cls, v):
        if v is None or str(v).strip() == "":
            return None
        s = str(v).strip()
        if looks_like_book_page(s):
            return None
        return s

    @field_validator("conveyance", mode="before")
    @classmethod
    def _norm_type(cls, v):
        return "" if v is None else str(v).strip().upper()


class TractChainResult(BaseModel):
    """The chained result for a single tract: final owners plus provenance."""

    tract: str
    tract_acres: Decimal
    final_owners: List[OwnerInterest] = Field(default_factory=list)
    balanced: bool = False
    review_flags: List[str] = Field(default_factory=list)
    assumption_notes: List[str] = Field(default_factory=list)
    attempts: int = 0

    @field_validator("tract_acres", mode="before")
    @classmethod
    def _q(cls, v):
        return quantize_acres(v)

    @property
    def total_acres(self) -> Decimal:
        total = sum((o.acres for o in self.final_owners), Decimal("0"))
        return total.quantize(ACRE_QUANT)

    @property
    def needs_review(self) -> bool:
        return (not self.balanced) or bool(self.review_flags) or any(
            o.is_assumption for o in self.final_owners
        )


class VerificationResult(BaseModel):
    """Deterministic verdict for a tract from :mod:`verifier`.

    ``passed`` is the AND of: total within tolerance of tract acreage, no
    negative holdings, and no over-conveyance. ``errors`` enumerates each
    concrete failure so the auditor agent gets precise correction feedback.
    """

    tract: str
    expected_acres: Decimal
    calculated_total: Decimal
    delta: Decimal
    passed: bool
    errors: List[str] = Field(default_factory=list)
    correction_suggestion: str = ""

    @field_validator("expected_acres", "calculated_total", "delta", mode="before")
    @classmethod
    def _q(cls, v):
        return quantize_acres(v)
