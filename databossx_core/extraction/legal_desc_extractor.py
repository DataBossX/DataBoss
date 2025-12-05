"""
Legal description extractor - parses S-T-R, aliquot parts, lots
"""

import re
import uuid
from typing import List, Optional
from decimal import Decimal

from ..models.entity import LegalDescription, AliquotPart


class LegalDescriptionExtractor:
    """
    Extracts and parses legal descriptions from land documents
    Handles: Section-Township-Range (STR), aliquot parts, lots
    """

    # Patterns for Section-Township-Range
    STR_PATTERNS = [
        # "Section 12, Township 5 North, Range 68 West"
        r"Section\s+(\d+),\s*Township\s+(\d+)\s+(North|South|N\.?|S\.?),\s*Range\s+(\d+)\s+(East|West|E\.?|W\.?)",
        # "S12, T5N, R68W"
        r"S(?:ec(?:tion)?\.?\s*)?(\d+),?\s*T(?:ownship|wp|wn)?\.?\s*(\d+)\s*(N|S)\.?,?\s*R(?:ange)?\.?\s*(\d+)\s*(E|W)\.?",
        # More compact: "S12-T5N-R68W"
        r"S(?:ec)?\.?\s*(\d+)[-\s]*T\.?\s*(\d+)\s*(N|S)[-\s]*R\.?\s*(\d+)\s*(E|W)",
    ]

    # Patterns for aliquot parts
    ALIQUOT_PATTERNS = [
        # "NE 1/4 of SW 1/4"
        r"\b([NSEW]{1,2})\s*1?/?4\s+of\s+([NSEW]{1,2})\s*1?/?4",
        # "NE1/4 SW1/4"
        r"\b([NSEW]{1,2})1?/?4\s+([NSEW]{1,2})1?/?4",
        # Simple "NE 1/4" or "NE1/4"
        r"\b([NSEW]{1,2})\s*1?/?4",
        # "Northeast Quarter"
        r"\b(North|South|East|West)(?:east|west)?\s+(?:Quarter|One-Fourth)",
    ]

    # Lot patterns
    LOT_PATTERNS = [
        r"Lots?\s+(\d+(?:\s*(?:and|&|,)\s*\d+)*)",
        r"Lot\s+No\.?\s*(\d+)",
    ]

    # Meridian patterns
    MERIDIAN_PATTERNS = [
        r"(\d+(?:st|nd|rd|th)?\s+(?:Principal\s+)?Meridian)",
        r"([A-Z][a-z]+\s+Meridian)",
    ]

    def __init__(self):
        self.rules_used = []
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns"""
        self.compiled_str_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.STR_PATTERNS
        ]
        self.compiled_aliquot_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.ALIQUOT_PATTERNS
        ]
        self.compiled_lot_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.LOT_PATTERNS
        ]
        self.compiled_meridian_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.MERIDIAN_PATTERNS
        ]

    async def extract(self, text: str) -> List[LegalDescription]:
        """
        Extract legal descriptions from text

        Args:
            text: Document text

        Returns:
            List of LegalDescription objects
        """
        self.rules_used = []
        descriptions = []

        # Find all potential legal description sections
        desc_sections = self._find_legal_desc_sections(text)

        for section_text in desc_sections:
            # Extract STR
            section, township, range_val, meridian = self._extract_str(section_text)

            # Extract aliquot parts
            aliquots = self._extract_aliquots(section_text)

            # Extract lots
            lots = self._extract_lots(section_text)

            # Extract county and state
            county, state = self._extract_location(section_text)

            # Calculate acres from aliquots
            acres = self._calculate_acres(aliquots)

            # Only create if we have minimum required info
            if section or lots or aliquots:
                description = LegalDescription(
                    id=str(uuid.uuid4()),
                    raw_text=section_text.strip(),
                    section=section,
                    township=township,
                    range=range_val,
                    meridian=meridian,
                    county=county,
                    state=state,
                    aliquot_parts=aliquots,
                    lots=lots,
                    acres=acres,
                    confidence=0.8 if section and township else 0.6,
                    metadata={"extraction_method": "pattern_matching"},
                )
                descriptions.append(description)
                self.rules_used.append("legal_desc_str")

        return descriptions

    def _find_legal_desc_sections(self, text: str) -> List[str]:
        """Find sections of text that likely contain legal descriptions"""
        # Look for "legal description" header
        sections = []

        # Pattern: "LEGAL DESCRIPTION:" followed by text
        pattern = re.compile(
            r"(?:LEGAL DESCRIPTION|PROPERTY DESCRIPTION|LAND DESCRIPTION)[:\s]+([^\n]{10,}(?:\n[^\n]{10,}){0,10})",
            re.IGNORECASE | re.MULTILINE,
        )

        matches = pattern.finditer(text)
        for match in matches:
            sections.append(match.group(1))

        # Also look for STR patterns anywhere in the document
        for str_pattern in self.compiled_str_patterns:
            matches = str_pattern.finditer(text)
            for match in matches:
                # Get surrounding context
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 200)
                context = text[start:end]
                if context not in sections:
                    sections.append(context)

        return sections if sections else [text[:2000]]  # Fallback to first 2000 chars

    def _extract_str(self, text: str) -> tuple:
        """
        Extract Section-Township-Range

        Returns:
            Tuple of (section, township, range, meridian)
        """
        for pattern in self.compiled_str_patterns:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                section = groups[0]
                township = f"{groups[1]}{self._normalize_direction(groups[2])}"
                range_val = f"{groups[3]}{self._normalize_direction(groups[4])}"

                # Extract meridian if present
                meridian = self._extract_meridian(text)

                return section, township, range_val, meridian

        return None, None, None, None

    def _extract_aliquots(self, text: str) -> List[AliquotPart]:
        """Extract aliquot parts (e.g., NE 1/4, SW 1/4)"""
        aliquots = []
        seen = set()

        for pattern in self.compiled_aliquot_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                # Parse aliquot
                aliquot_text = match.group(0)

                # Normalize
                normalized = self._normalize_aliquot(aliquot_text)

                if normalized not in seen:
                    acres = self._aliquot_to_acres(normalized)
                    aliquots.append(
                        AliquotPart(
                            part=normalized,
                            acres=acres,
                        )
                    )
                    seen.add(normalized)

        return aliquots

    def _extract_lots(self, text: str) -> List[str]:
        """Extract lot numbers"""
        lots = []

        for pattern in self.compiled_lot_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                lot_text = match.group(1)
                # Parse individual lots (handle "1, 2, and 3" or "1 and 2")
                lot_numbers = re.findall(r"\d+", lot_text)
                lots.extend(lot_numbers)

        return list(set(lots))  # Remove duplicates

    def _extract_meridian(self, text: str) -> Optional[str]:
        """Extract meridian reference"""
        for pattern in self.compiled_meridian_patterns:
            match = pattern.search(text)
            if match:
                return match.group(1)
        return None

    def _extract_location(self, text: str) -> tuple:
        """Extract county and state"""
        county = None
        state = None

        # County pattern
        county_pattern = re.compile(r"([A-Z][a-z]+)\s+County", re.IGNORECASE)
        county_match = county_pattern.search(text)
        if county_match:
            county = county_match.group(1)

        # State pattern
        state_pattern = re.compile(
            r"State of\s+([A-Z][a-z]+)|,\s+([A-Z]{2})\s*$",
            re.IGNORECASE | re.MULTILINE,
        )
        state_match = state_pattern.search(text)
        if state_match:
            state = state_match.group(1) or state_match.group(2)

        return county, state

    def _normalize_direction(self, direction: str) -> str:
        """Normalize direction to single letter"""
        direction = direction.upper()
        if direction.startswith("N"):
            return "N"
        elif direction.startswith("S"):
            return "S"
        elif direction.startswith("E"):
            return "E"
        elif direction.startswith("W"):
            return "W"
        return direction

    def _normalize_aliquot(self, aliquot_text: str) -> str:
        """Normalize aliquot part to standard format"""
        # Extract direction letters
        directions = re.findall(r"[NSEW]{1,2}", aliquot_text, re.IGNORECASE)
        directions = [d.upper() for d in directions]

        if len(directions) == 2:
            return f"{directions[0]}1/4 of {directions[1]}1/4"
        elif len(directions) == 1:
            return f"{directions[0]}1/4"

        return aliquot_text

    def _aliquot_to_acres(self, aliquot: str) -> Optional[Decimal]:
        """Calculate acres from aliquot part (assuming standard 640-acre section)"""
        # Count the number of 1/4 divisions
        quarter_count = aliquot.count("1/4")

        if quarter_count == 0:
            return None

        # Each 1/4 divides by 4
        acres = Decimal(640)
        for _ in range(quarter_count):
            acres = acres / Decimal(4)

        return acres

    def _calculate_acres(self, aliquots: List[AliquotPart]) -> Optional[Decimal]:
        """Calculate total acres from aliquot parts"""
        if not aliquots:
            return None

        total = Decimal(0)
        for aliquot in aliquots:
            if aliquot.acres:
                total += aliquot.acres

        return total if total > 0 else None

    def get_rules_used(self) -> List[str]:
        """Get list of rules used"""
        return self.rules_used
