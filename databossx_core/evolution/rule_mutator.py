"""
Rule mutator - generates improved versions of extraction rules
"""

import uuid
import re
from datetime import datetime
from typing import List

from ..models.evolution import ExtractionRule, LowConfidenceExtraction


class RuleMutator:
    """
    Generates mutations of extraction rules to improve performance
    """

    async def mutate_rule(
        self,
        original_rule: ExtractionRule,
        failed_extractions: List[LowConfidenceExtraction],
    ) -> List[ExtractionRule]:
        """
        Generate mutations of a rule

        Args:
            original_rule: Original extraction rule
            failed_extractions: List of failed extractions

        Returns:
            List of mutated rules
        """
        mutations = []

        if original_rule.rule_type == "regex":
            # Generate regex mutations
            mutations.extend(await self._mutate_regex(original_rule, failed_extractions))
        elif original_rule.rule_type == "llm_prompt":
            # Generate prompt mutations
            mutations.extend(await self._mutate_prompt(original_rule, failed_extractions))

        return mutations

    async def _mutate_regex(
        self,
        rule: ExtractionRule,
        failed: List[LowConfidenceExtraction],
    ) -> List[ExtractionRule]:
        """Generate regex pattern mutations"""
        mutations = []

        # Mutation 1: Make pattern more permissive (add optional whitespace)
        permissive_pattern = rule.pattern.replace(r"\s+", r"\s*")
        if permissive_pattern != rule.pattern:
            mutations.append(
                self._create_mutated_rule(
                    rule,
                    permissive_pattern,
                    "pattern_refinement",
                    "Made whitespace matching more permissive",
                )
            )

        # Mutation 2: Add case-insensitive flag if not present
        if "(?i)" not in rule.pattern and "re.IGNORECASE" not in rule.metadata.get("flags", ""):
            case_insensitive = f"(?i){rule.pattern}"
            mutations.append(
                self._create_mutated_rule(
                    rule,
                    case_insensitive,
                    "pattern_refinement",
                    "Added case-insensitive matching",
                )
            )

        # Mutation 3: Expand character classes
        expanded = rule.pattern.replace(r"[A-Z]", r"[A-Za-z]")
        if expanded != rule.pattern:
            mutations.append(
                self._create_mutated_rule(
                    rule,
                    expanded,
                    "pattern_refinement",
                    "Expanded character classes to include more variations",
                )
            )

        return mutations

    async def _mutate_prompt(
        self,
        rule: ExtractionRule,
        failed: List[LowConfidenceExtraction],
    ) -> List[ExtractionRule]:
        """Generate LLM prompt mutations"""
        mutations = []

        # Mutation 1: Add more specific instructions
        enhanced_prompt = rule.pattern + "\n\nIMPORTANT: Be very precise and include confidence scores."
        mutations.append(
            self._create_mutated_rule(
                rule,
                enhanced_prompt,
                "prompt_enhancement",
                "Added precision instructions",
            )
        )

        # Mutation 2: Add examples from failed cases
        if failed:
            examples = "\n\nExamples to handle:\n"
            for f in failed[:3]:  # Use up to 3 examples
                examples += f"- {f.extracted_value}\n"

            prompt_with_examples = rule.pattern + examples
            mutations.append(
                self._create_mutated_rule(
                    rule,
                    prompt_with_examples,
                    "prompt_enhancement",
                    "Added examples from difficult cases",
                )
            )

        return mutations

    def _create_mutated_rule(
        self,
        original: ExtractionRule,
        new_pattern: str,
        mutation_type: str,
        description: str,
    ) -> ExtractionRule:
        """Create a mutated rule"""
        return ExtractionRule(
            id=str(uuid.uuid4()),
            rule_name=f"{original.rule_name}_mutated_{mutation_type}",
            rule_type=original.rule_type,
            pattern=new_pattern,
            target_field=original.target_field,
            confidence_threshold=original.confidence_threshold,
            version=original.version + 1,
            parent_rule_id=original.id,
            created_at=datetime.utcnow(),
            is_active=False,  # Mutations start inactive
            metadata={
                "mutation_type": mutation_type,
                "mutation_description": description,
                "parent_rule": original.id,
            },
        )
