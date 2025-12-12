"""
Buffer engine for creating offset areas around unit polygons.
Critical: This creates TRUE geometric buffers, not "neighboring sections".
"""

import logging
from typing import Optional, List, Dict
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
import math

logger = logging.getLogger(__name__)


class BufferEngine:
    """Creates geometric buffers around unit polygons."""

    # Constants
    MILES_TO_DEGREES_AT_40N = 0.0145  # Approximate at 40° latitude
    FEET_TO_MILES = 1.0 / 5280.0

    def __init__(self, buffer_distance_miles: float = 0.5):
        """
        Initialize buffer engine.

        Args:
            buffer_distance_miles: Buffer distance in miles (default 0.5 for offset wells)
        """
        self.buffer_distance_miles = buffer_distance_miles
        self.buffer_distance_degrees = buffer_distance_miles * self.MILES_TO_DEGREES_AT_40N

    def create_buffer(self, geometry: Polygon, method: str = "simple") -> Optional[Polygon]:
        """
        Create buffer around geometry.

        Args:
            geometry: Input polygon (unit boundary)
            method: Buffer method - "simple" or "precise"

        Returns:
            Buffered polygon or None if failed
        """
        if geometry is None:
            logger.error("Cannot create buffer from None geometry")
            return None

        try:
            if method == "simple":
                # Simple buffer using degrees
                buffered = geometry.buffer(self.buffer_distance_degrees)

            elif method == "precise":
                # More precise buffer accounting for projection
                # In production, would use proper projected CRS
                buffered = geometry.buffer(self.buffer_distance_degrees)

            else:
                logger.warning(f"Unknown buffer method: {method}, using simple")
                buffered = geometry.buffer(self.buffer_distance_degrees)

            logger.info(f"Created {self.buffer_distance_miles}-mile buffer using {method} method")
            return buffered

        except Exception as e:
            logger.error(f"Failed to create buffer: {e}")
            return None

    def get_offset_zone(self, unit_polygon: Polygon, exclude_unit: bool = True) -> Optional[Polygon]:
        """
        Get offset zone (buffer minus unit polygon).

        Args:
            unit_polygon: Unit boundary polygon
            exclude_unit: If True, subtract unit polygon from buffer

        Returns:
            Offset zone polygon
        """
        buffered = self.create_buffer(unit_polygon)

        if buffered is None:
            return None

        if exclude_unit:
            try:
                offset_zone = buffered.difference(unit_polygon)
                logger.info("Created offset zone (buffer - unit)")
                return offset_zone
            except Exception as e:
                logger.error(f"Failed to subtract unit from buffer: {e}")
                return buffered

        return buffered

    def calculate_buffer_stats(self, unit_polygon: Polygon, buffer_polygon: Polygon) -> Dict:
        """
        Calculate statistics about the buffer.

        Args:
            unit_polygon: Original unit polygon
            buffer_polygon: Buffered polygon

        Returns:
            Dictionary with buffer statistics
        """
        try:
            # Approximate areas (these are in square degrees, would need proper projection for acres)
            unit_area = unit_polygon.area
            buffer_area = buffer_polygon.area
            offset_area = buffer_area - unit_area

            # Approximate conversion to acres (very rough)
            # 1 square degree ≈ 4,900,000,000 square feet at equator
            # At 40°N latitude, adjust by cos(40°)
            sq_deg_to_acres = 4900000000 * math.cos(math.radians(40)) / 43560

            return {
                "unit_area_sq_deg": unit_area,
                "buffer_area_sq_deg": buffer_area,
                "offset_area_sq_deg": offset_area,
                "unit_area_acres": unit_area * sq_deg_to_acres,
                "buffer_area_acres": buffer_area * sq_deg_to_acres,
                "offset_area_acres": offset_area * sq_deg_to_acres,
                "buffer_distance_miles": self.buffer_distance_miles,
            }
        except Exception as e:
            logger.error(f"Failed to calculate buffer stats: {e}")
            return {}

    def create_multi_distance_buffers(self, geometry: Polygon,
                                     distances_miles: List[float]) -> Dict[float, Polygon]:
        """
        Create multiple buffers at different distances.

        Args:
            geometry: Input polygon
            distances_miles: List of buffer distances in miles

        Returns:
            Dictionary mapping distance to buffered polygon
        """
        buffers = {}

        for distance in distances_miles:
            temp_engine = BufferEngine(buffer_distance_miles=distance)
            buffered = temp_engine.create_buffer(geometry)
            if buffered:
                buffers[distance] = buffered
                logger.info(f"Created {distance}-mile buffer")

        return buffers

    def validate_buffer(self, original: Polygon, buffered: Polygon) -> Dict[str, bool]:
        """
        Validate that buffer was created correctly.

        Args:
            original: Original polygon
            buffered: Buffered polygon

        Returns:
            Dictionary with validation results
        """
        checks = {
            "buffered_is_valid": buffered.is_valid if buffered else False,
            "buffered_is_larger": False,
            "original_contained": False,
        }

        if buffered and buffered.is_valid:
            checks["buffered_is_larger"] = buffered.area > original.area
            checks["original_contained"] = buffered.contains(original)

        all_passed = all(checks.values())
        checks["all_checks_passed"] = all_passed

        if not all_passed:
            logger.warning(f"Buffer validation failed: {checks}")

        return checks
