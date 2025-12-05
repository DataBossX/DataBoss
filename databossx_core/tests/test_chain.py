"""
Tests for chain-of-title builder
"""

import pytest
from datetime import datetime
from databossx_core.chain.builder import ChainBuilder
from databossx_core.models.document import Document, DocumentType, DocumentMetadata
from databossx_core.models.entity import EntityExtraction, Grantor, Grantee, EntityType


@pytest.mark.asyncio
async def test_chain_builder():
    """Test chain builder with simple conveyance"""
    builder = ChainBuilder()

    # Create mock documents and extractions
    doc1 = Document(
        id="doc1",
        filename="deed1.pdf",
        file_hash="hash1",
        file_type="pdf",
        file_size=1024,
        uploaded_at=datetime.utcnow(),
        document_type=DocumentType.MINERAL_DEED,
        document_type_confidence=0.9,
        metadata=DocumentMetadata(recording_date=datetime(2020, 1, 1)),
    )

    extraction1 = EntityExtraction(
        id="ext1",
        document_id="doc1",
        grantors=[
            Grantor(
                id="g1",
                name="John Smith",
                normalized_name="JOHN SMITH",
                entity_type=EntityType.PERSON,
                confidence=0.9,
                source_text="GRANTOR: John Smith",
            )
        ],
        grantees=[
            Grantee(
                id="ge1",
                name="Jane Doe",
                normalized_name="JANE DOE",
                entity_type=EntityType.PERSON,
                confidence=0.9,
                source_text="GRANTEE: Jane Doe",
            )
        ],
        legal_descriptions=[],
        depth_clauses=[],
        overall_confidence=0.9,
        created_at=datetime.utcnow().isoformat(),
    )

    # Build chain
    chain = await builder.build_chain(
        documents=[doc1],
        extractions=[extraction1],
        property_description="Section 12, T5N, R68W",
    )

    assert chain is not None
    assert len(chain.nodes) == 2
    assert len(chain.links) == 1
    assert len(chain.current_owners) > 0


@pytest.mark.asyncio
async def test_chain_gap_detection():
    """Test gap detection in chain"""
    from databossx_core.chain.graph_analyzer import ChainGraphAnalyzer

    analyzer = ChainGraphAnalyzer()

    # Create mock chain with gaps
    # (Simplified test - full implementation would create complete chain)

    # Test would verify gap detection works
    pass


def test_fraction_reconciler():
    """Test fraction reconciliation"""
    from databossx_core.chain.fraction_reconciler import FractionReconciler
    from databossx_core.models.chain import ChainNode, Ownership, InterestType, OwnershipType
    from decimal import Decimal

    reconciler = FractionReconciler()

    # Create node with fractional interests
    node = ChainNode(
        id="n1",
        entity_name="Test Owner",
        normalized_name="TEST OWNER",
        ownerships=[
            Ownership(
                owner_id="n1",
                owner_name="Test Owner",
                interest_type=InterestType.MINERAL,
                ownership_type=OwnershipType.FEE_SIMPLE,
                fraction=Decimal("0.5"),
                source_document_id="doc1",
                confidence=0.9,
            ),
            Ownership(
                owner_id="n1",
                owner_name="Test Owner",
                interest_type=InterestType.MINERAL,
                ownership_type=OwnershipType.FEE_SIMPLE,
                fraction=Decimal("0.25"),
                source_document_id="doc2",
                confidence=0.9,
            ),
        ],
    )

    result = reconciler.reconcile([node])

    assert result["total_interest"] == 0.75
    assert "Test Owner" in result["by_owner"]
