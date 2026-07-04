"""
Failure taxonomy classifier.

Maps validation results to a fixed taxonomy and decides the routing:
  * SAFE_REPAIR  — deterministic, intended-state-known formula/format/math fixes
  * ESCALATE     — any legal / title / source / HBP judgment
  * BLOCKED      — spend cap / auth / dependency failures
Legal/title/source problems can NEVER be routed to SAFE_REPAIR.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


class FailureType(str, Enum):
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


class Routing(str, Enum):
    SAFE_REPAIR = "SAFE_REPAIR"
    ESCALATE = "ESCALATE"
    BLOCKED = "BLOCKED"


# Legal/title/source types are always escalated, never auto-repaired.
NEVER_REPAIR = {
    FailureType.MISSING_SOURCE, FailureType.UNVERIFIABLE_SOURCE,
    FailureType.SOURCE_LEGAL_MISMATCH, FailureType.TITLE_CHAIN_GAP,
    FailureType.RESERVATION_CARRY_FORWARD, FailureType.OGL_WI_GAP,
    FailureType.HBP_UNSUPPORTED, FailureType.UNSAFE_LEGAL_INFERENCE,
    FailureType.BROKEN_STRUCTURE,
}
BLOCKED_TYPES = {FailureType.API_SPEND_BLOCKED, FailureType.API_AUTH_FAILURE,
                 FailureType.LIBREOFFICE_FAILURE}


@dataclass
class Triage:
    failure_type: FailureType
    routing: Routing
    gate_name: str
    reason: str
    subject: str = ""
    affected_sheet: str = ""
    affected_range: str = ""


def classify(result) -> Triage:
    """Classify a single ValidationResult (duck-typed: .gate_name/.reason/.repairable/.status)."""
    gate = (getattr(result, "gate_name", "") or "").lower()
    reason = (getattr(result, "reason", "") or "").lower()
    repairable = bool(getattr(result, "repairable", False))

    # Explicit signals in the reason text take priority.
    if "over-conveyance" in reason or "under-conveyance" in reason or "residual" in reason:
        ft = FailureType.COMPUTATIONAL_MISMATCH
    elif "hard-coded value where a sum" in reason or ("formula" in gate and repairable):
        ft = FailureType.FORMULA_DEFECT
    elif "corrupt" in reason or "integrity" in gate and "fail" in reason:
        ft = FailureType.BROKEN_STRUCTURE
    elif "no source" in reason or "lack a verified source" in reason or "missing source" in reason:
        ft = FailureType.MISSING_SOURCE
    elif "chain gap" in reason or "vesting" in reason or "unresolved conveyances" in reason:
        ft = FailureType.TITLE_CHAIN_GAP
    elif "hbp" in reason or "held-by-production" in reason or "recital" in reason:
        ft = FailureType.HBP_UNSUPPORTED
    elif "wi/nri" in reason or "assignment" in reason or "depth" in reason:
        ft = FailureType.OGL_WI_GAP
    elif "reservation" in reason:
        ft = FailureType.RESERVATION_CARRY_FORWARD
    elif "spend" in reason or "cap" in reason:
        ft = FailureType.API_SPEND_BLOCKED
    elif "auth" in reason or "credential" in reason:
        ft = FailureType.API_AUTH_FAILURE
    elif "libreoffice" in reason:
        ft = FailureType.LIBREOFFICE_FAILURE
    else:
        ft = FailureType.UNSAFE_LEGAL_INFERENCE

    # Decide routing. NEVER_REPAIR/legal wins over any 'repairable' flag.
    if ft in BLOCKED_TYPES:
        routing = Routing.BLOCKED
    elif ft in NEVER_REPAIR:
        routing = Routing.ESCALATE
    elif ft in (FailureType.FORMULA_DEFECT, FailureType.COMPUTATIONAL_MISMATCH) and repairable:
        routing = Routing.SAFE_REPAIR
    else:
        routing = Routing.ESCALATE

    return Triage(ft, routing, getattr(result, "gate_name", ""),
                  getattr(result, "reason", ""),
                  subject=getattr(result, "affected_subject", "") or "",
                  affected_sheet=getattr(result, "affected_sheet", "") or "",
                  affected_range=getattr(result, "affected_cell_or_range", "") or "")


def triage_all(results) -> List[Triage]:
    return [classify(r) for r in results if getattr(r, "status", "PASS") in ("FAIL", "ESCALATE", "ERROR")]
