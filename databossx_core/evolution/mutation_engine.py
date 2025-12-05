"""
Self-evolving mutation engine - automatically improves extraction rules
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from ..models.evolution import (
    ExtractionRule,
    RuleMutation,
    MutationScore,
    EvolutionHistory,
    LowConfidenceExtraction,
)
from .rule_mutator import RuleMutator
from .rule_scorer import RuleScorer


class MutationEngine:
    """
    Self-evolving mutation engine that automatically refines extraction rules
    """

    def __init__(self, evolution_archive_path: str = "./evolve"):
        self.evolution_path = Path(evolution_archive_path)
        self.evolution_path.mkdir(exist_ok=True)
        self.mutator = RuleMutator()
        self.scorer = RuleScorer()
        self.rules: Dict[str, ExtractionRule] = {}
        self.mutations: List[RuleMutation] = []
        self.low_confidence_extractions: List[LowConfidenceExtraction] = []

    async def track_low_confidence(
        self,
        document_id: str,
        extraction_id: str,
        field_name: str,
        extracted_value: str,
        confidence: float,
        rule_id: str,
    ):
        """
        Track a low-confidence extraction for future improvement

        Args:
            document_id: Document ID
            extraction_id: Extraction ID
            field_name: Field that was extracted
            extracted_value: Extracted value
            confidence: Confidence score
            rule_id: Rule that was used
        """
        low_conf = LowConfidenceExtraction(
            id=str(uuid.uuid4()),
            document_id=document_id,
            extraction_id=extraction_id,
            field_name=field_name,
            extracted_value=extracted_value,
            confidence=confidence,
            rule_id=rule_id,
            created_at=datetime.utcnow(),
        )
        self.low_confidence_extractions.append(low_conf)

        # Auto-trigger mutation if we have enough low-confidence samples
        if len(self.low_confidence_extractions) >= 10:
            await self.generate_mutations()

    async def generate_mutations(self) -> List[RuleMutation]:
        """
        Generate mutations for rules with low performance

        Returns:
            List of generated mutations
        """
        # Analyze low-confidence extractions to identify problem rules
        rule_issues = self._analyze_rule_performance()

        new_mutations = []
        for rule_id, issues in rule_issues.items():
            if rule_id not in self.rules:
                continue

            original_rule = self.rules[rule_id]

            # Generate mutations for this rule
            mutations = await self.mutator.mutate_rule(original_rule, issues)

            for mutated_rule in mutations:
                mutation = RuleMutation(
                    id=str(uuid.uuid4()),
                    original_rule_id=original_rule.id,
                    mutated_rule_id=mutated_rule.id,
                    mutation_type=mutated_rule.metadata.get("mutation_type", "unknown"),
                    mutation_description=mutated_rule.metadata.get("mutation_description", ""),
                    reason=f"Low confidence on {len(issues)} extractions",
                    created_at=datetime.utcnow(),
                )
                new_mutations.append(mutation)
                self.mutations.append(mutation)
                self.rules[mutated_rule.id] = mutated_rule

        # Save mutations to archive
        await self._archive_mutations(new_mutations)

        return new_mutations

    async def score_mutation(
        self, mutation: RuleMutation, test_cases: List[Dict]
    ) -> MutationScore:
        """
        Score a mutation's performance

        Args:
            mutation: RuleMutation object
            test_cases: List of test cases

        Returns:
            MutationScore object
        """
        mutated_rule = self.rules.get(mutation.mutated_rule_id)
        if not mutated_rule:
            raise ValueError(f"Mutated rule {mutation.mutated_rule_id} not found")

        # Score the mutated rule
        score = await self.scorer.score_rule(mutated_rule, test_cases)

        mutation_score = MutationScore(
            mutation_id=mutation.id,
            rule_id=mutation.mutated_rule_id,
            precision=score["precision"],
            recall=score["recall"],
            f1_score=score["f1_score"],
            confidence_improvement=score["confidence_improvement"],
            test_case_count=len(test_cases),
            passed_test_count=score["passed"],
            failed_test_count=score["failed"],
            score_date=datetime.utcnow(),
        )

        # Store test results in mutation
        mutation.test_results = score

        return mutation_score

    async def promote_mutation(self, mutation: RuleMutation):
        """
        Promote a mutation to replace the original rule

        Args:
            mutation: RuleMutation object
        """
        # Mark mutation as applied
        mutation.applied = True
        mutation.applied_at = datetime.utcnow()

        # Deactivate original rule
        original_rule = self.rules.get(mutation.original_rule_id)
        if original_rule:
            original_rule.is_active = False

        # Activate mutated rule
        mutated_rule = self.rules.get(mutation.mutated_rule_id)
        if mutated_rule:
            mutated_rule.is_active = True

        # Record evolution history
        history = EvolutionHistory(
            id=str(uuid.uuid4()),
            rule_id=mutation.mutated_rule_id,
            event_type="promoted",
            description=f"Mutation promoted to replace rule {mutation.original_rule_id}",
            metrics={
                "original_rule_id": mutation.original_rule_id,
                "mutation_id": mutation.id,
            },
            created_at=datetime.utcnow(),
        )

        await self._archive_history(history)

    def _analyze_rule_performance(self) -> Dict[str, List[LowConfidenceExtraction]]:
        """Analyze which rules are underperforming"""
        rule_issues = {}

        for low_conf in self.low_confidence_extractions:
            if low_conf.rule_id not in rule_issues:
                rule_issues[low_conf.rule_id] = []
            rule_issues[low_conf.rule_id].append(low_conf)

        return rule_issues

    async def _archive_mutations(self, mutations: List[RuleMutation]):
        """Archive mutations to versioned files"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = self.evolution_path / f"mutations_{timestamp}.json"

        data = [
            {
                "id": m.id,
                "original_rule_id": m.original_rule_id,
                "mutated_rule_id": m.mutated_rule_id,
                "mutation_type": m.mutation_type,
                "description": m.mutation_description,
                "created_at": m.created_at.isoformat(),
            }
            for m in mutations
        ]

        filename.write_text(json.dumps(data, indent=2))

    async def _archive_history(self, history: EvolutionHistory):
        """Archive evolution history"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = self.evolution_path / f"history_{timestamp}.json"

        data = {
            "id": history.id,
            "rule_id": history.rule_id,
            "event_type": history.event_type,
            "description": history.description,
            "metrics": history.metrics,
            "created_at": history.created_at.isoformat(),
        }

        filename.write_text(json.dumps(data, indent=2))

    def get_active_rules(self) -> List[ExtractionRule]:
        """Get all active rules"""
        return [rule for rule in self.rules.values() if rule.is_active]

    def get_mutation_history(self) -> List[RuleMutation]:
        """Get all mutations"""
        return self.mutations
