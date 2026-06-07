"""Dataclasses shared across the title_report_factory pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

UNKNOWN = "Unknown"
NEEDS_REVIEW = "Needs Review"


@dataclass
class TractKey:
    """Identifies the subject tract and target owner for a run."""

    section: str
    township: str
    range: str
    county: str
    state: str
    target_owner: str

    @property
    def legal_base(self) -> str:
        return (
            f"Section {self.section}, Township {self.township}, "
            f"Range {self.range}, I.M., {self.county} County, {self.state}"
        )

    @property
    def short(self) -> str:
        return f"{self.section}-{self.township}-{self.range}"

    def search_terms(self) -> List[str]:
        s, t, r = self.section, self.township, self.range
        c, st, o = self.county, self.state, self.target_owner
        return [
            f"{o} Section {s} {t} {r} {c} County {st}",
            f"{o} {s}-{t}-{r} {c} County",
            f"{o} S{s} T{t} R{r}",
            f"Section {s} Township {t} Range {r} {c} County {st}",
            f"Sec {s} T{t} R{r} {c} County",
            f"{t} {r} {s} {c} County",
            f"{s} {t} {r} {c}",
        ]


@dataclass
class SourceFile:
    """One discovered input file in the source inventory."""

    source_id: str
    source_type: str          # Excel / PDF / Image / Text / Other
    file_name: str
    where_found: str
    pages: Any = UNKNOWN
    ocr_status: str = "N/A"
    extraction_status: str = "Pending"
    important_text: str = ""
    limitations: str = ""
    confidence: int = 0


@dataclass
class Document:
    """A title instrument extracted from a source (deed, lease, assignment...)."""

    doc_type: str = UNKNOWN
    grantor: str = UNKNOWN          # grantor / assignor / lessor
    grantee: str = UNKNOWN          # grantee / assignee / lessee
    execution_date: str = UNKNOWN
    effective_date: str = UNKNOWN
    recording_date: str = UNKNOWN
    instrument_no: str = UNKNOWN
    book_page: str = UNKNOWN
    legal_description: str = UNKNOWN
    legal_normalized: str = UNKNOWN
    interest: str = UNKNOWN          # interest / lands affected
    title_effect: str = UNKNOWN
    notes: str = ""
    source_ref: str = UNKNOWN
    ocr_confidence: int = 0
    match_confidence: int = 0
    relevance_confidence: int = 0
    raw_text: str = ""

    @property
    def confidence(self) -> int:
        scores = [self.ocr_confidence, self.match_confidence, self.relevance_confidence]
        scores = [s for s in scores if s]
        return int(round(sum(scores) / len(scores))) if scores else 0


@dataclass
class CurativeIssue:
    issue_no: int
    severity: str               # Critical / High / Medium / Low
    issue_type: str
    affected_instrument: str
    affected_lands: str
    problem: str
    needed_action: str
    suggested_curative: str
    source: str
    confidence: int


@dataclass
class ReportData:
    """Everything the workbook builder needs, assembled by analysis.py."""

    tract: TractKey
    date_prepared: str
    sources: List[SourceFile] = field(default_factory=list)
    documents: List[Document] = field(default_factory=list)
    leases: List[Document] = field(default_factory=list)
    wells: List[Dict[str, Any]] = field(default_factory=list)
    curative: List[CurativeIssue] = field(default_factory=list)
    title_narrative: List[Dict[str, str]] = field(default_factory=list)
    overview: Dict[str, str] = field(default_factory=dict)
    confidence: Dict[str, Any] = field(default_factory=dict)
    qc_results: List[Dict[str, str]] = field(default_factory=list)
    search_log: List[Dict[str, str]] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    @property
    def has_sources(self) -> bool:
        return len(self.sources) > 0
