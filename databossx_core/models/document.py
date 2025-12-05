"""
Document data models
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class DocumentType(str, Enum):
    """Supported document types"""
    DEED = "deed"
    MINERAL_DEED = "mineral_deed"
    LEASE = "lease"
    ASSIGNMENT = "assignment"
    AFFIDAVIT = "affidavit"
    POOLING = "pooling"
    PROBATE = "probate"
    ROYALTY_DEED = "royalty_deed"
    RATIFICATION = "ratification"
    DIVISION_ORDER = "division_order"
    UNKNOWN = "unknown"


class DocumentMetadata(BaseModel):
    """Metadata extracted from document"""
    county: Optional[str] = None
    state: Optional[str] = None
    recording_date: Optional[datetime] = None
    instrument_number: Optional[str] = None
    book: Optional[str] = None
    page: Optional[str] = None
    grantor_names: List[str] = Field(default_factory=list)
    grantee_names: List[str] = Field(default_factory=list)
    legal_descriptions: List[str] = Field(default_factory=list)
    effective_date: Optional[datetime] = None
    consideration: Optional[str] = None
    notary_info: Optional[Dict[str, Any]] = None
    additional_fields: Dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """Core document model"""
    id: str
    filename: str
    file_hash: str
    file_type: str  # pdf, tiff, png, csv, xlsx
    file_size: int
    uploaded_at: datetime
    document_type: DocumentType = DocumentType.UNKNOWN
    document_type_confidence: float = 0.0
    metadata: Optional[DocumentMetadata] = None
    status: str = "uploaded"  # uploaded, processing, completed, failed
    error_message: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    raw_content: Optional[bytes] = None


class UploadedFile(BaseModel):
    """Model for file uploads"""
    filename: str
    content_type: str
    size: int
    content: bytes

    class Config:
        arbitrary_types_allowed = True
