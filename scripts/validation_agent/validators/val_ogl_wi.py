"""OGL Register Audit, WI/Depth Consistency, and Well/HBP Support gates.

These gates check structural completeness of the OGL register, consistency of
working-interest/depth assignments, and whether HBP (held-by-production)
claims are supported by well evidence. Any unsupported HBP claim, WI assignment
gap, or OGL mismatch that requires a legal inference is ESCALATED.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .base_validator import BaseValidator, ValidationResult, SEVERITY_MEDIUM, SEVERITY_HIGH


class OGLRegisterAuditValidator(BaseValidator):
    gate_name = "OGL Register Audit Gate"

    REQUIRED_FIELDS = ("lessor", "lessee", "date", "book_page", "royalty")

    def run(self, context: dict) -> list[ValidationResult]:
        leases = context.get("ogl_records")
        if leases is None:
            return [self._escalate(
                severity=SEVERITY_HIGH, affected_subject="OGL register",
                reason="OGL register not found or unreadable.",
                recommended_action="Examiner must confirm OGL register sheet.",
                confidence=0.9,
            )]
        incomplete = []
        for i, lease in enumerate(leases):
            missing = [f for f in self.REQUIRED_FIELDS if not lease.get(f)]
            if missing:
                incomplete.append({"index": i, "missing": missing,
                                   "lease": lease})
        if not incomplete:
            return [self._pass(
                affected_subject="OGL register",
                reason=f"OGL register complete for {len(leases)} lease(s).",
            )]
        return [self._escalate(
            severity=SEVERITY_MEDIUM, repairable=False,
            affected_subject="OGL register", evidence={"incomplete": incomplete},
            reason=f"{len(incomplete)} OGL record(s) missing required fields.",
            recommended_action="Examiner must complete lease facts from sources; "
                               "never invented.",
            confidence=0.9,
        )]


class WIDepthConsistencyValidator(BaseValidator):
    gate_name = "WI/Depth Consistency Gate"

    def run(self, context: dict) -> list[ValidationResult]:
        assignments = context.get("wi_assignments")
        if assignments is None:
            return [self._escalate(
                severity=SEVERITY_HIGH, affected_subject="working interest",
                reason="Working-interest sheet not found or unreadable.",
                recommended_action="Examiner must confirm WI sheet.",
                confidence=0.9,
            )]
        issues = []
        for i, a in enumerate(assignments):
            # WI must be present and depth interval well-formed.
            if a.get("wi") in (None, ""):
                issues.append({"index": i, "issue": "missing_wi", "row": a})
                continue
            top = a.get("depth_top")
            base = a.get("depth_base")
            if top is not None and base is not None:
                try:
                    if Decimal(str(top)) > Decimal(str(base)):
                        issues.append({"index": i, "issue": "inverted_depth",
                                       "row": a})
                except Exception:
                    issues.append({"index": i, "issue": "bad_depth", "row": a})
        if not issues:
            return [self._pass(
                affected_subject="working interest",
                reason=f"WI/depth consistent across {len(assignments)} row(s).",
            )]
        return [self._escalate(
            severity=SEVERITY_MEDIUM, repairable=False,
            affected_subject="working interest", evidence={"issues": issues},
            reason=f"{len(issues)} WI/depth assignment issue(s) detected.",
            recommended_action="Examiner must resolve WI assignment gaps.",
            confidence=0.88,
        )]


class WellHBPSupportValidator(BaseValidator):
    gate_name = "Well/HBP Support Gate"

    def run(self, context: dict) -> list[ValidationResult]:
        hbp_claims = context.get("hbp_claims")
        wells = context.get("wells") or []
        if hbp_claims is None:
            return [self._pass(
                affected_subject="HBP support",
                reason="No HBP claims asserted to verify.",
            )]
        producing_apis = {
            str(w.get("api")).strip()
            for w in wells if str(w.get("status", "")).lower() in
            {"producing", "active", "hbp"}
        }
        unsupported = []
        for c in hbp_claims:
            api = str(c.get("api", "")).strip()
            if not api or api not in producing_apis:
                unsupported.append(c)
        if not unsupported:
            return [self._pass(
                affected_subject="HBP support",
                reason="All HBP claims are supported by producing wells.",
            )]
        return [self._escalate(
            severity=SEVERITY_HIGH, repairable=False,
            affected_subject="HBP support", evidence={"unsupported": unsupported},
            reason=f"{len(unsupported)} HBP claim(s) lack producing-well support.",
            recommended_action="Examiner must verify HBP with well records; "
                               "unsupported HBP is never auto-certified.",
            confidence=0.92,
        )]
