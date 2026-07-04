"""Failure taxonomy classifier.

Maps a validation result to a failure class and decides whether it is on the
SAFE auto-repair path or the HUMAN escalation path. Legal/title/source problems
are always escalation-only.
"""
from __future__ import annotations

from typing import Any, Dict

from validators.base_validator import UNSAFE_LEGAL_CLASSES

SAFE_REPAIR_CLASSES = {"Formula Defect", "Computational Mismatch"}

ALL_CLASSES = sorted(SAFE_REPAIR_CLASSES | UNSAFE_LEGAL_CLASSES | {
    "Broken Workbook Structure / XML Corruption", "API Spend Blocked",
    "API Authentication Failure", "LibreOffice Failure",
})


def classify(result: Dict[str, Any]) -> Dict[str, Any]:
    fclass = result.get("failure_class") or "Computational Mismatch"
    # A computational mismatch that is actually an overconveyance is a title gap.
    safe = fclass in SAFE_REPAIR_CLASSES and bool(result.get("repairable"))
    if fclass in UNSAFE_LEGAL_CLASSES:
        safe = False
    return {
        "failure_class": fclass,
        "route": "repair" if safe else "escalate",
        "auto_repairable": safe,
        "reason": result.get("reason", ""),
    }
