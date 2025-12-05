"""
Predictive analytics models
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from decimal import Decimal


class ConfidenceMetrics(BaseModel):
    """Confidence metrics for predictions"""
    overall_confidence: float
    data_quality_score: float
    pattern_match_score: float
    historical_accuracy: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HeirshipPrediction(BaseModel):
    """Prediction of missing heirs"""
    id: str
    deceased_owner_name: str
    predicted_heirs: List[Dict[str, Any]] = Field(default_factory=list)
    prediction_basis: str  # "probate_pattern", "family_tree", "similar_cases"
    confidence: ConfidenceMetrics
    suggested_searches: List[str] = Field(default_factory=list)
    created_at: datetime


class MissingFilingPrediction(BaseModel):
    """Prediction of likely unrecorded assignments"""
    id: str
    from_entity: str
    to_entity: str
    predicted_interest_type: str
    predicted_fraction: Optional[Decimal] = None
    prediction_basis: str  # "fractional_gap", "corporate_pattern", "operator_change"
    confidence: ConfidenceMetrics
    suggested_counties: List[str] = Field(default_factory=list)
    suggested_date_range: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime


class MisindexingPrediction(BaseModel):
    """Prediction of potential misindexed filings"""
    id: str
    document_id: str
    likely_correct_grantor: Optional[str] = None
    likely_correct_grantee: Optional[str] = None
    indexing_issue_type: str  # "name_variant", "missing_entity", "wrong_book_page"
    confidence: ConfidenceMetrics
    suggested_corrections: List[Dict[str, str]] = Field(default_factory=list)
    created_at: datetime


class PredictiveInsight(BaseModel):
    """Container for all predictive insights"""
    id: str
    chain_id: Optional[str] = None
    property_description: Optional[str] = None
    heirship_predictions: List[HeirshipPrediction] = Field(default_factory=list)
    missing_filing_predictions: List[MissingFilingPrediction] = Field(default_factory=list)
    misindexing_predictions: List[MisindexingPrediction] = Field(default_factory=list)
    overall_risk_score: float = 0.0
    recommendations: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AnalyticsMetrics(BaseModel):
    """System-wide analytics metrics"""
    total_documents_processed: int
    avg_confidence_score: float
    rule_evolution_count: int
    successful_predictions: int
    failed_predictions: int
    accuracy_rate: float
    processing_time_avg: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
