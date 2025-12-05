"""
Filing predictor - predicts missing or misindexed filings
"""

import uuid
from datetime import datetime
from typing import List
from decimal import Decimal

from ..models.analytics import MissingFilingPrediction, ConfidenceMetrics
from ..models.chain import ChainGraph, ChainGap


class FilingPredictor:
    """
    Predicts likely unrecorded assignments and misindexed filings
    """

    async def predict(self, chain: ChainGraph) -> List[MissingFilingPrediction]:
        """
        Predict missing filings

        Args:
            chain: ChainGraph object

        Returns:
            List of MissingFilingPrediction objects
        """
        predictions = []

        # Check for fractional gaps
        fractional_predictions = await self._predict_from_fractional_gaps(chain)
        predictions.extend(fractional_predictions)

        # Check for missing links
        missing_link_predictions = await self._predict_from_missing_links(chain)
        predictions.extend(missing_link_predictions)

        return predictions

    async def _predict_from_fractional_gaps(
        self, chain: ChainGraph
    ) -> List[MissingFilingPrediction]:
        """Predict missing filings from fractional gaps"""
        predictions = []

        # Look for fractional mismatch gaps
        fractional_gaps = [g for g in chain.gaps if g.gap_type == "fractional_mismatch"]

        for gap in fractional_gaps:
            # Parse gap description to extract entities
            # This is simplified - real implementation would be more sophisticated
            prediction = MissingFilingPrediction(
                id=str(uuid.uuid4()),
                from_entity="Unknown",
                to_entity="Unknown",
                predicted_interest_type="mineral",
                predicted_fraction=None,
                prediction_basis="fractional_gap",
                confidence=ConfidenceMetrics(
                    overall_confidence=0.65,
                    data_quality_score=0.7,
                    pattern_match_score=0.6,
                    historical_accuracy=0.65,
                ),
                suggested_counties=[],
                suggested_date_range={},
                created_at=datetime.utcnow(),
            )
            predictions.append(prediction)

        return predictions

    async def _predict_from_missing_links(
        self, chain: ChainGraph
    ) -> List[MissingFilingPrediction]:
        """Predict missing filings from missing chain links"""
        predictions = []

        # Look for nodes that should be connected but aren't
        for node in chain.nodes:
            # Check if this node transferred interest but we don't see corresponding grantee
            outgoing_links = [l for l in chain.links if l.from_node_id == node.id]
            incoming_links = [l for l in chain.links if l.to_node_id == node.id]

            # If node received interest but never transferred it, but also isn't current owner
            if incoming_links and not outgoing_links and not node.is_current_owner:
                # Possible missing filing
                prediction = MissingFilingPrediction(
                    id=str(uuid.uuid4()),
                    from_entity=node.entity_name,
                    to_entity="Unknown",
                    predicted_interest_type=chain.interest_type.value,
                    prediction_basis="corporate_pattern",
                    confidence=ConfidenceMetrics(
                        overall_confidence=0.55,
                        data_quality_score=0.6,
                        pattern_match_score=0.5,
                        historical_accuracy=0.55,
                    ),
                    suggested_counties=[],
                    created_at=datetime.utcnow(),
                )
                predictions.append(prediction)

        return predictions
