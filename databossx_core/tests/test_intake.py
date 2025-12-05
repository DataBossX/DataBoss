"""
Tests for intake engine
"""

import pytest
from databossx_core.intake.engine import IntakeEngine
from databossx_core.models.document import UploadedFile, DocumentType


@pytest.mark.asyncio
async def test_intake_engine_pdf():
    """Test intake engine with PDF file"""
    engine = IntakeEngine()

    # Create mock PDF upload
    uploaded_file = UploadedFile(
        filename="test_deed.pdf",
        content_type="application/pdf",
        size=1024,
        content=b"mock pdf content",
    )

    # Process upload
    document = await engine.process_upload(uploaded_file)

    assert document is not None
    assert document.filename == "test_deed.pdf"
    assert document.file_type == "pdf"
    assert document.status == "uploaded"


@pytest.mark.asyncio
async def test_document_type_detection():
    """Test document type detection"""
    from databossx_core.intake.detector import DocumentTypeDetector

    detector = DocumentTypeDetector()

    # Test mineral deed detection
    text = """
    MINERAL DEED

    GRANTOR: John Smith, a single man
    GRANTEE: Jane Doe, a married woman

    The grantor hereby conveys all mineral rights in Section 12,
    Township 5 North, Range 68 West, 6th P.M., Weld County, Colorado.
    """

    doc_type, confidence = await detector.detect(text)

    assert doc_type == DocumentType.MINERAL_DEED
    assert confidence > 0.6


@pytest.mark.asyncio
async def test_supported_formats():
    """Test supported file formats"""
    engine = IntakeEngine()

    formats = engine.get_supported_formats()

    assert "pdf" in formats
    assert "tiff" in formats
    assert "png" in formats
    assert "csv" in formats
    assert "xlsx" in formats


def test_file_hash():
    """Test file hash calculation"""
    engine = IntakeEngine()

    content = b"test content"
    hash1 = engine.calculate_hash(content)
    hash2 = engine.calculate_hash(content)

    # Same content should produce same hash
    assert hash1 == hash2

    # Different content should produce different hash
    different_content = b"different content"
    hash3 = engine.calculate_hash(different_content)
    assert hash1 != hash3
