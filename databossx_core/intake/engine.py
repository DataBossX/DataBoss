"""
Main intake engine for document processing
"""

import hashlib
import mimetypes
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path
import uuid

from ..models.document import Document, DocumentType, UploadedFile
from .detector import DocumentTypeDetector
from .parser import DocumentParser


class IntakeEngine:
    """
    Main intake engine for processing documents
    Handles: PDF, TIFF, PNG, CSV, XLSX
    """

    SUPPORTED_FORMATS = {
        "application/pdf": "pdf",
        "image/tiff": "tiff",
        "image/png": "png",
        "image/jpeg": "jpg",
        "text/csv": "csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/vnd.ms-excel": "xls",
    }

    def __init__(self):
        self.detector = DocumentTypeDetector()
        self.parser = DocumentParser()

    def calculate_hash(self, content: bytes) -> str:
        """Calculate SHA-256 hash of file content"""
        return hashlib.sha256(content).hexdigest()

    def validate_file(self, uploaded_file: UploadedFile) -> Tuple[bool, Optional[str]]:
        """
        Validate uploaded file
        Returns: (is_valid, error_message)
        """
        # Check file size (max 100MB)
        max_size = 100 * 1024 * 1024
        if uploaded_file.size > max_size:
            return False, f"File size {uploaded_file.size} exceeds maximum {max_size}"

        # Check content type
        if uploaded_file.content_type not in self.SUPPORTED_FORMATS:
            return False, f"Unsupported file type: {uploaded_file.content_type}"

        # Check for empty files
        if uploaded_file.size == 0:
            return False, "Empty file"

        return True, None

    def detect_file_type(self, filename: str, content_type: str) -> str:
        """Detect file type from filename and content type"""
        if content_type in self.SUPPORTED_FORMATS:
            return self.SUPPORTED_FORMATS[content_type]

        # Fallback to extension
        ext = Path(filename).suffix.lower()
        ext_map = {
            ".pdf": "pdf",
            ".tiff": "tiff",
            ".tif": "tiff",
            ".png": "png",
            ".jpg": "jpg",
            ".jpeg": "jpg",
            ".csv": "csv",
            ".xlsx": "xlsx",
            ".xls": "xls",
        }
        return ext_map.get(ext, "unknown")

    async def process_upload(self, uploaded_file: UploadedFile) -> Document:
        """
        Process uploaded file and create Document object

        Args:
            uploaded_file: UploadedFile object

        Returns:
            Document object with initial metadata
        """
        # Validate file
        is_valid, error_msg = self.validate_file(uploaded_file)
        if not is_valid:
            raise ValueError(error_msg)

        # Calculate hash
        file_hash = self.calculate_hash(uploaded_file.content)

        # Detect file type
        file_type = self.detect_file_type(uploaded_file.filename, uploaded_file.content_type)

        # Create document
        document = Document(
            id=str(uuid.uuid4()),
            filename=uploaded_file.filename,
            file_hash=file_hash,
            file_type=file_type,
            file_size=uploaded_file.size,
            uploaded_at=datetime.utcnow(),
            status="uploaded",
        )

        return document

    async def detect_document_type(
        self, document: Document, text_content: str
    ) -> Tuple[DocumentType, float]:
        """
        Detect document type from text content

        Args:
            document: Document object
            text_content: Extracted text from document

        Returns:
            Tuple of (DocumentType, confidence_score)
        """
        return await self.detector.detect(text_content)

    async def parse_structured_data(
        self, document: Document, content: bytes
    ) -> dict:
        """
        Parse structured data from CSV/XLSX files

        Args:
            document: Document object
            content: File content

        Returns:
            Parsed data as dictionary
        """
        return await self.parser.parse(document.file_type, content)

    def get_supported_formats(self) -> list:
        """Get list of supported file formats"""
        return list(self.SUPPORTED_FORMATS.values())
