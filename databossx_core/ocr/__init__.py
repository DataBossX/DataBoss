"""
OCR Fusion Layer - Multi-engine OCR with LLM adjudication
"""

from .fusion_engine import OCRFusionEngine
from .engines.tesseract_engine import TesseractEngine
from .engines.paddle_engine import PaddleOCREngine
from .adjudicator import LLMAdjudicator

__all__ = [
    "OCRFusionEngine",
    "TesseractEngine",
    "PaddleOCREngine",
    "LLMAdjudicator",
]
