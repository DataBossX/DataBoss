"""
Owner resolver - identifies mineral and working interest owners for tracts.
Distinguishes between mineral owners (UMI/ROY) and leasehold/WI owners.
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class OwnershipType(Enum):
    """Types of ownership interest."""
    MINERAL = "MINERAL"  # Surface/mineral owner
    LEASEHOLD = "LEASEHOLD"  # Lessee/operator
    WORKING_INTEREST = "WORKING_INTEREST"  # Non-op WI
    ROYALTY = "ROYALTY"  # ORRI or other royalty
    UNKNOWN = "UNKNOWN"


@dataclass
class Owner:
    """Represents an owner with interest in a tract."""
    owner_id: str
    owner_name: str
    ownership_type: OwnershipType
    tract_id: str
    interest_decimal: Optional[float] = None
    interest_fraction: Optional[str] = None
    source: str = "unknown"
    source_date: Optional[datetime] = None
    confidence_score: float = 0.0
    raw_data: Optional[Dict] = None


class OwnerResolver:
    """Resolves ownership information for tracts."""

    def __init__(self):
        """Initialize owner resolver."""
        self.owners: Dict[str, List[Owner]] = {}  # tract_id -> list of owners

    def add_owner_from_instrument(
        self,
        tract_id: str,
        owner_name: str,
        ownership_type: str,
        interest: str,
        instrument_data: Dict
    ) -> Owner:
        """
        Add owner from recorded instrument.

        Args:
            tract_id: Tract identifier
            owner_name: Owner name
            ownership_type: Type of ownership (MINERAL, LEASEHOLD, etc.)
            interest: Interest amount (decimal or fraction)
            instrument_data: Raw instrument data

        Returns:
            Created Owner object
        """
        # Parse ownership type
        try:
            owner_type = OwnershipType[ownership_type.upper()]
        except KeyError:
            logger.warning(f"Unknown ownership type: {ownership_type}, using UNKNOWN")
            owner_type = OwnershipType.UNKNOWN

        # Parse interest
        interest_decimal = self._parse_interest(interest)

        owner = Owner(
            owner_id=f"{tract_id}_{owner_name}_{datetime.now().timestamp()}",
            owner_name=owner_name.strip(),
            ownership_type=owner_type,
            tract_id=tract_id,
            interest_decimal=interest_decimal,
            interest_fraction=interest,
            source="recorded_instrument",
            source_date=instrument_data.get("recording_date"),
            confidence_score=90.0,
            raw_data=instrument_data
        )

        # Add to owner registry
        if tract_id not in self.owners:
            self.owners[tract_id] = []

        self.owners[tract_id].append(owner)
        logger.info(f"Added owner {owner_name} for tract {tract_id}")

        return owner

    def add_owner_from_spreadsheet(
        self,
        tract_id: str,
        owner_name: str,
        ownership_type: str,
        interest: Optional[str] = None
    ) -> Owner:
        """
        Add owner from spreadsheet data.

        Args:
            tract_id: Tract identifier
            owner_name: Owner name
            ownership_type: Type of ownership
            interest: Interest amount

        Returns:
            Created Owner object
        """
        try:
            owner_type = OwnershipType[ownership_type.upper()]
        except KeyError:
            owner_type = OwnershipType.UNKNOWN

        interest_decimal = self._parse_interest(interest) if interest else None

        owner = Owner(
            owner_id=f"{tract_id}_{owner_name}_{datetime.now().timestamp()}",
            owner_name=owner_name.strip(),
            ownership_type=owner_type,
            tract_id=tract_id,
            interest_decimal=interest_decimal,
            interest_fraction=interest,
            source="spreadsheet",
            source_date=datetime.now(),
            confidence_score=70.0
        )

        if tract_id not in self.owners:
            self.owners[tract_id] = []

        self.owners[tract_id].append(owner)

        return owner

    def _parse_interest(self, interest_str: str) -> Optional[float]:
        """
        Parse interest string to decimal.

        Args:
            interest_str: Interest as fraction (e.g., "1/8") or decimal

        Returns:
            Decimal interest or None
        """
        if not interest_str:
            return None

        interest_str = str(interest_str).strip()

        # Try fraction format (e.g., "1/8")
        if "/" in interest_str:
            try:
                parts = interest_str.split("/")
                numerator = float(parts[0])
                denominator = float(parts[1])
                return numerator / denominator
            except (ValueError, ZeroDivisionError) as e:
                logger.warning(f"Failed to parse fraction interest {interest_str}: {e}")
                return None

        # Try decimal format
        try:
            return float(interest_str)
        except ValueError:
            logger.warning(f"Failed to parse decimal interest {interest_str}")
            return None

    def get_owners_by_tract(self, tract_id: str) -> List[Owner]:
        """
        Get all owners for a tract.

        Args:
            tract_id: Tract identifier

        Returns:
            List of owners
        """
        return self.owners.get(tract_id, [])

    def get_mineral_owners(self, tract_id: str) -> List[Owner]:
        """
        Get mineral owners for a tract (excludes leasehold/WI).

        Args:
            tract_id: Tract identifier

        Returns:
            List of mineral owners
        """
        all_owners = self.get_owners_by_tract(tract_id)
        return [o for o in all_owners if o.ownership_type == OwnershipType.MINERAL]

    def get_leasehold_owners(self, tract_id: str) -> List[Owner]:
        """
        Get leasehold/WI owners for a tract.

        Args:
            tract_id: Tract identifier

        Returns:
            List of leasehold/WI owners
        """
        all_owners = self.get_owners_by_tract(tract_id)
        return [o for o in all_owners
                if o.ownership_type in [OwnershipType.LEASEHOLD, OwnershipType.WORKING_INTEREST]]

    def deduplicate_owners(self, tract_id: str) -> List[Owner]:
        """
        Deduplicate owners for a tract (same name = same owner).

        Args:
            tract_id: Tract identifier

        Returns:
            Deduplicated list of owners
        """
        all_owners = self.get_owners_by_tract(tract_id)

        # Group by name and ownership type
        owner_map: Dict[tuple, Owner] = {}

        for owner in all_owners:
            key = (owner.owner_name.upper(), owner.ownership_type)

            if key not in owner_map:
                owner_map[key] = owner
            else:
                # Keep the one with higher confidence
                if owner.confidence_score > owner_map[key].confidence_score:
                    owner_map[key] = owner

        return list(owner_map.values())

    def validate_ownership(self, tract_id: str) -> Dict[str, any]:
        """
        Validate ownership data for a tract.

        Args:
            tract_id: Tract identifier

        Returns:
            Validation results
        """
        owners = self.get_owners_by_tract(tract_id)

        if not owners:
            return {
                "valid": False,
                "errors": ["No owners found for tract"],
                "warnings": []
            }

        errors = []
        warnings = []

        # Check for ownership gaps (interests don't add up to 1.0)
        mineral_owners = self.get_mineral_owners(tract_id)
        total_mineral_interest = sum(o.interest_decimal for o in mineral_owners
                                     if o.interest_decimal is not None)

        if total_mineral_interest > 0 and abs(total_mineral_interest - 1.0) > 0.01:
            warnings.append(f"Mineral interests sum to {total_mineral_interest}, expected 1.0")

        # Check for unknown ownership types
        unknown_count = sum(1 for o in owners if o.ownership_type == OwnershipType.UNKNOWN)
        if unknown_count > 0:
            warnings.append(f"{unknown_count} owners have UNKNOWN ownership type")

        # Check confidence scores
        low_confidence = [o for o in owners if o.confidence_score < 50.0]
        if low_confidence:
            warnings.append(f"{len(low_confidence)} owners have low confidence scores")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total_owners": len(owners),
            "mineral_owners": len(mineral_owners),
            "total_mineral_interest": total_mineral_interest
        }
