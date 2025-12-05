"""
OCR Fusion Engine - Combines multiple OCR engines with intelligent adjudication
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Optional
import uuid

from ..models.ocr import OCRResult, OCRFusionResult, FusedLineResult, OCREngine, OCRLineResult
from .adjudicator import LLMAdjudicator


class OCRFusionEngine:
    """
    Advanced OCR fusion engine that combines results from multiple OCR engines
    Uses LLM adjudication to select the best reading per line
    """

    def __init__(self, llm_adjudicator: Optional[LLMAdjudicator] = None):
        self.ocr_engines = []
        self.adjudicator = llm_adjudicator or LLMAdjudicator()

    def register_engine(self, engine):
        """Register an OCR engine"""
        self.ocr_engines.append(engine)

    async def process_document(
        self, document_id: str, image_data: bytes
    ) -> OCRFusionResult:
        """
        Process document with all registered OCR engines and fuse results

        Args:
            document_id: Document ID
            image_data: Image data as bytes

        Returns:
            OCRFusionResult with fused text
        """
        if not self.ocr_engines:
            raise ValueError("No OCR engines registered")

        # Run all OCR engines in parallel
        tasks = [
            engine.process(document_id, image_data) for engine in self.ocr_engines
        ]
        ocr_results: List[OCRResult] = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out failed results
        valid_results = [r for r in ocr_results if isinstance(r, OCRResult)]

        if not valid_results:
            raise RuntimeError("All OCR engines failed")

        # Fuse results
        fused_result = await self.fuse_results(document_id, valid_results)

        return fused_result

    async def fuse_results(
        self, document_id: str, ocr_results: List[OCRResult]
    ) -> OCRFusionResult:
        """
        Fuse multiple OCR results using line-by-line adjudication

        Args:
            document_id: Document ID
            ocr_results: List of OCR results from different engines

        Returns:
            Fused OCR result
        """
        # Organize results by line number
        line_map: Dict[int, List[OCRLineResult]] = {}

        for result in ocr_results:
            for line_result in result.lines:
                line_num = line_result.line_number
                if line_num not in line_map:
                    line_map[line_num] = []
                line_map[line_num].append(line_result)

        # Fuse each line
        fused_lines: List[FusedLineResult] = []
        for line_num in sorted(line_map.keys()):
            line_results = line_map[line_num]
            fused_line = await self.fuse_line(line_num, line_results)
            fused_lines.append(fused_line)

        # Combine fused lines into text
        fused_text = "\n".join(line.text for line in fused_lines)

        # Calculate overall confidence
        overall_confidence = (
            sum(line.confidence for line in fused_lines) / len(fused_lines)
            if fused_lines
            else 0.0
        )

        return OCRFusionResult(
            id=str(uuid.uuid4()),
            document_id=document_id,
            fused_text=fused_text,
            lines=fused_lines,
            source_results=[r.id for r in ocr_results],
            overall_confidence=overall_confidence,
            fusion_method="llm_adjudication",
            llm_model_used=self.adjudicator.model_name if self.adjudicator else None,
            created_at=datetime.utcnow(),
        )

    async def fuse_line(
        self, line_number: int, line_results: List[OCRLineResult]
    ) -> FusedLineResult:
        """
        Fuse a single line from multiple OCR results

        Strategy:
        1. If all engines agree, use that text
        2. If engines disagree, use LLM adjudication
        3. Select the engine with highest confidence for that line

        Args:
            line_number: Line number
            line_results: OCR results for this line

        Returns:
            Fused line result
        """
        if not line_results:
            return FusedLineResult(
                line_number=line_number,
                text="",
                confidence=0.0,
                selected_engine=OCREngine.TESSERACT,
                llm_adjudicated=False,
            )

        # Collect unique texts
        texts = {lr.text for lr in line_results}

        # Build engine votes map
        engine_votes = {lr.engine: lr.text for lr in line_results}

        # If all agree, use consensus
        if len(texts) == 1:
            text = list(texts)[0]
            best_result = max(line_results, key=lambda x: x.confidence)
            return FusedLineResult(
                line_number=line_number,
                text=text,
                confidence=best_result.confidence,
                selected_engine=best_result.engine,
                engine_votes=engine_votes,
                llm_adjudicated=False,
                provenance={
                    "method": "consensus",
                    "engine_count": len(line_results),
                },
            )

        # If engines disagree, use LLM adjudication
        if self.adjudicator:
            adjudicated_text, confidence = await self.adjudicator.adjudicate_line(
                line_results
            )
            # Find which engine provided this text
            selected_engine = OCREngine.TESSERACT
            for lr in line_results:
                if lr.text == adjudicated_text:
                    selected_engine = lr.engine
                    break

            return FusedLineResult(
                line_number=line_number,
                text=adjudicated_text,
                confidence=confidence,
                selected_engine=selected_engine,
                engine_votes=engine_votes,
                llm_adjudicated=True,
                provenance={
                    "method": "llm_adjudication",
                    "engine_count": len(line_results),
                    "model": self.adjudicator.model_name,
                },
            )

        # Fallback: use highest confidence
        best_result = max(line_results, key=lambda x: x.confidence)
        return FusedLineResult(
            line_number=line_number,
            text=best_result.text,
            confidence=best_result.confidence,
            selected_engine=best_result.engine,
            engine_votes=engine_votes,
            llm_adjudicated=False,
            provenance={
                "method": "max_confidence",
                "engine_count": len(line_results),
            },
        )
