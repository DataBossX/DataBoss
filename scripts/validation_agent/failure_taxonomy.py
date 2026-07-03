"""Section 6 -- Failure Taxonomy, encoded as data.

The FailureClassifier consumes this table; validators reference it to tag their
findings.  Keeping it declarative means the taxonomy is the single source of
truth for severity, repairability, routing, and examiner-facing language.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import FailureCategory, Severity


class Route:
    REPAIR_PLANNER = "repair_planner"
    XML_EDITOR = "xml_editor"
    ORCHESTRATOR = "orchestrator"
    HUMAN_ESCALATION = "human_escalation"
    ADMIN_ERROR_QUEUE = "admin_error_queue"


@dataclass(frozen=True)
class TaxonomyEntry:
    category: FailureCategory
    severity: Severity
    repairable: bool
    route: str
    escalate_language: str  # "" when N/A


TAXONOMY: dict[FailureCategory, TaxonomyEntry] = {
    FailureCategory.COMPUTATIONAL_MISMATCH: TaxonomyEntry(
        FailureCategory.COMPUTATIONAL_MISMATCH, Severity.HIGH, True,
        Route.REPAIR_PLANNER, ""),
    FailureCategory.FORMULA_DEFECT: TaxonomyEntry(
        FailureCategory.FORMULA_DEFECT, Severity.MEDIUM, True,
        Route.XML_EDITOR, ""),
    FailureCategory.BROKEN_WORKBOOK_STRUCTURE: TaxonomyEntry(
        FailureCategory.BROKEN_WORKBOOK_STRUCTURE, Severity.FATAL, False,
        Route.ORCHESTRATOR, "Corrupt file structure detected."),
    FailureCategory.MISSING_SOURCE: TaxonomyEntry(
        FailureCategory.MISSING_SOURCE, Severity.HIGH, False,
        Route.HUMAN_ESCALATION, "Material row lacks traceable source document."),
    FailureCategory.UNVERIFIABLE_SOURCE: TaxonomyEntry(
        FailureCategory.UNVERIFIABLE_SOURCE, Severity.HIGH, False,
        Route.HUMAN_ESCALATION, "API retrieval failed; source unverifiable."),
    FailureCategory.SOURCE_LEGAL_MISMATCH: TaxonomyEntry(
        FailureCategory.SOURCE_LEGAL_MISMATCH, Severity.CRITICAL, False,
        Route.HUMAN_ESCALATION,
        "API source document contradicts workbook legal description."),
    FailureCategory.TITLE_CHAIN_GAP: TaxonomyEntry(
        FailureCategory.TITLE_CHAIN_GAP, Severity.CRITICAL, False,
        Route.HUMAN_ESCALATION,
        "Vesting gap detected. Grantor not previously vested."),
    FailureCategory.RESERVATION_CARRY_FORWARD_FAILURE: TaxonomyEntry(
        FailureCategory.RESERVATION_CARRY_FORWARD_FAILURE, Severity.HIGH, False,
        Route.HUMAN_ESCALATION, "Prior reservation dropped from subsequent chain."),
    FailureCategory.OGL_WI_MISMATCH: TaxonomyEntry(
        FailureCategory.OGL_WI_MISMATCH, Severity.HIGH, False,
        Route.HUMAN_ESCALATION, "Lease logic mismatch."),
    FailureCategory.HBP_UNSUPPORTED: TaxonomyEntry(
        FailureCategory.HBP_UNSUPPORTED, Severity.HIGH, False,
        Route.HUMAN_ESCALATION,
        "Active lease beyond primary term lacks production support."),
    FailureCategory.API_SPEND_BLOCKED: TaxonomyEntry(
        FailureCategory.API_SPEND_BLOCKED, Severity.SYSTEM_HIGH, False,
        Route.HUMAN_ESCALATION, "Paid retrieval required but blocked by $100 cap."),
    FailureCategory.SUBPROCESS_DEPENDENCY_FAILURE: TaxonomyEntry(
        FailureCategory.SUBPROCESS_DEPENDENCY_FAILURE, Severity.FATAL, False,
        Route.ADMIN_ERROR_QUEUE, "Subprocess dependency failure."),
    FailureCategory.UNSAFE_LEGAL_INFERENCE: TaxonomyEntry(
        FailureCategory.UNSAFE_LEGAL_INFERENCE, Severity.CRITICAL, False,
        Route.HUMAN_ESCALATION,
        "Automated repair blocked. Cannot fabricate legal facts."),
}


def entry_for(category: FailureCategory) -> TaxonomyEntry:
    return TAXONOMY[category]


def is_repairable(category: FailureCategory) -> bool:
    return TAXONOMY[category].repairable


def escalate_language(category: FailureCategory) -> str:
    return TAXONOMY[category].escalate_language
