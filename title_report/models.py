"""Data model for the cursory title report.

Plain dataclasses, no I/O. Every entity that asserts a material fact carries a
``citation`` referencing a ``Source.source_id`` (and, where relevant, a page or
row). Fields whose value is not established by an examined instrument are left
as the sentinel :data:`UNKNOWN` rather than guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from fractions import Fraction
from typing import List, Optional, Union

# Sentinel for any value not established by an examined source. The QA layer
# treats this as an explicit "not determined", never an error or a zero.
UNKNOWN = "UNKNOWN"

# A fraction-or-unknown value (e.g. a royalty or mineral interest).
FracOrUnknown = Union[Fraction, str]


@dataclass
class ProjectConfig:
    """Top-of-report setup: the tract, dates, and stated assumptions."""

    section: str
    township: str
    range_: str
    county: str
    state: str = "OK"
    # Acreage assumptions -- stated, not measured. gross_acres is the nominal
    # section/tract size; net_mineral_acres is the assumption used for NMA math.
    gross_acres: FracOrUnknown = UNKNOWN
    net_mineral_acres: FracOrUnknown = UNKNOWN
    acreage_basis: str = UNKNOWN
    report_date: str = UNKNOWN          # e.g. "2026-06-23"
    source_cutoff_date: str = UNKNOWN   # records examined through this date
    prepared_for: str = UNKNOWN
    preparer: str = UNKNOWN
    report_type: str = "Cursory Title Report"
    # Free-text stated assumptions / scope limitations.
    assumptions: List[str] = field(default_factory=list)
    # True when the report is populated with illustrative data rather than
    # examined records. Surfaced prominently on the cover sheet.
    is_placeholder: bool = False
    # Data provenance: "EXAMINED" (real record review), "SPECIMEN" (fully
    # populated illustrative model), or "PLACEHOLDER" (skeletal/UNKNOWN-heavy).
    data_status: str = "EXAMINED"

    @property
    def tract_label(self) -> str:
        return f"Sec {self.section}-{self.township}-{self.range_}, {self.county} County, {self.state}"


@dataclass
class Source:
    """A source consulted during the examination (county index, OCC, BLM, ...)."""

    source_id: str            # stable handle used by citations, e.g. "SRC-001"
    category: str             # County Index | OCC | BLM/GLO | OTC | Court | Other
    name: str
    location: str = UNKNOWN   # URL, repository, or physical location
    accessed_date: str = UNKNOWN
    doc_count: FracOrUnknown = UNKNOWN
    credential_required: bool = False
    page_ref: str = UNKNOWN
    notes: str = ""


@dataclass
class Instrument:
    """A runsheet row: one recorded (or referenced) instrument."""

    instrument_no: str
    instrument_type: str            # Deed | OGL | Assignment | Mortgage | Probate ...
    book: str = UNKNOWN
    page: str = UNKNOWN
    instrument_date: str = UNKNOWN
    recording_date: str = UNKNOWN
    grantors: List[str] = field(default_factory=list)
    grantees: List[str] = field(default_factory=list)
    legal_raw: str = UNKNOWN        # legal description as written
    legal_normalized: str = UNKNOWN # normalized; raw value preserved above
    consideration: str = UNKNOWN
    classification: str = UNKNOWN   # Mineral | Surface | Leasehold | Burden | Lien ...
    citation: str = UNKNOWN         # source_id (+ page) supporting this row
    image_url: str = UNKNOWN        # direct link to the recorded image, if any
    notes: str = ""


@dataclass
class Abstraction:
    """Structured extraction for a single material instrument."""

    instrument_no: str
    grant_clause: str = UNKNOWN
    reservations: str = UNKNOWN
    royalty_wi_language: str = UNKNOWN
    exceptions: str = UNKNOWN
    pugh_shutin: str = UNKNOWN
    depth_limits: str = UNKNOWN
    pooling_refs: str = UNKNOWN
    liens: str = UNKNOWN
    probate: str = UNKNOWN
    tags: List[str] = field(default_factory=list)
    confidence: FracOrUnknown = UNKNOWN   # 0..1 when machine-extracted
    needs_review: bool = False
    citation: str = UNKNOWN


@dataclass
class ChainLink:
    """One link in a chronological chain of title."""

    chain_type: str          # "mineral_surface" | "leasehold_wi_burdens"
    seq: int
    instrument_no: str
    date: str = UNKNOWN
    conveyance: str = UNKNOWN
    from_party: str = UNKNOWN
    to_party: str = UNKNOWN
    interest: str = UNKNOWN
    gap_note: str = ""       # noted break/overlap in the chain, if any
    citation: str = UNKNOWN


@dataclass
class Well:
    """A well bearing on held-by-production analysis."""

    api_number: str
    well_name: str = UNKNOWN
    operator: str = UNKNOWN
    formation: str = UNKNOWN
    spacing_order: str = UNKNOWN
    pooling_order: str = UNKNOWN
    first_production: str = UNKNOWN
    status: str = UNKNOWN            # Producing | PA | Inactive | UNKNOWN
    # "Supported" | "Unknown" | "Not supported" -- never asserted without evidence.
    hbp_support: str = UNKNOWN
    citation: str = UNKNOWN


@dataclass
class Curative:
    """An encumbrance or curative item requiring tracking."""

    issue_id: str
    issue_type: str          # Mortgage | Lien | ROW | Probate | Trust | Authority ...
    instrument_no: str = UNKNOWN
    description: str = UNKNOWN
    materiality: str = UNKNOWN       # High | Medium | Low
    priority: str = UNKNOWN
    status: str = "Open"             # Open | Cleared
    recommended_action: str = UNKNOWN
    citation: str = UNKNOWN


@dataclass
class OwnershipEntry:
    """A row in the NRI/WI matrix.

    Interests are exact rationals (``Fraction``) or :data:`UNKNOWN`. Derived
    values (NRI, NMA) are only computed when the governing language is present;
    otherwise they remain UNKNOWN. The same arithmetic is mirrored as a live
    Excel formula in the workbook so the math is auditable in the spreadsheet.
    """

    owner: str
    role: str                        # "royalty" | "working_interest" | "overriding_royalty"
    mineral_interest: FracOrUnknown = UNKNOWN   # fraction of minerals owned
    lease_royalty: FracOrUnknown = UNKNOWN      # lessor royalty, e.g. 3/16
    working_interest: FracOrUnknown = UNKNOWN   # gross WI before burdens
    burdens: FracOrUnknown = UNKNOWN            # total burdens against WI
    override_royalty: FracOrUnknown = UNKNOWN   # ORRI carved out of leasehold
    basis_language: str = UNKNOWN    # exact governing text; required to compute
    citation: str = UNKNOWN


@dataclass
class TitleReport:
    """The complete examination: config plus every schedule."""

    config: ProjectConfig
    sources: List[Source] = field(default_factory=list)
    instruments: List[Instrument] = field(default_factory=list)
    abstractions: List[Abstraction] = field(default_factory=list)
    chain_links: List[ChainLink] = field(default_factory=list)
    wells: List[Well] = field(default_factory=list)
    curative: List[Curative] = field(default_factory=list)
    ownership: List[OwnershipEntry] = field(default_factory=list)

    # ---- convenience accessors -------------------------------------------

    def source_ids(self) -> set:
        return {s.source_id for s in self.sources}

    def mineral_chain(self) -> List[ChainLink]:
        return sorted(
            [c for c in self.chain_links if c.chain_type == "mineral_surface"],
            key=lambda c: c.seq,
        )

    def leasehold_chain(self) -> List[ChainLink]:
        return sorted(
            [c for c in self.chain_links if c.chain_type == "leasehold_wi_burdens"],
            key=lambda c: c.seq,
        )


def field_names(cls) -> List[str]:
    """Return dataclass field names (used by writers to stay in sync)."""
    return [f.name for f in fields(cls)]
