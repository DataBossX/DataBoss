"""
ARC Search Connector (Stub)
For ArcGIS/county GIS integration.

TODO: Implement actual ARC Search API integration.
"""

from .base_connector import BaseConnector, OwnerSearchResult, AddressSearchResult, LeaseSearchResult
from .retry_handler import retry_with_backoff
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class ARCSearchConnector(BaseConnector):
    """
    Connector for ARC Search / GIS systems.

    STUB: Implementation needed.
    """

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key
        logger.info("ARCSearchConnector initialized (STUB)")

    @retry_with_backoff(max_retries=3)
    async def search_owners(self, tract_key: str) -> List[OwnerSearchResult]:
        """Search ARC for tract owners (STUB)."""
        logger.info(f"ARC search for tract: {tract_key} (STUB - not implemented)")
        self.record_success()
        return []

    @retry_with_backoff(max_retries=3)
    async def resolve_address(self, owner_name: str) -> Optional[AddressSearchResult]:
        """Resolve address via ARC (STUB)."""
        logger.info(f"ARC address search: {owner_name} (STUB - not implemented)")
        self.record_success()
        return None

    @retry_with_backoff(max_retries=3)
    async def search_leases(self, tract_key: str) -> List[LeaseSearchResult]:
        """Search for leases via ARC (STUB)."""
        logger.info(f"ARC lease search: {tract_key} (STUB - not implemented)")
        self.record_success()
        return []
