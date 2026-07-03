"""Source Verification Gate.

Confirms that source documents referenced by the run are actually present and
hashed. Missing / unverifiable / blocked-by-spend sources are surfaced (and
escalated) but never fabricated.
"""

from __future__ import annotations

from typing import Any

from .base_validator import BaseValidator, ValidationResult, SEVERITY_MEDIUM


class SourceVerificationValidator(BaseValidator):
    gate_name = "Source Verification Gate"

    def run(self, context: dict) -> list[ValidationResult]:
        docs = context.get("source_documents") or []
        if not docs:
            return [self._pass(
                affected_subject="source verification",
                reason="No source documents required verification.",
            )]
        verified = [d for d in docs if d.get("status") in
                    {"found_local", "retrieved"} and d.get("sha256")]
        unverified = [d for d in docs if d not in verified]
        if not unverified:
            return [self._pass(
                affected_subject="source verification",
                evidence={"verified": len(verified)},
                reason=f"All {len(verified)} source document(s) verified & hashed.",
            )]
        return [self._escalate(
            severity=SEVERITY_MEDIUM, repairable=False,
            affected_subject="source verification",
            evidence={"unverified": unverified, "verified": len(verified)},
            reason=f"{len(unverified)} source document(s) unverified "
                   f"(missing / blocked / unretrieved).",
            recommended_action="Route to source finder or examiner; contents are "
                               "never invented.",
            confidence=0.9,
        )]
