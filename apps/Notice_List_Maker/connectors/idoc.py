"""
iDocMarket Connector (Stub)
For state O&G commission data.

TODO: Implement actual iDocMarket API integration.
"""

from .base_connector import BaseConnector, OwnerSearchResult, AddressSearchResult, LeaseSearchResult
from .retry_handler import retry_with_backoff
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class IDocConnector(BaseConnector):
    """
    Connector for iDocMarket / state O&G commission databases.

    STUB: Implementation needed.
    """

    def __init__(self, state: str = "CO", api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.state = state
        self.api_key = api_key
        logger.info(f"IDocConnector initialized for {state} (STUB)")

    @retry_with_backoff(max_retries=3)
    async def search_owners(self, tract_key: str) -> List[OwnerSearchResult]:
        """Search iDoc for tract owners (STUB)."""
        logger.info(f"iDoc search for tract: {tract_key} (STUB - not implemented)")
        self.record_success()
        return []

    @retry_with_backoff(max_retries=3)
    async def resolve_address(self, owner_name: str) -> Optional[AddressSearchResult]:
        """Resolve address via iDoc (STUB)."""
        logger.info(f"iDoc address search: {owner_name} (STUB - not implemented)")
        self.record_success()
        return None

    @retry_with_backoff(max_retries=3)
    async def search_leases(self, tract_key: str) -> List[LeaseSearchResult]:
        """Search for leases via iDoc (STUB)."""
        logger.info(f"iDoc lease search: {tract_key} (STUB - not implemented)")
        self.record_success()
        return []
