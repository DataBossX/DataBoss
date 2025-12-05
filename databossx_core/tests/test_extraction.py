"""
Tests for entity extraction
"""

import pytest
from databossx_core.extraction.extractor import EntityExtractor


@pytest.mark.asyncio
async def test_grantor_extraction():
    """Test grantor extraction with Weld County document"""
    from databossx_core.extraction.grantor_extractor import GrantorExtractor

    extractor = GrantorExtractor()

    text = """
    MINERAL DEED

    GRANTOR: SMITH FAMILY TRUST, a Colorado trust, and
    JOHN SMITH, a married man

    convey to the grantees all mineral rights...
    """

    grantors = await extractor.extract(text)

    assert len(grantors) >= 1
    assert any("SMITH" in g.normalized_name for g in grantors)


@pytest.mark.asyncio
async def test_legal_description_extraction():
    """Test legal description extraction"""
    from databossx_core.extraction.legal_desc_extractor import LegalDescriptionExtractor

    extractor = LegalDescriptionExtractor()

    text = """
    LEGAL DESCRIPTION:

    The NE 1/4 of Section 12, Township 5 North, Range 68 West,
    6th Principal Meridian, Weld County, Colorado,
    containing 160 acres, more or less.
    """

    descriptions = await extractor.extract(text)

    assert len(descriptions) > 0
    desc = descriptions[0]
    assert desc.section == "12"
    assert "5N" in desc.township
    assert "68W" in desc.range
    assert desc.county == "Weld"


@pytest.mark.asyncio
async def test_depth_clause_extraction():
    """Test depth clause extraction"""
    from databossx_core.extraction.depth_clause_extractor import DepthClauseExtractor

    extractor = DepthClauseExtractor()

    text = """
    The mineral rights conveyed herein are limited from the surface
    to 5000 feet below the surface, including all strata and formations
    within said depths.
    """

    clauses = await extractor.extract(text)

    assert len(clauses) > 0
    clause = clauses[0]
    assert clause.from_depth == 0
    assert clause.to_depth == 5000


@pytest.mark.asyncio
async def test_acreage_extraction():
    """Test acreage extraction"""
    from databossx_core.extraction.acreage_extractor import AcreageExtractor

    extractor = AcreageExtractor()

    text = """
    The property described above contains 160.5 acres, more or less.
    Gross Acres: 160.5
    Net Acres: 120.25
    """

    acreage = await extractor.extract(text)

    assert acreage is not None
    assert acreage.total_acres is not None


@pytest.mark.asyncio
async def test_campbell_county_document():
    """Test extraction with Campbell County, Wyoming document"""
    extractor = EntityExtractor()

    text = """
    ASSIGNMENT OF OIL AND GAS LEASE

    ASSIGNOR: WESTERN ENERGY COMPANY, LLC, a Wyoming limited liability company

    ASSIGNEE: ROCKY MOUNTAIN RESOURCES, INC., a Delaware corporation

    For good and valuable consideration, Assignor hereby assigns, transfers
    and conveys to Assignee an undivided 25% working interest in and to that
    certain Oil and Gas Lease dated January 15, 2020, covering:

    Section 24, Township 44 North, Range 73 West, 6th P.M.,
    Campbell County, Wyoming, containing 640 acres.

    Depths: from surface to the base of the Niobrara Formation
    """

    extraction = await extractor.extract("doc_123", text)

    assert len(extraction.grantors) > 0
    assert len(extraction.grantees) > 0
    assert len(extraction.legal_descriptions) > 0

    # Check for depth clause
    assert len(extraction.depth_clauses) > 0
    depth = extraction.depth_clauses[0]
    assert "Niobrara" in depth.formation_name or depth.formation_name
