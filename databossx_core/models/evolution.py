"""
Self-evolution and mutation models
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ExtractionRule(BaseModel):
    """Rule for extracting entities from documents"""
    id: str
    rule_name: str
    rule_type: str  # "regex", "llm_prompt", "pattern_match", "heuristic"
    pattern: str  # The actual rule pattern or prompt
    target_field: str  # What this rule extracts (e.g., "grantor", "legal_description")
    confidence_threshold: float = 0.7
    version: int = 1
    parent_rule_id: Optional[str] = None
    created_at: datetime
    success_count: int = 0
    failure_count: int = 0
    avg_confidence: float = 0.0
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RuleMutation(BaseModel):
    """Mutation applied to an extraction rule"""
    id: str
    original_rule_id: str
    mutated_rule_id: str
    mutation_type: str  # "pattern_refinement", "threshold_adjustment", "prompt_enhancement"
    mutation_description: str
    reason: str  # Why this mutation was created
    test_results: Dict[str, Any] = Field(default_factory=dict)
    applied: bool = False
    applied_at: Optional[datetime] = None
    created_at: datetime


class MutationScore(BaseModel):
    """Score for a mutation's performance"""
    mutation_id: str
    rule_id: str
    precision: float
    recall: float
    f1_score: float
    confidence_improvement: float
    test_case_count: int
    passed_test_count: int
    failed_test_count: int
    score_date: datetime


class EvolutionHistory(BaseModel):
    """History of rule evolution"""
    id: str
    rule_id: str
    event_type: str  # "created", "mutated", "promoted", "deprecated", "replaced"
    description: str
    metrics: Dict[str, float] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class LowConfidenceExtraction(BaseModel):
    """Tracking of low-confidence extractions for evolution"""
    id: str
    document_id: str
    extraction_id: str
    field_name: str
    extracted_value: str
    confidence: float
    rule_id: str
    needs_review: bool = True
    reviewed: bool = False
    correct_value: Optional[str] = None
    created_at: datetime
