"""
Case object - unified representation of a notice list case.
Combines all inputs (PDFs, spreadsheets, manual) into single structure.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class Case:
    """Complete representation of a notice list case."""

    # Metadata
    case_id: Optional[str] = None
    unit_name: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None
    plss_meridian: str = "6PM"

    # Tracts
    unit_tracts: List = field(default_factory=list)  # List of NormalizedTract

    # Processing metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Input sources
    source_files: List[str] = field(default_factory=list)

    # Processing status
    status: str = "pending"  # pending, processing, completed, failed

    # Results
    unit_tract_count: int = 0
    offset_tract_count: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "case_id": self.case_id,
            "unit_name": self.unit_name,
            "county": self.county,
            "state": self.state,
            "plss_meridian": self.plss_meridian,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "source_files": self.source_files,
            "status": self.status,
            "unit_tract_count": self.unit_tract_count,
            "offset_tract_count": self.offset_tract_count
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Case':
        """Create Case from dictionary."""
        return cls(
            case_id=data.get("case_id"),
            unit_name=data.get("unit_name"),
            county=data.get("county"),
            state=data.get("state"),
            plss_meridian=data.get("plss_meridian", "6PM"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            source_files=data.get("source_files", []),
            status=data.get("status", "pending"),
            unit_tract_count=data.get("unit_tract_count", 0),
            offset_tract_count=data.get("offset_tract_count", 0)
        )
