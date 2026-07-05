"""Typed data model for DataBossX Title Report Engine v2.

Everything that flows through the engine is one of these models. The two rules
that matter for a title report live here in the type system:

* All acreage / interest quantities are :class:`~decimal.Decimal`, never float.
  Float rounding silently invents fractions of an acre; a title report cannot
  tolerate that. The custom validators coerce strings/ints into ``Decimal`` and
  reject anything that cannot be represented exactly.
* Evidence is never anonymous. Every :class:`EvidenceRow` carries its
  ``source_sheet`` and ``source_row`` so any figure in the final report can be
  traced back to the exact cell it came from. Nothing is fabricated: unknown
  fields stay ``None`` and are surfaced as review flags, not guessed.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def to_decimal(value) -> Optional[Decimal]:
    """Coerce a cell value to :class:`Decimal`, or ``None`` if not numeric.

    Accepts ``Decimal``, ``int``, and strings that may carry ``%``, ``$``,
    commas, or surrounding whitespace. A percentage string (``"50%"``) is
    converted to its fractional value (``Decimal("0.5")``). Anything that is not
    an exact number returns ``None`` -- the engine treats that as "unknown", it
    never substitutes zero.
    """
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):  # guard: bool is an int subclass
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        # Route floats through str() so 0.1 becomes Decimal("0.1"), not the
        # binary-approx tail. Spreadsheet cells frequently arrive as floats.
        return Decimal(str(value))
    text = str(value).strip()
    if not text:
        return None
    is_pct = text.endswith("%")
    cleaned = text.replace("%", "").replace("$", "").replace(",", "").strip()
    try:
        dec = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    return dec / Decimal(100) if is_pct else dec


class ConveyanceType(str, Enum):
    """Normalized instrument / conveyance types the chain engine understands."""

    DEED = "DEED"
    MINERAL_DEED = "MD"
    WARRANTY_DEED = "WD"
    QUITCLAIM = "QCD"
    ASSIGNMENT = "ASSN"          # leasehold transfer -- rule #9
    LEASE = "OGL"               # oil & gas lease
    PROBATE = "PROBATE"
    AFFIDAVIT = "AFF"
    RELEASE = "RELEASE"
    ROOT = "ROOT"               # sovereignty / patent -- start of a chain
    OTHER = "OTHER"


# Words that map a raw instrument-type string onto a ConveyanceType. Ordered by
# specificity: assignment must beat "deed", lease must beat generic.
_TYPE_KEYWORDS = [
    (("assignment", "assign", "assn", "aoogl", "a.o.o.g.l"), ConveyanceType.ASSIGNMENT),
    (("oil and gas lease", "oil & gas lease", "ogl", "o.g.l", "lease"), ConveyanceType.LEASE),
    (("mineral deed", "mineral"), ConveyanceType.MINERAL_DEED),
    (("warranty deed", "warranty", "gwd", "swd"), ConveyanceType.WARRANTY_DEED),
    (("quit claim", "quitclaim", "quit-claim", "qcd"), ConveyanceType.QUITCLAIM),
    (("probate", "decree", "estate", "final decree", "letters"), ConveyanceType.PROBATE),
    (("affidavit", "affid", "aff of", "heirship"), ConveyanceType.AFFIDAVIT),
    (("release", "reconveyance"), ConveyanceType.RELEASE),
    (("patent", "sovereignty", "root of title"), ConveyanceType.ROOT),
    (("deed", "conveyance", "grant"), ConveyanceType.DEED),
]


def classify_type(raw: Optional[str]) -> ConveyanceType:
    """Map a free-text instrument-type string to a :class:`ConveyanceType`."""
    if not raw:
        return ConveyanceType.OTHER
    text = str(raw).strip().lower()
    for keywords, ctype in _TYPE_KEYWORDS:
        if any(k in text for k in keywords):
            return ctype
    return ConveyanceType.OTHER


class EvidenceRow(BaseModel):
    """One parsed instrument from a runsheet / tract sheet / OGL sheet.

    This is the atomic unit of evidence. It is deliberately permissive about
    what is present (a real runsheet is messy) but strict about types: acreage
    and interest are Decimal or nothing.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    instrument_date: Optional[str] = None
    recording_date: Optional[str] = None
    book_page: Optional[str] = None
    instrument_type: Optional[str] = None
    conveyance_type: ConveyanceType = ConveyanceType.OTHER
    grantor: str = ""
    grantee: str = ""
    legal_description: str = ""
    tract: Optional[str] = None
    notes: str = ""
    conveyed_interest: Optional[Decimal] = None
    reserved_interest: Optional[Decimal] = None
    gross_acres: Optional[Decimal] = None
    lease_number: Optional[str] = None          # OGL number -- rule #7
    source_sheet: str = ""
    source_row: Optional[int] = None

    @field_validator("grantor", "grantee", "legal_description", "notes", mode="before")
    @classmethod
    def _clean_str(cls, v):
        return "" if v is None else " ".join(str(v).split())

    @field_validator("conveyed_interest", "reserved_interest", "gross_acres", mode="before")
    @classmethod
    def _to_dec(cls, v):
        return to_decimal(v)

    @property
    def book(self) -> Optional[str]:
        if not self.book_page:
            return None
        return str(self.book_page).replace(":", "/").split("/")[0].strip() or None

    @property
    def page(self) -> Optional[str]:
        if not self.book_page or "/" not in str(self.book_page).replace(":", "/"):
            return None
        return str(self.book_page).replace(":", "/").split("/", 1)[1].strip() or None


class OwnerInterest(BaseModel):
    """A final calculated owner within a tract after chaining."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    owner: str
    mineral_interest: Decimal = Field(default=Decimal(0))   # fractional 0..1
    net_mineral_acres: Optional[Decimal] = None
    lease_number: Optional[str] = None                       # OGL beside owner -- rule #10
    lease_status: str = "Unleased"                           # Leased / Unleased / HBP
    source_sheet: str = ""
    source_row: Optional[int] = None
    remarks: str = ""

    @field_validator("mineral_interest", "net_mineral_acres", mode="before")
    @classmethod
    def _to_dec(cls, v):
        return to_decimal(v)


class ReviewFlag(BaseModel):
    """A single unresolved item a human examiner must clear."""

    tract: Optional[str] = None
    category: str                 # e.g. "unbalanced_tract", "unmatched_ogl"
    severity: str = "yellow"      # yellow = needs review; red = blocking
    message: str = ""
    source_sheet: str = ""
    source_row: Optional[int] = None


class AuditEntry(BaseModel):
    """One line of the Audit Log -- every material action is recorded here."""

    timestamp: str
    tract: Optional[str] = None
    source_sheet: str = ""
    source_row: Optional[int] = None
    action: str = ""
    before: str = ""
    after: str = ""
    evidence: str = ""
    flag: str = ""


class Tract(BaseModel):
    """A tract: its target acreage plus the evidence and final owners for it."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    gross_acres: Optional[Decimal] = None
    legal_description: str = ""
    evidence: List[EvidenceRow] = Field(default_factory=list)
    owners: List[OwnerInterest] = Field(default_factory=list)
    evidence_score: int = 0
    flags: List[ReviewFlag] = Field(default_factory=list)

    @field_validator("gross_acres", mode="before")
    @classmethod
    def _to_dec(cls, v):
        return to_decimal(v)

    @property
    def owned_acres(self) -> Decimal:
        return sum((o.net_mineral_acres or Decimal(0) for o in self.owners), Decimal(0))

    @property
    def owned_interest(self) -> Decimal:
        return sum((o.mineral_interest or Decimal(0) for o in self.owners), Decimal(0))
