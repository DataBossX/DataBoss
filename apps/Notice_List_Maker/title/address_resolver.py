"""
Address resolver - determines current mailing addresses for owners.
Follows explicit priority order and tracks source for every address.
"""

import logging
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class AddressSource(Enum):
    """Sources for address information."""
    RECENT_INSTRUMENT = "recent_instrument"
    COUNTY_TAX_ROLL = "county_tax_roll"
    OPERATOR_PAYDECK = "operator_paydeck"
    MANUAL_OVERRIDE = "manual_override"
    UNKNOWN = "unknown"


@dataclass
class Address:
    """Represents a mailing address."""
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "USA"

    def __str__(self):
        """Format address as single line."""
        return f"{self.street}, {self.city}, {self.state} {self.zip_code}"

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "street": self.street,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "country": self.country
        }


@dataclass
class ResolvedAddress:
    """Address with source tracking."""
    owner_name: str
    address: Address
    source: AddressSource
    source_date: Optional[datetime]
    confidence_score: float
    raw_data: Optional[Dict] = None


class AddressResolver:
    """Resolves current mailing addresses for owners."""

    # Priority order (higher = better)
    SOURCE_PRIORITY = {
        AddressSource.MANUAL_OVERRIDE: 100,
        AddressSource.RECENT_INSTRUMENT: 90,
        AddressSource.COUNTY_TAX_ROLL: 80,
        AddressSource.OPERATOR_PAYDECK: 70,
        AddressSource.UNKNOWN: 0,
    }

    def __init__(self):
        """Initialize address resolver."""
        self.addresses: Dict[str, List[ResolvedAddress]] = {}  # owner_name -> list of addresses

    def add_address(
        self,
        owner_name: str,
        street: str,
        city: str,
        state: str,
        zip_code: str,
        source: AddressSource,
        source_date: Optional[datetime] = None,
        raw_data: Optional[Dict] = None
    ) -> ResolvedAddress:
        """
        Add an address for an owner.

        Args:
            owner_name: Owner name
            street: Street address
            city: City
            state: State
            zip_code: ZIP code
            source: Address source
            source_date: Date of source
            raw_data: Raw data from source

        Returns:
            ResolvedAddress object
        """
        address = Address(
            street=street.strip(),
            city=city.strip(),
            state=state.strip().upper(),
            zip_code=zip_code.strip()
        )

        confidence_score = self._calculate_confidence(source, source_date)

        resolved = ResolvedAddress(
            owner_name=owner_name.strip(),
            address=address,
            source=source,
            source_date=source_date,
            confidence_score=confidence_score,
            raw_data=raw_data
        )

        owner_key = owner_name.strip().upper()
        if owner_key not in self.addresses:
            self.addresses[owner_key] = []

        self.addresses[owner_key].append(resolved)
        logger.info(f"Added address for {owner_name} from {source.value}")

        return resolved

    def add_address_from_instrument(
        self,
        owner_name: str,
        address_line: str,
        recording_date: datetime,
        instrument_data: Dict
    ) -> Optional[ResolvedAddress]:
        """
        Add address from recorded instrument.

        Args:
            owner_name: Owner name
            address_line: Full address line
            recording_date: Recording date
            instrument_data: Raw instrument data

        Returns:
            ResolvedAddress or None if parsing failed
        """
        parsed = self._parse_address_line(address_line)
        if not parsed:
            logger.warning(f"Failed to parse address from instrument: {address_line}")
            return None

        return self.add_address(
            owner_name=owner_name,
            street=parsed["street"],
            city=parsed["city"],
            state=parsed["state"],
            zip_code=parsed["zip_code"],
            source=AddressSource.RECENT_INSTRUMENT,
            source_date=recording_date,
            raw_data=instrument_data
        )

    def add_address_from_tax_roll(
        self,
        owner_name: str,
        address_line: str,
        tax_year: int
    ) -> Optional[ResolvedAddress]:
        """
        Add address from county tax roll.

        Args:
            owner_name: Owner name
            address_line: Full address line
            tax_year: Tax year

        Returns:
            ResolvedAddress or None if parsing failed
        """
        parsed = self._parse_address_line(address_line)
        if not parsed:
            return None

        return self.add_address(
            owner_name=owner_name,
            street=parsed["street"],
            city=parsed["city"],
            state=parsed["state"],
            zip_code=parsed["zip_code"],
            source=AddressSource.COUNTY_TAX_ROLL,
            source_date=datetime(tax_year, 12, 31)
        )

    def _parse_address_line(self, address_line: str) -> Optional[Dict]:
        """
        Parse address line into components.

        This is a simplified parser. Production version would use
        proper address validation service.

        Args:
            address_line: Full address (e.g., "123 Main St, Denver, CO 80202")

        Returns:
            Dictionary with address components or None
        """
        if not address_line:
            return None

        parts = [p.strip() for p in address_line.split(",")]

        if len(parts) < 3:
            # Try different format: "123 Main St Denver CO 80202"
            words = address_line.split()
            if len(words) >= 4:
                # Very rough parsing
                street = " ".join(words[:-3])
                city = words[-3]
                state = words[-2]
                zip_code = words[-1]
            else:
                return None
        else:
            street = parts[0]
            city = parts[1]

            # Last part should be "STATE ZIP"
            last_part = parts[-1].strip().split()
            if len(last_part) >= 2:
                state = last_part[0]
                zip_code = last_part[1]
            else:
                return None

        return {
            "street": street,
            "city": city,
            "state": state,
            "zip_code": zip_code
        }

    def get_best_address(self, owner_name: str) -> Optional[ResolvedAddress]:
        """
        Get best address for an owner based on source priority.

        Args:
            owner_name: Owner name

        Returns:
            Best ResolvedAddress or None if no addresses found
        """
        owner_key = owner_name.strip().upper()
        addresses = self.addresses.get(owner_key, [])

        if not addresses:
            logger.warning(f"No addresses found for {owner_name}")
            return None

        # Sort by priority and date
        sorted_addresses = sorted(
            addresses,
            key=lambda a: (
                self.SOURCE_PRIORITY.get(a.source, 0),
                a.source_date if a.source_date else datetime.min
            ),
            reverse=True
        )

        best = sorted_addresses[0]
        logger.debug(f"Best address for {owner_name}: {best.source.value}")

        return best

    def _calculate_confidence(
        self,
        source: AddressSource,
        source_date: Optional[datetime]
    ) -> float:
        """
        Calculate confidence score for an address.

        Args:
            source: Address source
            source_date: Date of source

        Returns:
            Confidence score (0-100)
        """
        base_score = self.SOURCE_PRIORITY.get(source, 0)

        # Reduce confidence if source is old
        if source_date:
            days_old = (datetime.now() - source_date).days
            years_old = days_old / 365.0

            # Reduce by 10 points per year (max 30 point reduction)
            age_penalty = min(years_old * 10, 30)
            base_score -= age_penalty

        return max(base_score, 0)

    def validate_address(self, address: Address) -> Dict[str, any]:
        """
        Validate address completeness.

        Args:
            address: Address to validate

        Returns:
            Validation results
        """
        errors = []
        warnings = []

        if not address.street:
            errors.append("Missing street address")
        if not address.city:
            errors.append("Missing city")
        if not address.state:
            errors.append("Missing state")
        if not address.zip_code:
            errors.append("Missing ZIP code")

        # Validate state (2-letter code)
        if address.state and len(address.state) != 2:
            warnings.append("State should be 2-letter code")

        # Validate ZIP (5 or 9 digits)
        if address.zip_code:
            zip_digits = address.zip_code.replace("-", "")
            if not (len(zip_digits) == 5 or len(zip_digits) == 9):
                warnings.append("ZIP code should be 5 or 9 digits")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def get_resolution_summary(self) -> Dict:
        """
        Get summary statistics for address resolution.

        Returns:
            Summary dictionary
        """
        total_owners = len(self.addresses)
        total_addresses = sum(len(addrs) for addrs in self.addresses.values())

        by_source = {source: 0 for source in AddressSource}
        for addrs in self.addresses.values():
            for addr in addrs:
                by_source[addr.source] += 1

        owners_with_best = sum(
            1 for owner in self.addresses.keys()
            if self.get_best_address(owner)
        )

        return {
            "total_owners": total_owners,
            "total_addresses": total_addresses,
            "owners_with_address": owners_with_best,
            "addresses_by_source": {k.value: v for k, v in by_source.items()},
            "average_addresses_per_owner": total_addresses / total_owners if total_owners > 0 else 0
        }
