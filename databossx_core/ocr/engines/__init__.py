"""
OCR Engine implementations
"""

from .tesseract_engine import TesseractEngine
from .paddle_engine import PaddleOCREngine

__all__ = ["TesseractEngine", "PaddleOCREngine"]
