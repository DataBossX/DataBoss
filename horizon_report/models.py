"""Data models for the ownership report system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path


@dataclass
class SourceDocument:
    """Represents a source document file."""
    
    path: Path
    file_type: str
    size: int
    modified_time: datetime
    relevance: str = ""
    warnings: List[str] = field(default_factory=list)
    parsed_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": str(self.path),
            "file_type": self.file_type,
            "size": self.size,
            "modified_time": self.modified_time.isoformat(),
            "relevance": self.relevance,
            "warnings": self.warnings,
            "has_parsed_data": self.parsed_data is not None
        }


@dataclass
class OwnershipEntry:
    """Represents a single ownership record."""
    
    owner_name: str = ""
    interest_type: str = ""
    interest_decimal: Optional[float] = None
    interest_fraction: str = ""
    net_acres: Optional[float] = None
    gross_acres: Optional[float] = None
    royalty: Optional[float] = None
    legal_description: str = ""
    source_instrument: str = ""
    recording_info: str = ""
    book: str = ""
    page: str = ""
    recording_date: str = ""
    grantor: str = ""
    grantee: str = ""
    notes: str = ""
    status: str = "Pending Review"
    confidence: str = "Low"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "owner_name": self.owner_name,
            "interest_type": self.interest_type,
            "interest_decimal": self.interest_decimal,
            "interest_fraction": self.interest_fraction,
            "net_acres": self.net_acres,
            "gross_acres": self.gross_acres,
            "royalty": self.royalty,
            "legal_description": self.legal_description,
            "source_instrument": self.source_instrument,
            "recording_info": self.recording_info,
            "book": self.book,
            "page": self.page,
            "recording_date": self.recording_date,
            "grantor": self.grantor,
            "grantee": self.grantee,
            "notes": self.notes,
            "status": self.status,
            "confidence": self.confidence
        }


@dataclass
class ChainEvent:
    """Represents an event in the chain of title."""
    
    sequence: int
    date: str
    instrument_type: str
    instrument_number: str
    grantor: str
    grantee: str
    conveyed_interest: str = ""
    retained_interest: str = ""
    recording_info: str = ""
    notes: str = ""
    verified: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sequence": self.sequence,
            "date": self.date,
            "instrument_type": self.instrument_type,
            "instrument_number": self.instrument_number,
            "grantor": self.grantor,
            "grantee": self.grantee,
            "conveyed_interest": self.conveyed_interest,
            "retained_interest": self.retained_interest,
            "recording_info": self.recording_info,
            "notes": self.notes,
            "verified": self.verified
        }


@dataclass
class ReportMetadata:
    """Metadata for the generated report."""
    
    report_date: str
    generated_at: datetime
    section: str = ""
    township: str = ""
    range: str = ""
    county: str = ""
    state: str = ""
    report_type: str = "Ownership Report"
    input_folder: str = ""
    template_used: str = ""
    sources_count: int = 0
    ownership_entries_count: int = 0
    chain_events_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "report_date": self.report_date,
            "generated_at": self.generated_at.isoformat(),
            "section": self.section,
            "township": self.township,
            "range": self.range,
            "county": self.county,
            "state": self.state,
            "report_type": self.report_type,
            "input_folder": self.input_folder,
            "template_used": self.template_used,
            "sources_count": self.sources_count,
            "ownership_entries_count": self.ownership_entries_count,
            "chain_events_count": self.chain_events_count
        }


@dataclass
class QAResult:
    """Results from QA checks."""
    
    check_name: str
    passed: bool
    message: str
    severity: str = "info"  # info, warning, error, critical
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity,
            "details": self.details
        }


@dataclass
class ReportBundle:
    """Complete bundle of report data."""
    
    metadata: ReportMetadata
    source_documents: List[SourceDocument] = field(default_factory=list)
    ownership_entries: List[OwnershipEntry] = field(default_factory=list)
    chain_events: List[ChainEvent] = field(default_factory=list)
    missing_items: List[str] = field(default_factory=list)
    exceptions: List[str] = field(default_factory=list)
    qa_results: List[QAResult] = field(default_factory=list)
    confidence_score: float = 0.0
    analyst_notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "metadata": self.metadata.to_dict(),
            "source_documents": [doc.to_dict() for doc in self.source_documents],
            "ownership_entries": [entry.to_dict() for entry in self.ownership_entries],
            "chain_events": [event.to_dict() for event in self.chain_events],
            "missing_items": self.missing_items,
            "exceptions": self.exceptions,
            "qa_results": [result.to_dict() for result in self.qa_results],
            "confidence_score": self.confidence_score,
            "analyst_notes": self.analyst_notes
        }
