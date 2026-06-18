"""Confidence gating for DataBossX title extraction.

Low confidence -> "Needs Human Review". This is conservative by design: the
default threshold is high because title facts are high-stakes.
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_THRESHOLD = 0.85

STATUS_AUTO = "Auto-Suggested"          # high confidence, still human-reviewed downstream
STATUS_NEEDS_REVIEW = "Needs Human Review"  # low confidence or uncertain fields present
STATUS_BLOCKED = "Blocked - Invalid OCR"    # failed schema validation


@dataclass
class GateDecision:
    status: str
    confidence: float
    reason: str


def decide(result: dict, *, valid: bool, threshold: float = DEFAULT_THRESHOLD) -> GateDecision:
    if not valid:
        return GateDecision(STATUS_BLOCKED, 0.0, "OCR result failed schema validation")
    conf = float(result.get("confidence", 0.0))
    uncertain = result.get("uncertain_fields") or []
    if conf < threshold:
        return GateDecision(STATUS_NEEDS_REVIEW, conf, f"confidence {conf:.2f} < {threshold:.2f}")
    if uncertain:
        return GateDecision(STATUS_NEEDS_REVIEW, conf, f"uncertain fields: {', '.join(map(str, uncertain))}")
    return GateDecision(STATUS_AUTO, conf, "confidence above threshold, no uncertain fields")
