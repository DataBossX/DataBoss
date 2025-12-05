"""
Base OCR engine interface
"""

from abc import ABC, abstractmethod
from typing import Optional
from ...models.ocr import OCRResult, OCREngine


class BaseOCREngine(ABC):
    """Base class for all OCR engines"""

    def __init__(self, engine_type: OCREngine):
        self.engine_type = engine_type

    @abstractmethod
    async def process(self, document_id: str, image_data: bytes) -> OCRResult:
        """
        Process image and return OCR result

        Args:
            document_id: Document ID
            image_data: Image data as bytes

        Returns:
            OCRResult object
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this OCR engine is available"""
        pass
