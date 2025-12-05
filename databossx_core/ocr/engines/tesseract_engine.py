"""
Tesseract OCR Engine
"""

import io
import uuid
from datetime import datetime
from typing import List
from PIL import Image
import pytesseract

from .base import BaseOCREngine
from ...models.ocr import OCRResult, OCREngine, OCRLineResult


class TesseractEngine(BaseOCREngine):
    """Tesseract OCR engine wrapper"""

    def __init__(self):
        super().__init__(OCREngine.TESSERACT)

    def is_available(self) -> bool:
        """Check if Tesseract is available"""
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    async def process(self, document_id: str, image_data: bytes) -> OCRResult:
        """
        Process image with Tesseract

        Args:
            document_id: Document ID
            image_data: Image data as bytes

        Returns:
            OCRResult object
        """
        start_time = datetime.utcnow()

        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))

            # Get detailed OCR data
            ocr_data = pytesseract.image_to_data(
                image, output_type=pytesseract.Output.DICT
            )

            # Extract text and confidence
            raw_text = pytesseract.image_to_string(image)

            # Parse line-by-line results
            lines = self._parse_lines(ocr_data)

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
            raise RuntimeError(f"Tesseract OCR failed: {str(e)}")

    def _parse_lines(self, ocr_data: dict) -> List[OCRLineResult]:
        """
        Parse Tesseract OCR data into line results

        Args:
            ocr_data: Tesseract OCR data dictionary

        Returns:
            List of OCRLineResult objects
        """
        lines = {}
        num_boxes = len(ocr_data["text"])

        for i in range(num_boxes):
            text = ocr_data["text"][i].strip()
            conf = float(ocr_data["conf"][i])
            line_num = ocr_data["line_num"][i]

            if not text or conf < 0:
                continue

            # Group by line number
            if line_num not in lines:
                lines[line_num] = {
                    "texts": [],
                    "confidences": [],
                }

            lines[line_num]["texts"].append(text)
            lines[line_num]["confidences"].append(conf / 100.0)  # Normalize to 0-1

        # Convert to OCRLineResult objects
        line_results = []
        for line_num, data in sorted(lines.items()):
            line_text = " ".join(data["texts"])
            line_conf = (
                sum(data["confidences"]) / len(data["confidences"])
                if data["confidences"]
                else 0.0
            )

            line_results.append(
                OCRLineResult(
                    line_number=line_num,
                    text=line_text,
                    confidence=line_conf,
                    engine=self.engine_type,
                )
            )

        return line_results
