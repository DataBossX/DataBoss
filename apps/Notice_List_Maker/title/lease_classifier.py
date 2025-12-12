"""
Lease status classifier - determines UMI, ROY, or WI status.

HARD RULES (no exceptions):
- UMI = unleased mineral interest (owner owns minerals, no active lease)
- ROY = royalty interest (owner owns minerals, has active lease)
- WI = working interest (leasehold, operator, non-op working interest)
"""

import logging
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class LeaseStatus(Enum):
    """Lease status categories."""
    UMI = "UMI"  # Unleased Mineral Interest
    ROY = "ROY"  # Royalty (leased mineral)
    WI = "WI"    # Working Interest (leasehold)
    UNKNOWN = "UNKNOWN"


@dataclass
class Lease:
    """Represents a lease on a tract."""
    lease_id: str
    tract_id: str
    lessee_name: str
    lessor_name: str
    effective_date: Optional[datetime]
    expiration_date: Optional[datetime]
    is_active: bool
    primary_term_years: Optional[int] = None
    royalty_fraction: Optional[str] = None
    source: str = "unknown"
    raw_data: Optional[Dict] = None


class LeaseClassifier:
    """Classifies lease status for owners."""

    def __init__(self):
        """Initialize lease classifier."""
        self.leases: Dict[str, List[Lease]] = {}  # tract_id -> list of leases

    def add_lease(
        self,
        lease_id: str,
        tract_id: str,
        lessee_name: str,
        lessor_name: str,
        effective_date: Optional[datetime],
        expiration_date: Optional[datetime],
        is_active: bool,
        **kwargs
    ) -> Lease:
        """
        Add a lease to the system.

        Args:
            lease_id: Unique lease identifier
            tract_id: Tract identifier
            lessee_name: Name of lessee (operator)
            lessor_name: Name of lessor (mineral owner)
            effective_date: Lease effective date
            expiration_date: Lease expiration date
            is_active: Whether lease is currently active
            **kwargs: Additional lease data

        Returns:
            Created Lease object
        """
        lease = Lease(
            lease_id=lease_id,
            tract_id=tract_id,
            lessee_name=lessee_name.strip(),
            lessor_name=lessor_name.strip(),
            effective_date=effective_date,
            expiration_date=expiration_date,
            is_active=is_active,
            primary_term_years=kwargs.get("primary_term_years"),
            royalty_fraction=kwargs.get("royalty_fraction"),
            source=kwargs.get("source", "unknown"),
            raw_data=kwargs.get("raw_data")
        )

        if tract_id not in self.leases:
            self.leases[tract_id] = []

        self.leases[tract_id].append(lease)
        logger.info(f"Added {'active' if is_active else 'inactive'} lease {lease_id} for tract {tract_id}")

        return lease

    def get_active_leases(self, tract_id: str) -> List[Lease]:
        """
        Get active leases for a tract.

        Args:
            tract_id: Tract identifier

        Returns:
            List of active leases
        """
        all_leases = self.leases.get(tract_id, [])
        return [lease for lease in all_leases if lease.is_active]

    def has_active_lease(self, tract_id: str, owner_name: Optional[str] = None) -> bool:
        """
        Check if tract (or specific owner) has active lease.

        Args:
            tract_id: Tract identifier
            owner_name: Optional owner name to check specific owner

        Returns:
            True if active lease exists
        """
        active_leases = self.get_active_leases(tract_id)

        if not active_leases:
            return False

        if owner_name:
            # Check if this specific owner has leased their minerals
            owner_name_upper = owner_name.strip().upper()
            return any(
                lease.lessor_name.upper() == owner_name_upper
                for lease in active_leases
            )

        return True

    def classify_owner(
        self,
        owner_name: str,
        ownership_type: str,
        tract_id: str
    ) -> LeaseStatus:
        """
        Classify owner lease status using HARD RULES.

        Rules:
        1. If ownership_type is LEASEHOLD or WORKING_INTEREST → WI
        2. If ownership_type is MINERAL:
           - AND has active lease → ROY
           - AND no active lease → UMI
        3. Otherwise → UNKNOWN

        Args:
            owner_name: Owner name
            ownership_type: Type of ownership (MINERAL, LEASEHOLD, etc.)
            tract_id: Tract identifier

        Returns:
            LeaseStatus classification
        """
        ownership_upper = ownership_type.upper()

        # Rule 1: Leasehold/WI owners are always WI
        if ownership_upper in ["LEASEHOLD", "WORKING_INTEREST"]:
            logger.debug(f"{owner_name} classified as WI (leasehold/working interest)")
            return LeaseStatus.WI

        # Rule 2: Mineral owners - check for active lease
        if ownership_upper == "MINERAL":
            has_lease = self.has_active_lease(tract_id, owner_name)

            if has_lease:
                logger.debug(f"{owner_name} classified as ROY (mineral owner with active lease)")
                return LeaseStatus.ROY
            else:
                logger.debug(f"{owner_name} classified as UMI (mineral owner without active lease)")
                return LeaseStatus.UMI

        # Rule 3: Unknown ownership type
        logger.warning(f"{owner_name} has unknown ownership type: {ownership_type}")
        return LeaseStatus.UNKNOWN

    def classify_batch(
        self,
        owners: List[Dict]
    ) -> Dict[str, LeaseStatus]:
        """
        Classify multiple owners.

        Args:
            owners: List of owner dictionaries with keys: owner_name, ownership_type, tract_id

        Returns:
            Dictionary mapping owner_name to LeaseStatus
        """
        classifications = {}

        for owner in owners:
            owner_name = owner.get("owner_name")
            ownership_type = owner.get("ownership_type")
            tract_id = owner.get("tract_id")

            if not all([owner_name, ownership_type, tract_id]):
                logger.warning(f"Incomplete owner data: {owner}")
                classifications[owner_name] = LeaseStatus.UNKNOWN
                continue

            status = self.classify_owner(owner_name, ownership_type, tract_id)
            classifications[owner_name] = status

        return classifications

    def get_classification_summary(self) -> Dict:
        """
        Get summary of lease classifications across all tracts.

        Returns:
            Summary statistics
        """
        total_tracts = len(self.leases)
        total_leases = sum(len(leases) for leases in self.leases.values())
        active_leases = sum(
            len(self.get_active_leases(tract_id))
            for tract_id in self.leases.keys()
        )

        return {
            "total_tracts_with_leases": total_tracts,
            "total_leases": total_leases,
            "active_leases": active_leases,
            "inactive_leases": total_leases - active_leases
        }

    def validate_lease(self, lease: Lease) -> Dict[str, any]:
        """
        Validate lease data.

        Args:
            lease: Lease object to validate

        Returns:
            Validation results
        """
        errors = []
        warnings = []

        # Check required fields
        if not lease.lessee_name:
            errors.append("Missing lessee_name")
        if not lease.lessor_name:
            errors.append("Missing lessor_name")

        # Check dates
        if lease.effective_date and lease.expiration_date:
            if lease.expiration_date <= lease.effective_date:
                errors.append("Expiration date must be after effective date")

        # Check active status
        if lease.is_active and lease.expiration_date:
            if lease.expiration_date < datetime.now():
                warnings.append("Lease marked active but expiration date has passed")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
