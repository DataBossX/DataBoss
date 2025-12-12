"""
Input normalization module.
Converts various input formats into standard internal representation.
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from .case import Case

logger = logging.getLogger(__name__)


@dataclass
class NormalizedTract:
    """Standard tract representation."""
    tract_id: str
    legal_description: str
    gross_acres: Optional[float] = None
    net_acres: Optional[float] = None
    township: Optional[str] = None
    range: Optional[str] = None
    section: Optional[int] = None
    source: str = "unknown"
    source_file: str = ""
    confidence_score: float = 0.0


@dataclass
class NormalizedOwner:
    """Standard owner representation."""
    owner_name: str
    tract_id: str
    ownership_type: str  # MINERAL, LEASEHOLD, WORKING_INTEREST
    interest_decimal: Optional[float] = None
    interest_fraction: Optional[str] = None
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    source: str = "unknown"


class InputNormalizer:
    """Normalizes various input formats."""

    def __init__(self):
        """Initialize normalizer."""
        self.tracts: List[NormalizedTract] = []
        self.owners: List[NormalizedOwner] = []

    def normalize_pdf_tracts(self, pdf_tracts: List) -> List[NormalizedTract]:
        """
        Normalize PDF tract data.

        Args:
            pdf_tracts: List of PDFTractInfo objects

        Returns:
            List of NormalizedTract objects
        """
        normalized = []

        for tract in pdf_tracts:
            norm_tract = NormalizedTract(
                tract_id=tract.tract_id,
                legal_description=tract.legal_description,
                gross_acres=tract.gross_acres,
                net_acres=tract.net_acres,
                source="pdf",
                source_file=tract.source_file,
                confidence_score=tract.confidence_score
            )

            # Extract township/range/section if possible
            self._parse_plss(norm_tract)

            normalized.append(norm_tract)

        logger.info(f"Normalized {len(normalized)} PDF tracts")
        return normalized

    def normalize_spreadsheet_tracts(self, sheet_tracts: List) -> List[NormalizedTract]:
        """
        Normalize spreadsheet tract data.

        Args:
            sheet_tracts: List of SpreadsheetTract objects

        Returns:
            List of NormalizedTract objects
        """
        normalized = []

        for tract in sheet_tracts:
            norm_tract = NormalizedTract(
                tract_id=tract.tract_id,
                legal_description=tract.legal_description,
                gross_acres=tract.gross_acres,
                net_acres=tract.net_acres,
                source="spreadsheet",
                source_file=tract.source_file,
                confidence_score=80.0
            )

            # Extract PLSS components
            self._parse_plss(norm_tract)

            normalized.append(norm_tract)

            # If owner data exists, normalize it too
            if tract.owner_name:
                owner = NormalizedOwner(
                    owner_name=tract.owner_name,
                    tract_id=tract.tract_id,
                    ownership_type=tract.ownership_type or "MINERAL",
                    interest_fraction=tract.interest,
                    source="spreadsheet"
                )
                self.owners.append(owner)

        logger.info(f"Normalized {len(normalized)} spreadsheet tracts")
        return normalized

    def _parse_plss(self, tract: NormalizedTract) -> None:
        """
        Parse PLSS components from legal description.

        Args:
            tract: NormalizedTract to update
        """
        import re

        legal = tract.legal_description

        # Extract Township
        township_match = re.search(r'T\s*(\d+[NS])', legal, re.IGNORECASE)
        if township_match:
            tract.township = township_match.group(1).upper()

        # Extract Range
        range_match = re.search(r'R\s*(\d+[EW])', legal, re.IGNORECASE)
        if range_match:
            tract.range = range_match.group(1).upper()

        # Extract Section
        section_match = re.search(r'Sec\.?\s*(\d+)', legal, re.IGNORECASE)
        if section_match:
            try:
                tract.section = int(section_match.group(1))
            except ValueError:
                pass

    def merge_duplicate_tracts(self) -> List[NormalizedTract]:
        """
        Merge duplicate tracts (same legal description).

        Returns:
            Deduplicated list of tracts
        """
        tract_map: Dict[str, NormalizedTract] = {}

        for tract in self.tracts:
            # Use normalized legal description as key
            key = self._normalize_legal_desc(tract.legal_description)

            if key not in tract_map:
                tract_map[key] = tract
            else:
                # Merge: keep highest confidence, fill in missing data
                existing = tract_map[key]

                if tract.confidence_score > existing.confidence_score:
                    tract_map[key] = tract
                else:
                    # Fill in missing fields from new tract
                    if not existing.gross_acres and tract.gross_acres:
                        existing.gross_acres = tract.gross_acres
                    if not existing.net_acres and tract.net_acres:
                        existing.net_acres = tract.net_acres

        logger.info(f"Merged {len(self.tracts)} tracts into {len(tract_map)} unique tracts")
        return list(tract_map.values())

    def _normalize_legal_desc(self, legal_desc: str) -> str:
        """
        Normalize legal description for comparison.

        Args:
            legal_desc: Legal description

        Returns:
            Normalized string
        """
        # Remove extra whitespace, convert to uppercase
        normalized = " ".join(legal_desc.upper().split())

        # Standardize abbreviations
        replacements = {
            "SECTION": "SEC",
            "TOWNSHIP": "T",
            "RANGE": "R",
        }

        for old, new in replacements.items():
            normalized = normalized.replace(old, new)

        return normalized

    def validate_normalized_data(self) -> Dict:
        """
        Validate normalized data.

        Returns:
            Validation results
        """
        errors = []
        warnings = []

        if not self.tracts:
            errors.append("No tracts found after normalization")

        # Check for missing critical fields
        missing_legal = sum(1 for t in self.tracts if not t.legal_description)
        if missing_legal > 0:
            errors.append(f"{missing_legal} tracts missing legal description")

        # Check PLSS parsing success rate
        with_plss = sum(1 for t in self.tracts if t.township and t.range and t.section)
        plss_rate = with_plss / len(self.tracts) * 100 if self.tracts else 0

        if plss_rate < 50:
            warnings.append(f"Only {plss_rate:.1f}% of tracts have complete PLSS data")

        # Check average confidence
        avg_confidence = sum(t.confidence_score for t in self.tracts) / len(self.tracts) if self.tracts else 0
        if avg_confidence < 60:
            warnings.append(f"Low average confidence score: {avg_confidence:.1f}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total_tracts": len(self.tracts),
            "total_owners": len(self.owners),
            "plss_parse_rate": plss_rate,
            "average_confidence": avg_confidence
        }

    def get_summary(self) -> Dict:
        """
        Get summary of normalized data.

        Returns:
            Summary dictionary
        """
        return {
            "total_tracts": len(self.tracts),
            "total_owners": len(self.owners),
            "tracts_by_source": {
                "pdf": sum(1 for t in self.tracts if t.source == "pdf"),
                "spreadsheet": sum(1 for t in self.tracts if t.source == "spreadsheet"),
                "manual": sum(1 for t in self.tracts if t.source == "manual")
            },
            "tracts_with_acres": sum(1 for t in self.tracts if t.gross_acres or t.net_acres),
            "tracts_with_complete_plss": sum(1 for t in self.tracts if t.township and t.range and t.section)
        }

    def normalize_to_case(
        self,
        pdf_tracts: List,
        sheet_tracts: List,
        unit_name: Optional[str] = None,
        county: Optional[str] = None,
        state: Optional[str] = None,
        plss_meridian: str = "6PM"
    ) -> Case:
        """
        Normalize all inputs into a Case object.

        Args:
            pdf_tracts: List of PDF tract objects
            sheet_tracts: List of spreadsheet tract objects
            unit_name: Unit name
            county: County
            state: State
            plss_meridian: PLSS meridian

        Returns:
            Case object with normalized data
        """
        # Normalize tracts
        normalized_tracts = []
        normalized_tracts.extend(self.normalize_pdf_tracts(pdf_tracts))
        normalized_tracts.extend(self.normalize_spreadsheet_tracts(sheet_tracts))

        # Store for later access
        self.tracts = normalized_tracts

        # Create Case object
        case = Case(
            unit_name=unit_name,
            county=county,
            state=state,
            plss_meridian=plss_meridian,
            unit_tracts=normalized_tracts,
            source_files=list(set(t.source_file for t in normalized_tracts if t.source_file))
        )

        logger.info(f"Created case with {len(normalized_tracts)} tracts")

        return case
