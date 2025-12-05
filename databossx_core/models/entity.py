"""
Legal entity extraction models
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from decimal import Decimal


class EntityType(str, Enum):
    """Types of legal entities"""
    PERSON = "person"
    CORPORATION = "corporation"
    LLC = "llc"
    PARTNERSHIP = "partnership"
    TRUST = "trust"
    ESTATE = "estate"
    GOVERNMENT = "government"
    UNKNOWN = "unknown"


class LegalEntity(BaseModel):
    """Base legal entity model"""
    id: str
    name: str
    normalized_name: str  # Standardized for matching
    entity_type: EntityType
    confidence: float
    source_text: str  # Original text from document
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Grantor(LegalEntity):
    """Grantor (seller/transferor) entity"""
    marital_status: Optional[str] = None
    spouse_name: Optional[str] = None
    address: Optional[str] = None


class Grantee(LegalEntity):
    """Grantee (buyer/transferee) entity"""
    address: Optional[str] = None
    percentage_interest: Optional[Decimal] = None


class AliquotPart(BaseModel):
    """Aliquot part of legal description (e.g., NE 1/4, SW 1/4)"""
    part: str  # "NE 1/4", "SW 1/4 of NW 1/4", etc.
    acres: Optional[Decimal] = None


class LegalDescription(BaseModel):
    """Parsed legal description"""
    id: str
    raw_text: str
    section: Optional[str] = None
    township: Optional[str] = None
    range: Optional[str] = None
    meridian: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None
    aliquot_parts: List[AliquotPart] = Field(default_factory=list)
    lots: List[str] = Field(default_factory=list)
    acres: Optional[Decimal] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DepthClause(BaseModel):
    """Depth limitation clause"""
    id: str
    raw_text: str
    from_depth: Optional[int] = None  # feet
    to_depth: Optional[int] = None  # feet
    formation_name: Optional[str] = None
    depth_type: str = "feet_from_surface"  # or "subsea", "formation"
    confidence: float = 0.0


class AcreageInfo(BaseModel):
    """Parsed acreage information"""
    total_acres: Optional[Decimal] = None
    net_acres: Optional[Decimal] = None
    gross_acres: Optional[Decimal] = None
    source_text: str
    confidence: float = 0.0


class EntityExtraction(BaseModel):
    """Complete entity extraction result"""
    id: str
    document_id: str
    grantors: List[Grantor] = Field(default_factory=list)
    grantees: List[Grantee] = Field(default_factory=list)
    legal_descriptions: List[LegalDescription] = Field(default_factory=list)
    depth_clauses: List[DepthClause] = Field(default_factory=list)
    acreage_info: Optional[AcreageInfo] = None
    extraction_rules_used: List[str] = Field(default_factory=list)
    overall_confidence: float = 0.0
    created_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
