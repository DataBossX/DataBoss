"""
Base connector interface for external data sources.
All connectors must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class OwnerSearchResult:
    """Result from owner search."""
    owner_name: str
    tract_id: str
    ownership_type: str  # MINERAL, LEASEHOLD, WORKING_INTEREST
    interest_decimal: Optional[float] = None
    interest_fraction: Optional[str] = None
    source: str = "unknown"
    confidence_score: float = 0.0
    evidence: List[Dict] = None  # List of evidence records

    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []


@dataclass
class AddressSearchResult:
    """Result from address search."""
    owner_name: str
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "USA"
    source: str = "unknown"
    source_date: Optional[datetime] = None
    confidence_score: float = 0.0
    evidence: List[Dict] = None  # List of evidence records

    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []


@dataclass
class LeaseSearchResult:
    """Result from lease search."""
    lease_id: str
    tract_id: str
    lessee_name: str
    lessor_name: str
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    is_active: bool = False
    source: str = "unknown"
    evidence: List[Dict] = None

    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []


class BaseConnector(ABC):
    """
    Base interface for all connectors.

    All connectors must implement these methods and handle:
    - Timeouts
    - Retries with exponential backoff
    - Detailed error logging
    - Evidence tracking
    """

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        Initialize connector.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.success_count = 0
        self.failure_count = 0

    @abstractmethod
    async def search_owners(self, tract_key: str) -> List[OwnerSearchResult]:
        """
        Search for owners of a tract.

        Args:
            tract_key: Tract identifier (legal description or ID)

        Returns:
            List of owner search results
        """
        pass

    @abstractmethod
    async def resolve_address(self, owner_name: str) -> Optional[AddressSearchResult]:
        """
        Resolve current address for an owner.

        Args:
            owner_name: Owner name

        Returns:
            Address search result or None
        """
        pass

    @abstractmethod
    async def search_leases(self, tract_key: str) -> List[LeaseSearchResult]:
        """
        Search for leases on a tract.

        Args:
            tract_key: Tract identifier

        Returns:
            List of lease search results
        """
        pass

    def record_success(self):
        """Record successful operation."""
        self.success_count += 1

    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1

    def get_scorecard(self) -> Dict:
        """
        Get connector performance scorecard.

        Returns:
            Dictionary with success/failure stats
        """
        total = self.success_count + self.failure_count
        success_rate = self.success_count / total * 100 if total > 0 else 0

        return {
            "connector": self.__class__.__name__,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_requests": total,
            "success_rate": round(success_rate, 2)
        }
