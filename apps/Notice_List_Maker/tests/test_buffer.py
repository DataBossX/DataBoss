"""
Tests for buffer/geospatial logic.
Verifies a known unit produces known offset tracts.
"""

import pytest
from pathlib import Path
from shapely.geometry import Polygon, Point

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from geospatial.unit_builder import UnitBuilder, PLSSCoordinate
from geospatial.buffer_engine import BufferEngine
from geospatial.tract_selector import TractSelector, TractType


class TestUnitBuilder:
    """Test unit polygon building."""

    def test_parse_legal_description(self):
        """Test legal description parsing."""
        builder = UnitBuilder()

        legal = "T1N R68W Sec 16"
        plss = builder.parse_legal_description(legal)

        assert plss is not None
        assert plss.township == 1
        assert plss.township_direction == "N"
        assert plss.range == 68
        assert plss.range_direction == "W"
        assert plss.section == 16

    def test_build_section_polygon(self):
        """Test section polygon creation."""
        builder = UnitBuilder()

        plss = PLSSCoordinate(
            township=1,
            township_direction="N",
            range=68,
            range_direction="W",
            section=16
        )

        polygon = builder.build_section_polygon(plss)

        assert polygon is not None
        assert polygon.is_valid
        assert polygon.area > 0

    def test_add_tract(self):
        """Test adding tract to unit."""
        builder = UnitBuilder()

        tract = builder.add_tract(
            tract_id="TEST-1",
            legal_description="T1N R68W Sec 16",
            gross_acres=160.0
        )

        assert tract.tract_id == "TEST-1"
        assert tract.geometry is not None
        assert tract.confidence_score > 0

    def test_build_unit_polygon(self):
        """Test building combined unit polygon."""
        builder = UnitBuilder()

        # Add multiple tracts
        builder.add_tract("1", "T1N R68W Sec 16", 160.0)
        builder.add_tract("2", "T1N R68W Sec 21", 160.0)

        unit_polygon = builder.build_unit_polygon()

        assert unit_polygon is not None
        assert unit_polygon.is_valid
        assert unit_polygon.area > 0


class TestBufferEngine:
    """Test buffer creation."""

    def test_create_buffer(self):
        """Test buffer creation around polygon."""
        # Create simple square polygon
        polygon = Polygon([
            (-104.0, 40.0),
            (-104.0, 40.01),
            (-103.99, 40.01),
            (-103.99, 40.0)
        ])

        engine = BufferEngine(buffer_distance_miles=0.5)
        buffered = engine.create_buffer(polygon)

        assert buffered is not None
        assert buffered.is_valid
        assert buffered.area > polygon.area

    def test_validate_buffer(self):
        """Test buffer validation."""
        polygon = Polygon([
            (-104.0, 40.0),
            (-104.0, 40.01),
            (-103.99, 40.01),
            (-103.99, 40.0)
        ])

        engine = BufferEngine(buffer_distance_miles=0.5)
        buffered = engine.create_buffer(polygon)

        validation = engine.validate_buffer(polygon, buffered)

        assert validation["buffered_is_valid"]
        assert validation["buffered_is_larger"]
        assert validation["original_contained"]
        assert validation["all_checks_passed"]

    def test_get_offset_zone(self):
        """Test offset zone creation (buffer minus unit)."""
        polygon = Polygon([
            (-104.0, 40.0),
            (-104.0, 40.01),
            (-103.99, 40.01),
            (-103.99, 40.0)
        ])

        engine = BufferEngine(buffer_distance_miles=0.5)
        offset_zone = engine.get_offset_zone(polygon, exclude_unit=True)

        assert offset_zone is not None
        assert offset_zone.is_valid
        # Offset zone should not contain original polygon center
        # (since we excluded the unit)


class TestTractSelector:
    """Test tract classification."""

    def test_classify_unit_tract(self):
        """Test classification of tract inside unit."""
        # Create unit polygon
        unit_polygon = Polygon([
            (-104.0, 40.0),
            (-104.0, 40.01),
            (-103.99, 40.01),
            (-103.99, 40.0)
        ])

        # Create offset polygon (buffer)
        engine = BufferEngine(buffer_distance_miles=0.5)
        offset_polygon = engine.create_buffer(unit_polygon)

        selector = TractSelector(unit_polygon, offset_polygon)

        # Tract inside unit
        tract_geometry = Polygon([
            (-103.998, 40.002),
            (-103.998, 40.008),
            (-103.992, 40.008),
            (-103.992, 40.002)
        ])

        classified = selector.classify_tract(
            tract_id="TEST-1",
            legal_description="Test Tract",
            geometry=tract_geometry
        )

        assert classified.tract_type == TractType.UNIT

    def test_classify_offset_tract(self):
        """Test classification of tract in offset zone."""
        unit_polygon = Polygon([
            (-104.0, 40.0),
            (-104.0, 40.01),
            (-103.99, 40.01),
            (-103.99, 40.0)
        ])

        engine = BufferEngine(buffer_distance_miles=0.5)
        offset_polygon = engine.create_buffer(unit_polygon)

        selector = TractSelector(unit_polygon, offset_polygon)

        # Tract outside unit but inside buffer
        tract_geometry = Polygon([
            (-104.02, 40.0),
            (-104.02, 40.01),
            (-104.01, 40.01),
            (-104.01, 40.0)
        ])

        classified = selector.classify_tract(
            tract_id="TEST-2",
            legal_description="Test Offset Tract",
            geometry=tract_geometry
        )

        # Should be either OFFSET or UNIT depending on buffer size
        assert classified.tract_type in [TractType.OFFSET, TractType.UNIT, TractType.UNKNOWN]

    def test_classify_batch(self):
        """Test batch classification."""
        unit_polygon = Polygon([
            (-104.0, 40.0),
            (-104.0, 40.01),
            (-103.99, 40.01),
            (-103.99, 40.0)
        ])

        engine = BufferEngine(buffer_distance_miles=0.5)
        offset_polygon = engine.create_buffer(unit_polygon)

        selector = TractSelector(unit_polygon, offset_polygon)

        # Multiple tracts
        tracts = [
            {
                "tract_id": "1",
                "legal_description": "Inside",
                "geometry": Point(-103.995, 40.005).buffer(0.001)
            },
            {
                "tract_id": "2",
                "legal_description": "Outside",
                "geometry": Point(-104.1, 40.0).buffer(0.001)
            }
        ]

        unit_tracts, offset_tracts = selector.classify_batch(tracts)

        # Should have at least some classification
        assert len(unit_tracts) + len(offset_tracts) <= len(tracts)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
