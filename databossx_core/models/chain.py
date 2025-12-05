"""
Chain-of-title models
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from decimal import Decimal


class InterestType(str, Enum):
    """Types of mineral interests"""
    MINERAL = "mineral"
    WORKING_INTEREST = "working_interest"
    ROYALTY = "royalty"
    OVERRIDING_ROYALTY = "overriding_royalty"
    NET_REVENUE = "net_revenue"
    SURFACE = "surface"
    LEASEHOLD = "leasehold"
    UNKNOWN = "unknown"


class OwnershipType(str, Enum):
    """Types of ownership"""
    FEE_SIMPLE = "fee_simple"
    LIFE_ESTATE = "life_estate"
    LEASEHOLD = "leasehold"
    EASEMENT = "easement"
    UNDIVIDED_INTEREST = "undivided_interest"


class Ownership(BaseModel):
    """Ownership interest"""
    owner_id: str
    owner_name: str
    interest_type: InterestType
    ownership_type: OwnershipType
    fraction: Optional[Decimal] = None  # e.g., 0.125 for 1/8
    acres: Optional[Decimal] = None
    depth_from: Optional[int] = None
    depth_to: Optional[int] = None
    effective_date: Optional[datetime] = None
    termination_date: Optional[datetime] = None
    source_document_id: str
    confidence: float = 0.0


class ChainNode(BaseModel):
    """Node in chain-of-title graph"""
    id: str
    entity_name: str
    normalized_name: str
    ownerships: List[Ownership] = Field(default_factory=list)
    is_current_owner: bool = False
    is_original_grantor: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChainLink(BaseModel):
    """Link between nodes in chain"""
    id: str
    from_node_id: str
    to_node_id: str
    document_id: str
    transaction_date: Optional[datetime] = None
    transaction_type: str  # "conveyance", "devise", "assignment", etc.
    interest_transferred: InterestType
    fraction_transferred: Optional[Decimal] = None
    consideration: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChainGap(BaseModel):
    """Identified gap or inconsistency in chain"""
    id: str
    gap_type: str  # "missing_link", "fractional_mismatch", "date_conflict", "missing_heir"
    description: str
    severity: str  # "critical", "warning", "info"
    from_document_id: Optional[str] = None
    to_document_id: Optional[str] = None
    suggested_resolution: Optional[str] = None
    confidence: float = 0.0


class ChainGraph(BaseModel):
    """Complete chain-of-title graph"""
    id: str
    property_description: str
    nodes: List[ChainNode] = Field(default_factory=list)
    links: List[ChainLink] = Field(default_factory=list)
    gaps: List[ChainGap] = Field(default_factory=list)
    current_owners: List[str] = Field(default_factory=list)  # node IDs
    original_grantors: List[str] = Field(default_factory=list)  # node IDs
    interest_type: InterestType
    created_at: datetime
    last_updated: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChainAnalysis(BaseModel):
    """Analysis of chain-of-title"""
    chain_id: str
    is_marketable: bool
    marketability_issues: List[str] = Field(default_factory=list)
    fractional_reconciliation: Dict[str, Any] = Field(default_factory=dict)
    missing_successors: List[str] = Field(default_factory=list)
    unrecorded_instruments: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    analysis_date: datetime
