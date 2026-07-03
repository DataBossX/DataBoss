"""Failure taxonomy and gate identifiers — shared by the validators and the loop.

The taxonomy is the pivot of the Golden Law. Category A failures are strictly
structural or mathematical and can be repaired by the agent without asserting
any new fact. Category B failures cannot be cleared without a fact the agent is
forbidden to invent, so they halt the loop for the human Examiner.

Keeping this in one module means the validators tag a failure with a category
and the ``TaxonomyRouter`` routes on exactly the same enum — there is no second
place where the A/B boundary could drift.
"""

from __future__ import annotations

from enum import Enum


class Gate(str, Enum):
    """The six quality gates, by their blueprint numbers."""

    INTEREST_CONSERVATION = "Gate 1: Interest Conservation"
    ACREAGE_FOOTING = "Gate 2: Acreage Footing"
    CHAIN_CONTINUITY = "Gate 3: Chain Continuity"
    SOURCE_VERIFICATION = "Gate 4: Source Verification"
    OGL_PARITY = "Gate 5: OGL Parity"
    EXECUTION = "Gate 6: Execution"


class FailureCategory(str, Enum):
    """Failure codes from the blueprint's taxonomy."""

    # Category A — safe automated repair, the loop continues.
    MATH_FOOTING_ERROR = "MATH_FOOTING_ERROR"
    XML_STATE_ERROR = "XML_STATE_ERROR"
    METADATA_MISSING = "METADATA_MISSING"

    # Category B — escalation, the loop halts for the Examiner.
    TITLE_GAP = "TITLE_GAP"
    SOURCE_UNVERIFIED = "SOURCE_UNVERIFIED"
    BUDGET_CAP_REACHED = "BUDGET_CAP_REACHED"


#: Failures the agent may repair on its own without asserting a legal fact.
CATEGORY_A: frozenset[FailureCategory] = frozenset(
    {
        FailureCategory.MATH_FOOTING_ERROR,
        FailureCategory.XML_STATE_ERROR,
        FailureCategory.METADATA_MISSING,
    }
)

#: Failures that require a human decision — the loop must halt.
CATEGORY_B: frozenset[FailureCategory] = frozenset(
    {
        FailureCategory.TITLE_GAP,
        FailureCategory.SOURCE_UNVERIFIED,
        FailureCategory.BUDGET_CAP_REACHED,
    }
)


def is_auto_repairable(category: FailureCategory) -> bool:
    """True for Category A. Anything not explicitly Category A is treated as an
    escalation — the safe default under the Golden Law."""
    return category in CATEGORY_A


def requires_escalation(category: FailureCategory) -> bool:
    """True for Category B (or anything not recognized as Category A)."""
    return not is_auto_repairable(category)
