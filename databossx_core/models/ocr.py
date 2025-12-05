"""
OCR data models
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class OCREngine(str, Enum):
    """Supported OCR engines"""
    TESSERACT = "tesseract"
    PADDLE_OCR = "paddle_ocr"
    GOOGLE_VISION = "google_vision"
    AZURE_VISION = "azure_vision"
    AWS_TEXTRACT = "aws_textract"
    LLM_VISION = "llm_vision"


class OCRLineResult(BaseModel):
    """Single line OCR result from one engine"""
    line_number: int
    text: str
    confidence: float
    engine: OCREngine
    bounding_box: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OCRResult(BaseModel):
    """OCR result from a single engine"""
    id: str
    document_id: str
    engine: OCREngine
    raw_text: str
    lines: List[OCRLineResult] = Field(default_factory=list)
    overall_confidence: float
    processing_time: float
    created_at: datetime
    page_count: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OCRFusionResult(BaseModel):
    """Fused OCR result from multiple engines with LLM adjudication"""
    id: str
    document_id: str
    fused_text: str
    lines: List["FusedLineResult"] = Field(default_factory=list)
    source_results: List[str] = Field(default_factory=list)  # OCR result IDs
    overall_confidence: float
    fusion_method: str = "llm_adjudication"
    llm_model_used: Optional[str] = None
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FusedLineResult(BaseModel):
    """Single line from fused OCR result"""
    line_number: int
    text: str
    confidence: float
    selected_engine: OCREngine
    engine_votes: Dict[OCREngine, str] = Field(default_factory=dict)
    llm_adjudicated: bool = False
    provenance: Dict[str, Any] = Field(default_factory=dict)
