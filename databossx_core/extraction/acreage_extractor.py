"""
Acreage information extractor
"""

import re
from typing import Optional, List
from decimal import Decimal

from ..models.entity import AcreageInfo


class AcreageExtractor:
    """
    Extracts acreage information from documents
    """

    # Acreage patterns
    ACREAGE_PATTERNS = [
        # "containing 160 acres"
        r"containing\s+(\d+(?:\.\d+)?)\s+acres?",
        # "160 acres, more or less"
        r"(\d+(?:\.\d+)?)\s+acres?,?\s+more or less",
        # "Total acres: 160"
        r"total\s+acres?:\s*(\d+(?:\.\d+)?)",
        # "Gross acres: 160.5"
        r"gross\s+acres?:\s*(\d+(?:\.\d+)?)",
        # "Net acres: 40.25"
        r"net\s+acres?:\s*(\d+(?:\.\d+)?)",
        # Simple "160 acres"
        r"(\d+(?:\.\d+)?)\s+acres?",
    ]

    def __init__(self):
        self.rules_used = []
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns"""
        self.compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.ACREAGE_PATTERNS
        ]

    async def extract(self, text: str) -> Optional[AcreageInfo]:
        """
        Extract acreage information from text

        Args:
            text: Document text

        Returns:
            AcreageInfo object or None
        """
        self.rules_used = []

        total_acres = None
        gross_acres = None
        net_acres = None
        source_text = ""

        # Look for specific patterns
        for idx, pattern in enumerate(self.compiled_patterns):
            matches = pattern.finditer(text)
            for match in matches:
                acres_str = match.group(1)
                acres = Decimal(acres_str)
                source = match.group(0)

                # Determine what type of acres this is
                source_lower = source.lower()

                if "gross" in source_lower:
                    gross_acres = acres
                    source_text = source
                elif "net" in source_lower:
                    net_acres = acres
                    source_text = source
                elif "total" in source_lower or "containing" in source_lower:
                    total_acres = acres
                    source_text = source
                elif not total_acres:
                    # Default to total acres if not specified
                    total_acres = acres
                    source_text = source

                self.rules_used.append(f"acreage_pattern_{idx}")

        # Only return if we found something
        if total_acres or gross_acres or net_acres:
            return AcreageInfo(
                total_acres=total_acres,
                gross_acres=gross_acres,
                net_acres=net_acres,
                source_text=source_text,
                confidence=0.85,
            )

        return None

    def get_rules_used(self) -> List[str]:
        """Get list of rules used"""
        return self.rules_used
