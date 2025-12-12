"""
Connector Manager - orchestrates multiple connectors.
Aggregates results from different sources and ranks by confidence.
"""

import logging
from typing import List, Optional, Dict
import asyncio

from .base_connector import OwnerSearchResult, AddressSearchResult, LeaseSearchResult
from .county_records import CountyRecordsConnector
# Import other connectors as implemented
# from .arc_search import ARCSearchConnector
# from .idoc import IDocConnector

logger = logging.getLogger(__name__)


class ConnectorManager:
    """
    Manages multiple connectors and aggregates results.
    """

    def __init__(self, database, county: Optional[str] = None, state: Optional[str] = None):
        """
        Initialize connector manager.

        Args:
            database: Database instance for caching
            county: County name
            state: State code
        """
        self.db = database
        self.county = county
        self.state = state

        # Initialize available connectors
        self.connectors = []

        if county and state:
            self.connectors.append(
                CountyRecordsConnector(county=county, state=state)
            )

        # Add more connectors as they become available
        # self.connectors.append(ARCSearchConnector())
        # self.connectors.append(IDocConnector())

        logger.info(f"Initialized {len(self.connectors)} connectors")

    async def search_owners(self, tract_key: str) -> List[OwnerSearchResult]:
        """
        Search for owners across all connectors.

        Args:
            tract_key: Tract identifier

        Returns:
            Aggregated list of owners
        """
        # Run searches in parallel
        tasks = [
            connector.search_owners(tract_key)
            for connector in self.connectors
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        all_owners = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Connector search failed: {result}")
                continue

            if isinstance(result, list):
                all_owners.extend(result)

        # Deduplicate and rank by confidence
        deduplicated = self._deduplicate_owners(all_owners)

        logger.info(f"Found {len(deduplicated)} unique owners for tract {tract_key}")

        return deduplicated

    async def resolve_address(self, owner_name: str) -> Optional[AddressSearchResult]:
        """
        Resolve address across all connectors.

        Args:
            owner_name: Owner name

        Returns:
            Best address result or None
        """
        # Run in parallel
        tasks = [
            connector.resolve_address(owner_name)
            for connector in self.connectors
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter and rank
        addresses = []
        for result in results:
            if isinstance(result, AddressSearchResult):
                addresses.append(result)

        if not addresses:
            return None

        # Return highest confidence
        best = max(addresses, key=lambda a: a.confidence_score)

        logger.info(f"Resolved address for {owner_name} from {best.source}")

        return best

    async def search_leases(self, tract_key: str) -> List[LeaseSearchResult]:
        """
        Search for leases across all connectors.

        Args:
            tract_key: Tract identifier

        Returns:
            List of leases
        """
        tasks = [
            connector.search_leases(tract_key)
            for connector in self.connectors
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_leases = []
        for result in results:
            if isinstance(result, list):
                all_leases.extend(result)

        # Deduplicate
        deduplicated = self._deduplicate_leases(all_leases)

        return deduplicated

    def _deduplicate_owners(self, owners: List[OwnerSearchResult]) -> List[OwnerSearchResult]:
        """
        Deduplicate owners by name and tract.

        Keeps highest confidence result for each unique owner.
        """
        owner_map = {}

        for owner in owners:
            key = (owner.owner_name.upper(), owner.tract_id)

            if key not in owner_map:
                owner_map[key] = owner
            else:
                # Keep higher confidence
                if owner.confidence_score > owner_map[key].confidence_score:
                    owner_map[key] = owner

        return list(owner_map.values())

    def _deduplicate_leases(self, leases: List[LeaseSearchResult]) -> List[LeaseSearchResult]:
        """Deduplicate leases."""
        lease_map = {}

        for lease in leases:
            # Use lessee/lessor/tract as key
            key = (lease.lessee_name.upper(), lease.lessor_name.upper(), lease.tract_id)

            if key not in lease_map:
                lease_map[key] = lease

        return list(lease_map.values())

    def get_scorecard(self) -> Dict:
        """
        Get performance scorecard for all connectors.

        Returns:
            Dictionary with stats for each connector
        """
        scorecard = {
            "total_connectors": len(self.connectors),
            "connectors": []
        }

        for connector in self.connectors:
            scorecard["connectors"].append(connector.get_scorecard())

        return scorecard
