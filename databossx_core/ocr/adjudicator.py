"""
LLM Adjudicator for OCR conflicts
"""

import os
from typing import List, Tuple
import anthropic

from ..models.ocr import OCRLineResult


class LLMAdjudicator:
    """
    Uses LLM to adjudicate between conflicting OCR results
    """

    def __init__(self, model_name: str = "claude-3-5-sonnet-20241022"):
        self.model_name = model_name
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None

    async def adjudicate_line(
        self, line_results: List[OCRLineResult]
    ) -> Tuple[str, float]:
        """
        Adjudicate between multiple OCR readings of the same line

        Args:
            line_results: List of OCR results for the same line

        Returns:
            Tuple of (selected_text, confidence)
        """
        if not self.client:
            # Fallback to highest confidence if no API key
            best_result = max(line_results, key=lambda x: x.confidence)
            return best_result.text, best_result.confidence

        # Build options for LLM
        options = []
        for i, lr in enumerate(line_results, 1):
            options.append(
                f"Option {i} (from {lr.engine.value}, confidence {lr.confidence:.2f}): {lr.text}"
            )

        prompt = f"""You are an expert OCR adjudicator for legal land documents.

Multiple OCR engines have read the same line and produced different results. Your task is to select the most accurate reading based on:
1. Common legal document terminology and patterns
2. Contextual consistency with land records
3. Proper names, dates, and legal descriptions
4. OCR confidence scores

OCR Readings:
{chr(10).join(options)}

Instructions:
- Analyze each option carefully
- Consider which reading makes the most sense in a legal land document context
- Return ONLY the number of the best option (1, 2, 3, etc.)
- If multiple options are equally valid, choose the one with highest confidence

Your selection (just the number):"""

        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            selection_text = response.content[0].text.strip()
            selection_num = int(selection_text)

            if 1 <= selection_num <= len(line_results):
                selected = line_results[selection_num - 1]
                # Boost confidence slightly for LLM-validated selection
                confidence = min(selected.confidence + 0.1, 1.0)
                return selected.text, confidence
            else:
                # Invalid selection, fallback
                best_result = max(line_results, key=lambda x: x.confidence)
                return best_result.text, best_result.confidence

        except Exception as e:
            # On error, fallback to highest confidence
            best_result = max(line_results, key=lambda x: x.confidence)
            return best_result.text, best_result.confidence

    async def adjudicate_batch(
        self, line_results_batch: List[List[OCRLineResult]]
    ) -> List[Tuple[str, float]]:
        """
        Adjudicate multiple lines in a batch for efficiency

        Args:
            line_results_batch: List of lists of OCR line results

        Returns:
            List of (selected_text, confidence) tuples
        """
        results = []
        for line_results in line_results_batch:
            result = await self.adjudicate_line(line_results)
            results.append(result)
        return results
