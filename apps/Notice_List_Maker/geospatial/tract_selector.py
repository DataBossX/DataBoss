"""
Tract selector - determines which tracts are unit vs offset.
Critical: Offset tracts are determined by TRUE geometric intersection,
not by section adjacency.
"""

import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from shapely.geometry import Polygon, Point
from enum import Enum

logger = logging.getLogger(__name__)


class TractType(Enum):
    """Classification of tract types."""
    UNIT = "UNIT"
    OFFSET = "OFFSET"
    UNKNOWN = "UNKNOWN"


@dataclass
class ClassifiedTract:
    """Tract with classification."""
    tract_id: str
    tract_type: TractType
    legal_description: str
    geometry: Optional[Polygon]
    offset_method: str  # How offset determination was made
    confidence_score: float
    distance_to_unit_miles: Optional[float] = None
    intersection_area: Optional[float] = None


class TractSelector:
    """Selects and classifies tracts as unit or offset."""

    def __init__(self, unit_polygon: Polygon, offset_polygon: Polygon):
        """
        Initialize tract selector.

        Args:
            unit_polygon: Unit boundary polygon
            offset_polygon: Offset zone polygon (buffer around unit)
        """
        self.unit_polygon = unit_polygon
        self.offset_polygon = offset_polygon

    def classify_tract(self, tract_id: str, legal_description: str,
                       geometry: Optional[Polygon]) -> ClassifiedTract:
        """
        Classify a tract as UNIT, OFFSET, or UNKNOWN.

        Args:
            tract_id: Tract identifier
            legal_description: Legal description
            geometry: Tract geometry

        Returns:
            ClassifiedTract with determination
        """
        if geometry is None:
            logger.warning(f"Tract {tract_id} has no geometry - marking UNKNOWN")
            return ClassifiedTract(
                tract_id=tract_id,
                tract_type=TractType.UNKNOWN,
                legal_description=legal_description,
                geometry=None,
                offset_method="no_geometry",
                confidence_score=0.0
            )

        # Check if tract intersects unit polygon
        if self.unit_polygon.intersects(geometry):
            intersection_area = self.unit_polygon.intersection(geometry).area

            return ClassifiedTract(
                tract_id=tract_id,
                tract_type=TractType.UNIT,
                legal_description=legal_description,
                geometry=geometry,
                offset_method="polygon_intersection",
                confidence_score=95.0,
                intersection_area=intersection_area
            )

        # Check if tract intersects offset polygon
        if self.offset_polygon.intersects(geometry):
            intersection_area = self.offset_polygon.intersection(geometry).area
            distance = self.calculate_distance_to_unit(geometry)

            return ClassifiedTract(
                tract_id=tract_id,
                tract_type=TractType.OFFSET,
                legal_description=legal_description,
                geometry=geometry,
                offset_method="polygon_intersection",
                confidence_score=90.0,
                distance_to_unit_miles=distance,
                intersection_area=intersection_area
            )

        # Fallback: check centroid distance
        centroid_classification = self.classify_by_centroid(
            tract_id, legal_description, geometry
        )

        return centroid_classification

    def classify_by_centroid(self, tract_id: str, legal_description: str,
                            geometry: Polygon) -> ClassifiedTract:
        """
        Classify tract based on centroid distance (fallback method).

        Args:
            tract_id: Tract identifier
            legal_description: Legal description
            geometry: Tract geometry

        Returns:
            ClassifiedTract
        """
        centroid = geometry.centroid
        distance = self.calculate_distance_to_unit(geometry)

        # If centroid is in unit
        if self.unit_polygon.contains(centroid):
            return ClassifiedTract(
                tract_id=tract_id,
                tract_type=TractType.UNIT,
                legal_description=legal_description,
                geometry=geometry,
                offset_method="centroid_in_unit",
                confidence_score=70.0
            )

        # If centroid is in offset zone
        if self.offset_polygon.contains(centroid):
            return ClassifiedTract(
                tract_id=tract_id,
                tract_type=TractType.OFFSET,
                legal_description=legal_description,
                geometry=geometry,
                offset_method="centroid_in_offset",
                confidence_score=65.0,
                distance_to_unit_miles=distance
            )

        # Outside both - mark as UNKNOWN
        return ClassifiedTract(
            tract_id=tract_id,
            tract_type=TractType.UNKNOWN,
            legal_description=legal_description,
            geometry=geometry,
            offset_method="outside_buffer",
            confidence_score=30.0,
            distance_to_unit_miles=distance
        )

    def calculate_distance_to_unit(self, geometry: Polygon) -> float:
        """
        Calculate distance from tract to unit boundary.

        Args:
            geometry: Tract geometry

        Returns:
            Distance in miles (approximate)
        """
        try:
            # Calculate distance between boundaries
            distance_degrees = self.unit_polygon.distance(geometry)

            # Approximate conversion to miles (rough)
            miles_per_degree = 69.0  # At mid-latitudes
            distance_miles = distance_degrees * miles_per_degree

            return round(distance_miles, 2)
        except Exception as e:
            logger.error(f"Failed to calculate distance: {e}")
            return 999.0

    def classify_batch(self, tracts: List[Dict]) -> Tuple[List[ClassifiedTract], List[ClassifiedTract]]:
        """
        Classify a batch of tracts.

        Args:
            tracts: List of tract dictionaries with keys: tract_id, legal_description, geometry

        Returns:
            Tuple of (unit_tracts, offset_tracts)
        """
        unit_tracts = []
        offset_tracts = []
        unknown_tracts = []

        for tract in tracts:
            classified = self.classify_tract(
                tract_id=tract.get("tract_id"),
                legal_description=tract.get("legal_description"),
                geometry=tract.get("geometry")
            )

            if classified.tract_type == TractType.UNIT:
                unit_tracts.append(classified)
            elif classified.tract_type == TractType.OFFSET:
                offset_tracts.append(classified)
            else:
                unknown_tracts.append(classified)

        logger.info(f"Classified {len(unit_tracts)} UNIT, {len(offset_tracts)} OFFSET, "
                   f"{len(unknown_tracts)} UNKNOWN tracts")

        # Log unknown tracts as warnings
        for tract in unknown_tracts:
            logger.warning(f"Tract {tract.tract_id} classified as UNKNOWN: {tract.offset_method}")

        return unit_tracts, offset_tracts

    def get_classification_summary(self, classified_tracts: List[ClassifiedTract]) -> Dict:
        """
        Get summary statistics for classified tracts.

        Args:
            classified_tracts: List of classified tracts

        Returns:
            Summary statistics dictionary
        """
        total = len(classified_tracts)

        by_type = {
            TractType.UNIT: 0,
            TractType.OFFSET: 0,
            TractType.UNKNOWN: 0
        }

        by_method = {}
        confidence_scores = []

        for tract in classified_tracts:
            by_type[tract.tract_type] += 1
            by_method[tract.offset_method] = by_method.get(tract.offset_method, 0) + 1
            confidence_scores.append(tract.confidence_score)

        avg_confidence = sum(confidence_scores) / total if total > 0 else 0

        return {
            "total_tracts": total,
            "by_type": {k.value: v for k, v in by_type.items()},
            "by_method": by_method,
            "average_confidence": round(avg_confidence, 2),
            "min_confidence": min(confidence_scores) if confidence_scores else 0,
            "max_confidence": max(confidence_scores) if confidence_scores else 0,
        }
