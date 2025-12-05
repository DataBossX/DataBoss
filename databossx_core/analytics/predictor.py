"""
Main predictive analyzer - coordinates all prediction modules
"""

import uuid
from datetime import datetime
from typing import Optional

from ..models.analytics import PredictiveInsight, ConfidenceMetrics
from ..models.chain import ChainGraph
from .heirship_predictor import HeirshipPredictor
from .filing_predictor import FilingPredictor


class PredictiveAnalyzer:
    """
    Main predictive analyzer that coordinates all prediction modules
    """

    def __init__(self):
        self.heirship_predictor = HeirshipPredictor()
        self.filing_predictor = FilingPredictor()

    async def analyze(
        self,
        chain: ChainGraph,
        property_description: Optional[str] = None,
    ) -> PredictiveInsight:
        """
        Generate predictive insights for a chain

        Args:
            chain: ChainGraph object
            property_description: Property description

        Returns:
            PredictiveInsight object
        """
        # Predict missing heirs
        heirship_predictions = await self.heirship_predictor.predict(chain)

        # Predict missing filings
        filing_predictions = await self.filing_predictor.predict(chain)

        # Calculate overall risk score
        risk_score = self._calculate_risk_score(chain, heirship_predictions, filing_predictions)

        # Generate recommendations
        recommendations = self._generate_recommendations(chain, heirship_predictions, filing_predictions)

        return PredictiveInsight(
            id=str(uuid.uuid4()),
            chain_id=chain.id,
            property_description=property_description or chain.property_description,
            heirship_predictions=heirship_predictions,
            missing_filing_predictions=filing_predictions,
            overall_risk_score=risk_score,
            recommendations=recommendations,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def _calculate_risk_score(self, chain, heirship_preds, filing_preds) -> float:
        """Calculate overall risk score"""
        risk = 0.0

        # Add risk for gaps
        critical_gaps = [g for g in chain.gaps if g.severity == "critical"]
        risk += len(critical_gaps) * 0.3

        warning_gaps = [g for g in chain.gaps if g.severity == "warning"]
        risk += len(warning_gaps) * 0.1

        # Add risk for predictions
        risk += len(heirship_preds) * 0.15
        risk += len(filing_preds) * 0.1

        return min(1.0, risk)

    def _generate_recommendations(self, chain, heirship_preds, filing_preds) -> list:
        """Generate actionable recommendations"""
        recommendations = []

        if heirship_preds:
            recommendations.append(
                f"Conduct heirship search for {len(heirship_preds)} potential missing heirs"
            )

        if filing_preds:
            recommendations.append(
                f"Search for {len(filing_preds)} potentially unrecorded instruments"
            )

        critical_gaps = [g for g in chain.gaps if g.severity == "critical"]
        if critical_gaps:
            recommendations.append(
                f"Resolve {len(critical_gaps)} critical chain-of-title gaps"
            )

        if not chain.current_owners:
            recommendations.append("Clarify current ownership")

        return recommendations
