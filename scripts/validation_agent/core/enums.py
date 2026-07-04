"""Shared enumerations for states, gate outcomes, severity, and failures."""

from __future__ import annotations

from enum import Enum


class State(str, Enum):
    INIT = "STATE_INIT"
    INGEST = "STATE_INGEST"
    VALIDATE = "STATE_VALIDATE"
    TRIAGE = "STATE_TRIAGE"
    EVALUATE_GATES = "STATE_EVALUATE_GATES"
    REPAIR = "STATE_REPAIR"
    RECALC = "STATE_RECALC"
    ITERATE = "STATE_ITERATE"
    CERTIFY = "STATE_CERTIFY"
    ESCALATE = "STATE_ESCALATE"


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ESCALATE = "ESCALATE"
    SKIP = "SKIP"


class Severity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    FATAL = "FATAL"


class Urgency(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FailureCategory(str, Enum):
    COMPUTATIONAL_MISMATCH = "Computational Mismatch"
    FORMULA_DEFECT = "Formula Defect"
    BROKEN_WORKBOOK_STRUCTURE = "Broken Workbook Structure / XML Corruption"
    MISSING_SOURCE = "Missing Source"
    UNVERIFIABLE_SOURCE = "Unverifiable Source"
    SOURCE_LEGAL_MISMATCH = "Source/Legal Mismatch"
    TITLE_CHAIN_GAP = "Title Chain Gap"
    RESERVATION_CARRY_FORWARD_FAILURE = "Reservation Carry-Forward Failure"
    OGL_MISMATCH_WI_GAP = "OGL Mismatch / WI Assignment Gap"
    HBP_UNSUPPORTED = "HBP Unsupported"
    API_SPEND_BLOCKED = "API Spend Blocked"
    API_AUTH_FAILURE = "API Authentication Failure"
    LIBREOFFICE_FAILURE = "LibreOffice Failure"
    UNSAFE_LEGAL_INFERENCE = "Unsafe Legal Inference"


# Categories that are SAFE to auto-repair (deterministic math / formula / format).
SAFE_REPAIR_CATEGORIES = frozenset(
    {
        FailureCategory.COMPUTATIONAL_MISMATCH,
        FailureCategory.FORMULA_DEFECT,
    }
)

# Categories that MUST escalate and must never trigger an automated repair of
# legal/title/source facts.
UNSAFE_ESCALATION_CATEGORIES = frozenset(
    {
        FailureCategory.MISSING_SOURCE,
        FailureCategory.UNVERIFIABLE_SOURCE,
        FailureCategory.SOURCE_LEGAL_MISMATCH,
        FailureCategory.TITLE_CHAIN_GAP,
        FailureCategory.RESERVATION_CARRY_FORWARD_FAILURE,
        FailureCategory.OGL_MISMATCH_WI_GAP,
        FailureCategory.HBP_UNSUPPORTED,
        FailureCategory.API_SPEND_BLOCKED,
        FailureCategory.API_AUTH_FAILURE,
        FailureCategory.UNSAFE_LEGAL_INFERENCE,
    }
)
