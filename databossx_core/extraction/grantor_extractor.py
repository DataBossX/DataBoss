"""
Grantor (seller/transferor) extractor
"""

import re
import uuid
from typing import List

from ..models.entity import Grantor, EntityType


class GrantorExtractor:
    """
    Extracts grantor information from legal documents
    """

    # Patterns for identifying grantors
    GRANTOR_PATTERNS = [
        # "GRANTOR:" or "Grantor:" followed by name
        r"grantor:\s*([A-Z][A-Za-z\s,.'&-]+?)(?:,\s*(?:a|an)\s+)",
        # "KNOW ALL MEN BY THESE PRESENTS, that [GRANTOR]"
        r"know all (?:men|persons) by these presents,?\s+that\s+([A-Z][A-Za-z\s,.'&-]+?)(?:,\s*(?:a|an|of|in)\s+)",
        # "This deed made by [GRANTOR]"
        r"deed made (?:this day )?by\s+([A-Z][A-Za-z\s,.'&-]+?)(?:,\s*(?:a|an|of|in)\s+)",
        # Traditional conveyance pattern
        r"([A-Z][A-Za-z\s,.'&-]+?),\s+(?:grantor|seller|assignor|lessor)",
        # Between "GRANTOR:" and a terminating pattern
        r"grantor[:\s]+([A-Z][A-Za-z\s,.'&-]+?)(?:\n|,\s*grantee)",
    ]

    # Patterns for marital status
    MARITAL_STATUS_PATTERNS = [
        r"(?:a\s+)?(married (?:man|woman))",
        r"(?:a\s+)?(single (?:man|woman))",
        r"(?:a\s+)?(widow(?:er)?)",
        r"(?:an?\s+)?(unmarried (?:man|woman))",
    ]

    # Patterns for corporate entities
    CORPORATE_PATTERNS = [
        r"(?:,\s+)?(?:a|an)\s+(corporation|inc\.|incorporated|llc|l\.l\.c\.|limited liability company)",
        r"(?:,\s+)?(?:a|an)\s+([A-Z][a-z]+)\s+(corporation|company)",
    ]

    def __init__(self):
        self.rules_used = []
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns"""
        self.compiled_grantor_patterns = [
            re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.GRANTOR_PATTERNS
        ]
        self.compiled_marital_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.MARITAL_STATUS_PATTERNS
        ]
        self.compiled_corporate_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.CORPORATE_PATTERNS
        ]

    async def extract(self, text: str) -> List[Grantor]:
        """
        Extract grantors from text

        Args:
            text: Document text

        Returns:
            List of Grantor objects
        """
        self.rules_used = []
        grantors = []
        seen_names = set()

        # Try each pattern
        for idx, pattern in enumerate(self.compiled_grantor_patterns):
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

                # Extract marital status
                marital_status = self._extract_marital_status(text, name)

                # Create grantor
                grantor = Grantor(
                    id=str(uuid.uuid4()),
                    name=name,
                    normalized_name=normalized_name,
                    entity_type=entity_type,
                    confidence=0.8 if idx == 0 else 0.7,  # First pattern is most reliable
                    source_text=match.group(0),
                    marital_status=marital_status,
                    metadata={
                        "pattern_index": idx,
                        "pattern": self.GRANTOR_PATTERNS[idx],
                    },
                )

                grantors.append(grantor)
                seen_names.add(name.lower())
                self.rules_used.append(f"grantor_pattern_{idx}")

        return grantors

    def _clean_name(self, name: str) -> str:
        """Clean extracted name"""
        # Remove common suffixes that might be captured
        name = re.sub(r",\s*(?:grantor|seller|assignor|lessor)\s*$", "", name, flags=re.IGNORECASE)
        # Remove excess whitespace
        name = " ".join(name.split())
        # Remove trailing punctuation
        name = name.rstrip(",.;:")
        return name

    def _normalize_name(self, name: str) -> str:
        """
        Normalize name for matching
        - Uppercase
        - Remove punctuation
        - Standardize common abbreviations
        """
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

        # Remove extra spaces
        normalized = " ".join(normalized.split())

        return normalized

    def _detect_entity_type(self, text: str, name: str) -> EntityType:
        """Detect entity type (person, corporation, LLC, etc.)"""
        name_lower = name.lower()

        # Check for corporate indicators
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

        # Check for trust
        if "trust" in name_lower:
            return EntityType.TRUST

        # Check for estate
        if "estate" in name_lower:
            return EntityType.ESTATE

        # Default to person
        return EntityType.PERSON

    def _extract_marital_status(self, text: str, name: str) -> str:
        """Extract marital status if present"""
        # Look for marital status near the name
        name_pos = text.lower().find(name.lower())
        if name_pos == -1:
            return None

        # Get context around name
        context_start = max(0, name_pos - 50)
        context_end = min(len(text), name_pos + len(name) + 100)
        context = text[context_start:context_end]

        # Check marital status patterns
        for pattern in self.compiled_marital_patterns:
            match = pattern.search(context)
            if match:
                return match.group(1)

        return None

    def get_rules_used(self) -> List[str]:
        """Get list of rules used in extraction"""
        return self.rules_used
