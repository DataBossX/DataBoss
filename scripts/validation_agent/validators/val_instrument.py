"""Instrument Source Audit Gate.

Every instrument reference (book/page or instrument number) cited in the
workbook must have a corresponding source document. References without a
verified source are ESCALATED (added to the missing-source queue); their
contents are never invented.
"""

from __future__ import annotations

from typing import Any

from .base_validator import BaseValidator, ValidationResult, SEVERITY_MEDIUM


def audit_instruments(references: list[dict], known_sources: set[str]) -> dict:
    """Compare cited instrument references to available source doc keys."""
    missing: list[dict] = []
    present: list[dict] = []
    for ref in references:
        key = str(ref.get("reference_key", "")).strip().lower()
        if key and key in known_sources:
            present.append(ref)
        else:
            missing.append(ref)
    return {
        "total": len(references),
        "present": len(present),
        "missing": missing,
        "complete": not missing,
    }


class InstrumentSourceAuditValidator(BaseValidator):
    gate_name = "Instrument Source Audit Gate"

    def run(self, context: dict) -> list[ValidationResult]:
        refs = context.get("instrument_references") or []
        known = {
            str(k).strip().lower()
            for k in (context.get("known_source_keys") or [])
        }
        if not refs:
            return [self._pass(
                affected_subject="instrument sources",
                reason="No instrument references cited to audit.",
            )]
        report = audit_instruments(refs, known)
        if report["complete"]:
            return [self._pass(
                affected_subject="instrument sources", evidence=report,
                reason=f"All {report['total']} instrument references are sourced.",
            )]
        return [self._escalate(
            severity=SEVERITY_MEDIUM, repairable=False,
            affected_subject="instrument sources", evidence=report,
            reason=f"{len(report['missing'])} instrument reference(s) lack a "
                   f"verified source document.",
            recommended_action="Route to source finder / examiner. Do not "
                               "fabricate instrument contents.",
            confidence=0.9,
        )]
