"""Validator framework: typed result objects and a common contract.

Every gate returns one or more result dicts with a fixed shape so the audit
logger, orchestrator and reports can consume them uniformly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Status + severity vocabularies.
PASS, FAIL, ESCALATE, ERROR = "PASS", "FAIL", "ESCALATE", "ERROR"
SEV_INFO, SEV_LOW, SEV_MEDIUM, SEV_HIGH, SEV_FATAL = "INFO", "LOW", "MEDIUM", "HIGH", "FATAL"

# Failure classes that are NEVER auto-repaired — they route to a human examiner.
UNSAFE_LEGAL_CLASSES = {
    "Missing Source", "Unverifiable Source", "Source/Legal Mismatch",
    "Title Chain Gap", "Reservation Carry-Forward Failure",
    "OGL Mismatch / WI Assignment Gap", "HBP Unsupported", "Unsafe Legal Inference",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def make_result(gate_name: str, status: str, *, severity: str = SEV_MEDIUM,
                repairable: bool = False, affected_sheet: Optional[str] = None,
                affected_cell_or_range: Optional[str] = None, affected_subject: Optional[str] = None,
                evidence: Any = None, reason: str = "", recommended_action: str = "",
                confidence: float = 1.0, failure_class: Optional[str] = None) -> Dict[str, Any]:
    # Legal/title/source problems can never be marked repairable.
    if failure_class in UNSAFE_LEGAL_CLASSES:
        repairable = False
    return {
        "gate_name": gate_name,
        "status": status,
        "severity": severity,
        "repairable": bool(repairable),
        "affected_sheet": affected_sheet,
        "affected_cell_or_range": affected_cell_or_range,
        "affected_subject": affected_subject,
        "evidence": evidence,
        "reason": reason,
        "recommended_action": recommended_action,
        "confidence": float(confidence),
        "failure_class": failure_class,
        "created_at": _now(),
    }


class Validator:
    """Base class. Subclasses implement :meth:`run` and return a list of results."""

    gate_name = "UnnamedGate"

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError
