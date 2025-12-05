"""
Depth clause extractor - extracts depth limitations
"""

import re
import uuid
from typing import List, Optional

from ..models.entity import DepthClause


class DepthClauseExtractor:
    """
    Extracts depth clauses from mineral documents
    """

    # Depth clause patterns
    DEPTH_PATTERNS = [
        # "from surface to 5000 feet"
        r"from\s+(?:the\s+)?surface\s+(?:down\s+)?to\s+(\d+(?:,\d+)?)\s*feet",
        # "from 1000 feet to 5000 feet"
        r"from\s+(\d+(?:,\d+)?)\s*feet\s+to\s+(\d+(?:,\d+)?)\s*feet",
        # "down to the base of the [Formation]"
        r"(?:down\s+)?to\s+the\s+(?:base|top)\s+of\s+the\s+([A-Z][A-Za-z\s]+(?:Formation|Sand|Shale|Limestone))",
        # "from surface to the [Formation]"
        r"from\s+(?:the\s+)?surface\s+to\s+the\s+(?:base|top)\s+of\s+the\s+([A-Z][A-Za-z\s]+(?:Formation|Sand|Shale))",
        # "all depths" or "all strata"
        r"(all\s+depths|all\s+strata|all\s+formations)",
        # Depth limitation format: "Depths: 0-5000 ft"
        r"depths?:\s*(\d+(?:,\d+)?)\s*-\s*(\d+(?:,\d+)?)\s*(?:ft|feet)",
    ]

    def __init__(self):
        self.rules_used = []
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns"""
        self.compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.DEPTH_PATTERNS
        ]

    async def extract(self, text: str) -> List[DepthClause]:
        """
        Extract depth clauses from text

        Args:
            text: Document text

        Returns:
            List of DepthClause objects
        """
        self.rules_used = []
        clauses = []
        seen = set()

        for idx, pattern in enumerate(self.compiled_patterns):
            matches = pattern.finditer(text)
            for match in matches:
                raw_text = match.group(0)

                # Skip duplicates
                if raw_text.lower() in seen:
                    continue

                # Parse the depth clause
                from_depth, to_depth, formation = self._parse_depth(match, idx)

                # Determine depth type
                depth_type = "feet_from_surface"
                if formation:
                    depth_type = "formation"

                clause = DepthClause(
                    id=str(uuid.uuid4()),
                    raw_text=raw_text,
                    from_depth=from_depth,
                    to_depth=to_depth,
                    formation_name=formation,
                    depth_type=depth_type,
                    confidence=0.85,
                )

                clauses.append(clause)
                seen.add(raw_text.lower())
                self.rules_used.append(f"depth_clause_pattern_{idx}")

        return clauses

    def _parse_depth(self, match: re.Match, pattern_idx: int) -> tuple:
        """
        Parse depth information from match

        Returns:
            Tuple of (from_depth, to_depth, formation_name)
        """
        groups = match.groups()

        # Pattern-specific parsing
        if pattern_idx == 0:
            # "from surface to 5000 feet"
            from_depth = 0
            to_depth = self._parse_depth_number(groups[0])
            formation = None
        elif pattern_idx == 1:
            # "from 1000 feet to 5000 feet"
            from_depth = self._parse_depth_number(groups[0])
            to_depth = self._parse_depth_number(groups[1])
            formation = None
        elif pattern_idx == 2:
            # "to the base of the Formation"
            from_depth = None
            to_depth = None
            formation = groups[0].strip()
        elif pattern_idx == 3:
            # "from surface to the Formation"
            from_depth = 0
            to_depth = None
            formation = groups[0].strip()
        elif pattern_idx == 4:
            # "all depths"
            from_depth = 0
            to_depth = None
            formation = "all depths"
        elif pattern_idx == 5:
            # "Depths: 0-5000 ft"
            from_depth = self._parse_depth_number(groups[0])
            to_depth = self._parse_depth_number(groups[1])
            formation = None
        else:
            from_depth = None
            to_depth = None
            formation = None

        return from_depth, to_depth, formation

    def _parse_depth_number(self, depth_str: str) -> Optional[int]:
        """Parse depth number, removing commas"""
        if not depth_str:
            return None
        # Remove commas
        depth_str = depth_str.replace(",", "")
        try:
            return int(depth_str)
        except ValueError:
            return None

    def get_rules_used(self) -> List[str]:
        """Get list of rules used"""
        return self.rules_used
