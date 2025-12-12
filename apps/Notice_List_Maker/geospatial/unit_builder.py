"""
Unit polygon builder from tract descriptions.
Converts legal descriptions (STR, aliquots) into geometric polygons.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.ops import unary_union
import re

logger = logging.getLogger(__name__)


@dataclass
class PLSSCoordinate:
    """Public Land Survey System coordinate."""
    township: int
    township_direction: str  # N or S
    range: int
    range_direction: str     # E or W
    section: int
    meridian: Optional[str] = None

    def __str__(self):
        return f"T{self.township}{self.township_direction} R{self.range}{self.range_direction} Sec {self.section}"


@dataclass
class Tract:
    """Individual tract with geometry and metadata."""
    tract_id: str
    legal_description: str
    geometry: Optional[Polygon] = None
    plss: Optional[PLSSCoordinate] = None
    aliquots: Optional[List[str]] = None
    gross_acres: Optional[float] = None
    net_acres: Optional[float] = None
    confidence_score: float = 0.0
    geometry_method: str = "unknown"


class UnitBuilder:
    """Builds unit polygon from tract descriptions."""

    # Standard section size in miles
    SECTION_SIZE_MILES = 1.0
    MILES_TO_FEET = 5280.0

    def __init__(self, base_meridian: str = "6PM"):
        """
        Initialize unit builder.

        Args:
            base_meridian: Base meridian for coordinate system (e.g., "6PM" for 6th Principal Meridian)
        """
        self.base_meridian = base_meridian
        self.tracts: List[Tract] = []

    def parse_legal_description(self, legal_desc: str) -> Optional[PLSSCoordinate]:
        """
        Parse legal description into PLSS coordinates.

        Args:
            legal_desc: Legal description string (e.g., "T1N R68W Sec 16")

        Returns:
            PLSSCoordinate if successfully parsed, None otherwise
        """
        # Pattern: T{num}{N|S} R{num}{E|W} Sec {num}
        pattern = r'T(\d+)([NS])\s+R(\d+)([EW])\s+Sec\.?\s+(\d+)'
        match = re.search(pattern, legal_desc, re.IGNORECASE)

        if match:
            return PLSSCoordinate(
                township=int(match.group(1)),
                township_direction=match.group(2).upper(),
                range=int(match.group(3)),
                range_direction=match.group(4).upper(),
                section=int(match.group(5)),
                meridian=self.base_meridian
            )

        logger.warning(f"Could not parse legal description: {legal_desc}")
        return None

    def parse_aliquots(self, legal_desc: str) -> List[str]:
        """
        Extract aliquot parts from legal description.

        Args:
            legal_desc: Legal description (e.g., "NW1/4 NE1/4")

        Returns:
            List of aliquot parts
        """
        # Common aliquot patterns: NW1/4, SE/4, N2, etc.
        aliquot_pattern = r'[NSEW][NSEW]?(?:1/[24]|/[24]|2)?'
        aliquots = re.findall(aliquot_pattern, legal_desc, re.IGNORECASE)
        return [a.upper() for a in aliquots]

    def plss_to_coords(self, plss: PLSSCoordinate) -> Tuple[float, float]:
        """
        Convert PLSS coordinates to approximate lat/lon.

        This is a simplified conversion. Production systems should use
        proper PLSS grid shapefiles for accurate coordinates.

        Args:
            plss: PLSS coordinate

        Returns:
            (longitude, latitude) tuple
        """
        # Approximate conversion - this should be replaced with real PLSS grid lookup
        # Base point (arbitrary reference)
        base_lon = -104.0  # Colorado reference
        base_lat = 40.0

        # Calculate offsets
        range_offset = plss.range if plss.range_direction == 'W' else -plss.range
        township_offset = plss.township if plss.township_direction == 'N' else -plss.township

        # Approximate degrees per township/range (1 mile ≈ 0.0145 degrees at 40° lat)
        deg_per_township = 6 * 0.0145  # 6 miles per township
        deg_per_range = 6 * 0.0145

        lon = base_lon - (range_offset * deg_per_range)
        lat = base_lat + (township_offset * deg_per_township)

        # Add section offset within township (sections are ~1 mile square)
        section_row = (plss.section - 1) // 6
        section_col = (plss.section - 1) % 6

        lat += section_row * 0.0145
        lon += section_col * 0.0145

        return (lon, lat)

    def build_section_polygon(self, plss: PLSSCoordinate) -> Polygon:
        """
        Build polygon for a full section.

        Args:
            plss: PLSS coordinate

        Returns:
            Polygon representing the section
        """
        center_lon, center_lat = self.plss_to_coords(plss)

        # Section is approximately 1 mile square
        half_mile_lat = 0.0145 / 2  # Approximate
        half_mile_lon = 0.0145 / 2

        return Polygon([
            (center_lon - half_mile_lon, center_lat - half_mile_lat),
            (center_lon + half_mile_lon, center_lat - half_mile_lat),
            (center_lon + half_mile_lon, center_lat + half_mile_lat),
            (center_lon - half_mile_lon, center_lat + half_mile_lat),
        ])

    def build_aliquot_polygon(self, section_poly: Polygon, aliquots: List[str]) -> Polygon:
        """
        Build polygon for aliquot parts within a section.

        Args:
            section_poly: Full section polygon
            aliquots: List of aliquot descriptions (e.g., ["NW", "1/4"])

        Returns:
            Polygon for the aliquot part
        """
        if not aliquots:
            return section_poly

        # Simplified aliquot subdivision - production version needs proper logic
        # For now, use centroid as approximation
        centroid = section_poly.centroid
        bounds = section_poly.bounds

        # This is a placeholder - proper implementation would subdivide section
        # based on aliquot parts (quarters, halves, etc.)
        return section_poly

    def build_tract_geometry(self, tract: Tract, method: str = "polygon") -> Tract:
        """
        Build geometry for a tract.

        Args:
            tract: Tract object
            method: "polygon", "centroid", or "str_grid"

        Returns:
            Tract with geometry populated
        """
        if not tract.plss:
            logger.warning(f"No PLSS coordinate for tract {tract.tract_id}")
            tract.geometry_method = "failed"
            tract.confidence_score = 0.0
            return tract

        try:
            if method == "polygon":
                section_poly = self.build_section_polygon(tract.plss)
                if tract.aliquots:
                    tract.geometry = self.build_aliquot_polygon(section_poly, tract.aliquots)
                else:
                    tract.geometry = section_poly
                tract.geometry_method = "polygon"
                tract.confidence_score = 90.0

            elif method == "centroid":
                center_lon, center_lat = self.plss_to_coords(tract.plss)
                # Create small buffer around centroid
                tract.geometry = Point(center_lon, center_lat).buffer(0.01)
                tract.geometry_method = "centroid"
                tract.confidence_score = 70.0

            else:  # str_grid
                # Grid-based approximation
                section_poly = self.build_section_polygon(tract.plss)
                tract.geometry = section_poly
                tract.geometry_method = "str_grid"
                tract.confidence_score = 50.0

        except Exception as e:
            logger.error(f"Failed to build geometry for tract {tract.tract_id}: {e}")
            tract.geometry_method = "failed"
            tract.confidence_score = 0.0

        return tract

    def add_tract(self, tract_id: str, legal_description: str,
                  gross_acres: Optional[float] = None,
                  net_acres: Optional[float] = None) -> Tract:
        """
        Add a tract to the unit.

        Args:
            tract_id: Unique identifier for tract
            legal_description: Legal description string
            gross_acres: Gross acreage
            net_acres: Net acreage

        Returns:
            Created Tract object
        """
        plss = self.parse_legal_description(legal_description)
        aliquots = self.parse_aliquots(legal_description)

        tract = Tract(
            tract_id=tract_id,
            legal_description=legal_description,
            plss=plss,
            aliquots=aliquots,
            gross_acres=gross_acres,
            net_acres=net_acres
        )

        # Try to build geometry with fallback methods
        for method in ["polygon", "centroid", "str_grid"]:
            tract = self.build_tract_geometry(tract, method)
            if tract.geometry is not None:
                break

        self.tracts.append(tract)
        logger.info(f"Added tract {tract_id} with {tract.geometry_method} method")

        return tract

    def build_unit_polygon(self) -> Optional[Polygon]:
        """
        Build combined unit polygon from all tracts.

        Returns:
            Polygon representing the entire unit
        """
        valid_geometries = [t.geometry for t in self.tracts if t.geometry is not None]

        if not valid_geometries:
            logger.error("No valid geometries to build unit polygon")
            return None

        try:
            unit_polygon = unary_union(valid_geometries)
            logger.info(f"Built unit polygon from {len(valid_geometries)} tracts")
            return unit_polygon
        except Exception as e:
            logger.error(f"Failed to build unit polygon: {e}")
            return None

    def get_unit_summary(self) -> Dict:
        """Get summary statistics for the unit."""
        total_tracts = len(self.tracts)
        valid_geoms = sum(1 for t in self.tracts if t.geometry is not None)
        avg_confidence = sum(t.confidence_score for t in self.tracts) / total_tracts if total_tracts > 0 else 0

        return {
            "total_tracts": total_tracts,
            "valid_geometries": valid_geoms,
            "average_confidence": avg_confidence,
            "methods_used": {
                "polygon": sum(1 for t in self.tracts if t.geometry_method == "polygon"),
                "centroid": sum(1 for t in self.tracts if t.geometry_method == "centroid"),
                "str_grid": sum(1 for t in self.tracts if t.geometry_method == "str_grid"),
                "failed": sum(1 for t in self.tracts if t.geometry_method == "failed"),
            }
        }
