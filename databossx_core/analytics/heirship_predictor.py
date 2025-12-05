"""
Heirship predictor - predicts missing heirs using pattern matching
"""

import uuid
from datetime import datetime
from typing import List
import re

from ..models.analytics import HeirshipPrediction, ConfidenceMetrics
from ..models.chain import ChainGraph


class HeirshipPredictor:
    """
    Predicts missing heirs based on probate patterns and gaps
    """

    async def predict(self, chain: ChainGraph) -> List[HeirshipPrediction]:
        """
        Predict missing heirs

        Args:
            chain: ChainGraph object

        Returns:
            List of HeirshipPrediction objects
        """
        predictions = []

        # Look for estate/probate-related nodes
        for node in chain.nodes:
            if self._is_estate_node(node.entity_name):
                # Predict potential heirs
                prediction = await self._predict_heirs_for_estate(node, chain)
                if prediction:
                    predictions.append(prediction)

        return predictions

    def _is_estate_node(self, name: str) -> bool:
        """Check if name indicates an estate"""
        estate_patterns = [
            r"estate of",
            r"deceased",
            r"decedent",
        ]

        name_lower = name.lower()
        for pattern in estate_patterns:
            if re.search(pattern, name_lower):
                return True

        return False

    async def _predict_heirs_for_estate(
        self, estate_node, chain: ChainGraph
    ) -> HeirshipPrediction:
        """Predict heirs for an estate"""
        # Extract deceased name
        deceased_name = self._extract_deceased_name(estate_node.entity_name)

        # Look for common heir patterns
        predicted_heirs = []

        # Pattern 1: Children (look for Jr, Sr, III, etc.)
        potential_children = self._find_name_variants(deceased_name, chain)
        for child in potential_children:
            predicted_heirs.append({
                "name": child,
                "relationship": "potential_child",
                "confidence": 0.6,
            })

        # Pattern 2: Spouse (look for same last name with different first name)
        potential_spouse = self._find_potential_spouse(deceased_name, chain)
        if potential_spouse:
            predicted_heirs.append({
                "name": potential_spouse,
                "relationship": "potential_spouse",
                "confidence": 0.5,
            })

        if not predicted_heirs:
            return None

        # Calculate confidence
        confidence = ConfidenceMetrics(
            overall_confidence=0.6,
            data_quality_score=0.7,
            pattern_match_score=0.6,
            historical_accuracy=0.5,
        )

        # Suggest searches
        suggested_searches = [
            f"Probate records for {deceased_name}",
            f"Death certificate for {deceased_name}",
            f"Family tree search for {deceased_name}",
        ]

        return HeirshipPrediction(
            id=str(uuid.uuid4()),
            deceased_owner_name=deceased_name,
            predicted_heirs=predicted_heirs,
            prediction_basis="probate_pattern",
            confidence=confidence,
            suggested_searches=suggested_searches,
            created_at=datetime.utcnow(),
        )

    def _extract_deceased_name(self, estate_name: str) -> str:
        """Extract deceased name from estate designation"""
        # Remove "Estate of" and similar prefixes
        cleaned = re.sub(r"(?:estate|heirs) of\s+", "", estate_name, flags=re.IGNORECASE)
        cleaned = re.sub(r",?\s*deceased", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _find_name_variants(self, name: str, chain: ChainGraph) -> List[str]:
        """Find name variants (Jr, Sr, etc.)"""
        variants = []
        last_name = name.split()[-1] if name else ""

        for node in chain.nodes:
            if last_name and last_name.lower() in node.entity_name.lower():
                if node.entity_name.lower() != name.lower():
                    variants.append(node.entity_name)

        return variants

    def _find_potential_spouse(self, name: str, chain: ChainGraph) -> str:
        """Find potential spouse by matching last name"""
        last_name = name.split()[-1] if name else ""

        for node in chain.nodes:
            node_last = node.entity_name.split()[-1] if node.entity_name else ""
            if node_last.lower() == last_name.lower() and node.entity_name.lower() != name.lower():
                # Check if it's a different first name (not Jr/Sr variant)
                if not re.search(r"\b(jr|sr|iii|ii|iv)\b", node.entity_name, re.IGNORECASE):
                    return node.entity_name

        return None
