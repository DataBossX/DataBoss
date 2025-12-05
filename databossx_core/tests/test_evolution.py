"""
Tests for self-evolving mutation engine
"""

import pytest
from datetime import datetime
from databossx_core.evolution.mutation_engine import MutationEngine
from databossx_core.models.evolution import ExtractionRule


@pytest.mark.asyncio
async def test_mutation_generation():
    """Test mutation generation"""
    from databossx_core.evolution.rule_mutator import RuleMutator

    mutator = RuleMutator()

    original_rule = ExtractionRule(
        id="rule1",
        rule_name="grantor_pattern_1",
        rule_type="regex",
        pattern=r"grantor:\s*([A-Z][A-Za-z\s]+)",
        target_field="grantor",
        confidence_threshold=0.7,
        version=1,
        created_at=datetime.utcnow(),
    )

    mutations = await mutator.mutate_rule(original_rule, [])

    assert len(mutations) > 0
    # Mutations should have different patterns
    for mutation in mutations:
        assert mutation.pattern != original_rule.pattern
        assert mutation.parent_rule_id == original_rule.id


@pytest.mark.asyncio
async def test_low_confidence_tracking():
    """Test tracking of low-confidence extractions"""
    engine = MutationEngine()

    await engine.track_low_confidence(
        document_id="doc1",
        extraction_id="ext1",
        field_name="grantor",
        extracted_value="John Smith",
        confidence=0.45,
        rule_id="rule1",
    )

    assert len(engine.low_confidence_extractions) == 1


@pytest.mark.asyncio
async def test_rule_scoring():
    """Test rule scoring"""
    from databossx_core.evolution.rule_scorer import RuleScorer

    scorer = RuleScorer()

    rule = ExtractionRule(
        id="rule1",
        rule_name="test_rule",
        rule_type="regex",
        pattern=r"test:\s*(\w+)",
        target_field="test",
        confidence_threshold=0.7,
        version=1,
        created_at=datetime.utcnow(),
    )

    test_cases = [
        {"text": "test: value1", "expected": "value1", "confidence": 0.9},
        {"text": "test: value2", "expected": "value2", "confidence": 0.85},
    ]

    score = await scorer.score_rule(rule, test_cases)

    assert "precision" in score
    assert "recall" in score
    assert "f1_score" in score
