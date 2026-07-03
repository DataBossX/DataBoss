"""Failure taxonomy classifier.

Maps a validation result to a failure category and decides whether it is
SAFE to auto-repair or MUST be escalated to a human examiner. Every unsafe
legal / title / source problem routes to escalation.
"""

from __future__ import annotations

from dataclasses import dataclass

# Taxonomy categories.
COMPUTATIONAL_MISMATCH = "Computational Mismatch"
FORMULA_DEFECT = "Formula Defect"
BROKEN_STRUCTURE = "Broken Workbook Structure / XML Corruption"
MISSING_SOURCE = "Missing Source"
UNVERIFIABLE_SOURCE = "Unverifiable Source"
SOURCE_LEGAL_MISMATCH = "Source/Legal Mismatch"
TITLE_CHAIN_GAP = "Title Chain Gap"
RESERVATION_CARRY_FORWARD = "Reservation Carry-Forward Failure"
OGL_WI_GAP = "OGL Mismatch / WI Assignment Gap"
HBP_UNSUPPORTED = "HBP Unsupported"
API_SPEND_BLOCKED = "API Spend Blocked"
API_AUTH_FAILURE = "API Authentication Failure"
LIBREOFFICE_FAILURE = "LibreOffice Failure"
UNSAFE_LEGAL_INFERENCE = "Unsafe Legal Inference"

# Categories that are NEVER auto-repaired.
UNSAFE_CATEGORIES = {
    MISSING_SOURCE, UNVERIFIABLE_SOURCE, SOURCE_LEGAL_MISMATCH,
    TITLE_CHAIN_GAP, RESERVATION_CARRY_FORWARD, OGL_WI_GAP, HBP_UNSUPPORTED,
    UNSAFE_LEGAL_INFERENCE, COMPUTATIONAL_MISMATCH,
}

# Categories that MAY be auto-repaired when evidence is exact.
SAFE_REPAIR_CATEGORIES = {FORMULA_DEFECT}


@dataclass
class Triage:
    category: str
    repairable: bool
    escalate: bool
    rationale: str


_GATE_TO_CATEGORY = {
    "Workbook Integrity Gate": BROKEN_STRUCTURE,
    "Sheet Classification Gate": UNSAFE_LEGAL_INFERENCE,
    "Interest Conservation Gate": COMPUTATIONAL_MISMATCH,
    "Acreage Footing Gate": COMPUTATIONAL_MISMATCH,
    "Chain Continuity Gate": TITLE_CHAIN_GAP,
    "Instrument Source Audit Gate": MISSING_SOURCE,
    "OGL Register Audit Gate": OGL_WI_GAP,
    "WI/Depth Consistency Gate": OGL_WI_GAP,
    "Well/HBP Support Gate": HBP_UNSUPPORTED,
    "Formula Integrity Gate": FORMULA_DEFECT,
    "Source Verification Gate": UNVERIFIABLE_SOURCE,
}


def classify(result: dict) -> Triage:
    """Classify a single validation result dict into a Triage decision."""
    gate = result.get("gate_name", "")
    category = _GATE_TO_CATEGORY.get(gate, UNSAFE_LEGAL_INFERENCE)

    # Structural corruption is repairable via safe XML rebuild ONLY if the
    # validator flagged it repairable; otherwise escalate.
    if category == BROKEN_STRUCTURE:
        repairable = bool(result.get("repairable"))
        return Triage(category, repairable, not repairable,
                      "Structural corruption: safe rebuild only if reversible.")

    if category == FORMULA_DEFECT:
        repairable = bool(result.get("repairable"))
        return Triage(
            category, repairable, not repairable,
            "Formula defect is repairable only when the exact intended formula "
            "is known from adjacent cells / template / prior version.",
        )

    # Everything else that is failing/escalating is unsafe to auto-repair.
    return Triage(category, False, True,
                  f"{category} requires human examiner judgment; never "
                  f"auto-repaired.")
