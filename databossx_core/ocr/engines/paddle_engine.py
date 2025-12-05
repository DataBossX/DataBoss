"""
PaddleOCR Engine
"""

import io
import uuid
import sys
from datetime import datetime
from typing import List, Optional
import numpy as np
from PIL import Image

from .base import BaseOCREngine
from ...models.ocr import OCRResult, OCREngine, OCRLineResult


class PaddleOCREngine(BaseOCREngine):
    """PaddleOCR engine wrapper"""

    def __init__(self):
        super().__init__(OCREngine.PADDLE_OCR)
        self._ocr_instance: Optional[any] = None

    def is_available(self) -> bool:
        """Check if PaddleOCR is available"""
        # PaddleOCR is not available on Windows
        if sys.platform == "win32":
            return False

        try:
            from paddleocr import PaddleOCR
            return True
        except ImportError:
            return False

    def _get_ocr_instance(self):
        """Lazy load PaddleOCR instance"""
        if self._ocr_instance is None:
            try:
                from paddleocr import PaddleOCR
                # Initialize with English language
                self._ocr_instance = PaddleOCR(
                    use_angle_cls=True,
                    lang="en",
                    show_log=False,
                )
            except Exception as e:
                raise RuntimeError(f"Failed to initialize PaddleOCR: {str(e)}")
        return self._ocr_instance

    async def process(self, document_id: str, image_data: bytes) -> OCRResult:
        """
        Process image with PaddleOCR

        Args:
            document_id: Document ID
            image_data: Image data as bytes

        Returns:
            OCRResult object
        """
        if not self.is_available():
            raise RuntimeError("PaddleOCR is not available on this system")

        start_time = datetime.utcnow()

        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))
            img_array = np.array(image)

            # Get OCR instance
            ocr = self._get_ocr_instance()

            # Run OCR
            results = ocr.ocr(img_array, cls=True)

            # Parse results
            lines = self._parse_results(results)

            # Build raw text
            raw_text = "\n".join(line.text for line in lines)

            # Calculate overall confidence
            confidences = [line.confidence for line in lines if line.confidence > 0]
            overall_confidence = (
                sum(confidences) / len(confidences) if confidences else 0.0
            )

            processing_time = (datetime.utcnow() - start_time).total_seconds()

            return OCRResult(
                id=str(uuid.uuid4()),
                document_id=document_id,
                engine=self.engine_type,
                raw_text=raw_text,
                lines=lines,
                overall_confidence=overall_confidence,
                processing_time=processing_time,
                created_at=datetime.utcnow(),
            )

        except Exception as e:
            raise RuntimeError(f"PaddleOCR processing failed: {str(e)}")

    def _parse_results(self, results: list) -> List[OCRLineResult]:
        """
        Parse PaddleOCR results into line results

        Args:
            results: PaddleOCR results

        Returns:
            List of OCRLineResult objects
        """
        line_results = []

        if not results or not results[0]:
            return line_results

        for line_num, line_data in enumerate(results[0], start=1):
            if not line_data:
                continue

            # PaddleOCR returns: [box, (text, confidence)]
            text = line_data[1][0]
            confidence = float(line_data[1][1])

            # Bounding box
            box = line_data[0]
            bounding_box = {
                "x_min": float(box[0][0]),
                "y_min": float(box[0][1]),
                "x_max": float(box[2][0]),
                "y_max": float(box[2][1]),
            }

            line_results.append(
                OCRLineResult(
                    line_number=line_num,
                    text=text,
                    confidence=confidence,
                    engine=self.engine_type,
                    bounding_box=bounding_box,
                )
            )

        return line_results
