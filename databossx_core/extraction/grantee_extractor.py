"""
Grantee (buyer/transferee) extractor
"""

import re
import uuid
from typing import List
from decimal import Decimal

from ..models.entity import Grantee, EntityType


class GranteeExtractor:
    """
    Extracts grantee information from legal documents
    """

    # Patterns for identifying grantees
    GRANTEE_PATTERNS = [
        # "GRANTEE:" or "Grantee:" followed by name
        r"grantee:\s*([A-Z][A-Za-z\s,.'&-]+?)(?:\n|,\s*whose)",
        # "to [GRANTEE]"
        r"(?:grant|convey|transfer|assign)(?:ed|s)?\s+(?:to|unto)\s+([A-Z][A-Za-z\s,.'&-]+?)(?:,\s*(?:a|an|of|in)\s+)",
        # Traditional pattern
        r"([A-Z][A-Za-z\s,.'&-]+?),\s+(?:grantee|buyer|assignee|lessee)",
        # Between "GRANTEE:" and terminating pattern
        r"grantee[:\s]+([A-Z][A-Za-z\s,.'&-]+?)(?:\n|,\s*a\s+)",
    ]

    # Patterns for percentage interest
    INTEREST_PATTERNS = [
        r"(\d+(?:\.\d+)?)\s*%\s*(?:interest|undivided interest)",
        r"an?\s+(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\s+(?:interest|undivided interest)",
        r"(\d+(?:\.\d+)?)\s+percent",
    ]

    def __init__(self):
        self.rules_used = []
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns"""
        self.compiled_grantee_patterns = [
            re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.GRANTEE_PATTERNS
        ]
        self.compiled_interest_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.INTEREST_PATTERNS
        ]

    async def extract(self, text: str) -> List[Grantee]:
        """
        Extract grantees from text

        Args:
            text: Document text

        Returns:
            List of Grantee objects
        """
        self.rules_used = []
        grantees = []
        seen_names = set()

        # Try each pattern
        for idx, pattern in enumerate(self.compiled_grantee_patterns):
            matches = pattern.finditer(text)
            for match in matches:
                name = match.group(1).strip()

                # Clean up name
                name = self._clean_name(name)

                # Skip duplicates
                if name.lower() in seen_names:
                    continue

                # Normalize name
                normalized_name = self._normalize_name(name)

                # Detect entity type
                entity_type = self._detect_entity_type(text, name)

                # Extract percentage interest
                percentage = self._extract_percentage(text, name)

                # Create grantee
                grantee = Grantee(
                    id=str(uuid.uuid4()),
                    name=name,
                    normalized_name=normalized_name,
                    entity_type=entity_type,
                    confidence=0.8 if idx == 0 else 0.7,
                    source_text=match.group(0),
                    percentage_interest=percentage,
                    metadata={
                        "pattern_index": idx,
                        "pattern": self.GRANTEE_PATTERNS[idx],
                    },
                )

                grantees.append(grantee)
                seen_names.add(name.lower())
                self.rules_used.append(f"grantee_pattern_{idx}")

        return grantees

    def _clean_name(self, name: str) -> str:
        """Clean extracted name"""
        # Remove common suffixes
        name = re.sub(r",\s*(?:grantee|buyer|assignee|lessee)\s*$", "", name, flags=re.IGNORECASE)
        # Remove excess whitespace
        name = " ".join(name.split())
        # Remove trailing punctuation
        name = name.rstrip(",.;:")
        return name

    def _normalize_name(self, name: str) -> str:
        """Normalize name for matching"""
        normalized = name.upper()

        # Standardize common abbreviations
        replacements = {
            " JR.": " JR",
            " SR.": " SR",
            " III": " III",
            " II": " II",
            " IV": " IV",
            ",": "",
            ".": "",
        }

        for old, new in replacements.items():
            normalized = normalized.replace(old, new)

        normalized = " ".join(normalized.split())
        return normalized

    def _detect_entity_type(self, text: str, name: str) -> EntityType:
        """Detect entity type"""
        name_lower = name.lower()

        # Corporate indicators
        corporate_indicators = [
            "corporation", "corp", "inc", "incorporated",
            "llc", "l.l.c.", "limited liability company",
            "ltd", "limited", "company", "co.",
        ]

        for indicator in corporate_indicators:
            if indicator in name_lower:
                if "llc" in name_lower or "limited liability" in name_lower:
                    return EntityType.LLC
                return EntityType.CORPORATION

        if "trust" in name_lower:
            return EntityType.TRUST

        if "estate" in name_lower:
            return EntityType.ESTATE

        if "partnership" in name_lower:
            return EntityType.PARTNERSHIP

        return EntityType.PERSON

    def _extract_percentage(self, text: str, name: str) -> Decimal:
        """Extract percentage interest if present"""
        # Look for percentage near the name
        name_pos = text.lower().find(name.lower())
        if name_pos == -1:
            return None

        # Get context around name
        context_start = max(0, name_pos - 100)
        context_end = min(len(text), name_pos + len(name) + 200)
        context = text[context_start:context_end]

        # Check interest patterns
        for pattern in self.compiled_interest_patterns:
            match = pattern.search(context)
            if match:
                # Handle different formats
                if len(match.groups()) == 2:
                    # Fraction format: 1/8
                    numerator = Decimal(match.group(1))
                    denominator = Decimal(match.group(2))
                    return numerator / denominator
                else:
                    # Percentage format: 12.5%
                    return Decimal(match.group(1)) / Decimal(100)

        return None

    def get_rules_used(self) -> List[str]:
        """Get list of rules used in extraction"""
        return self.rules_used
