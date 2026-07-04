"""
Source Verification Gate.

Cross-checks instrument references against source documents that are actually
available (located locally or retrieved). In dry-run with nothing available,
missing sources ESCALATE rather than fail the whole run. Never invents content.
"""
from __future__ import annotations

from typing import List, Set

from .base_validator import BaseValidator, ValidationResult, PASS, ESCALATE, SEV_MED, SEV_HIGH
from .wb_access import find_book_page_refs


class SourceValidator(BaseValidator):
    gate_name = "Source Verification Gate"

    def run(self) -> List[ValidationResult]:
        if not self.workbook_path:
            return [self._result(ESCALATE, severity=SEV_MED, reason="No workbook path provided")]
        refs = find_book_page_refs(self.workbook_path)
        available: Set[str] = set(self.config.get("available_source_refs", []))
        missing = [r["reference"] for r in refs if r["reference"] not in available]
        if not refs:
            return [self._result(PASS, severity=SEV_MED, reason="No instrument references to verify")]
        if not missing:
            return [self._result(PASS, severity=SEV_MED,
                evidence={"verified": len(refs)},
                reason=f"All {len(refs)} referenced instruments have a source")]
        return [self._result(ESCALATE, severity=SEV_HIGH, repairable=False,
            evidence={"referenced": len(refs), "missing": len(missing),
                      "sample_missing": missing[:25]},
            reason=f"{len(missing)} of {len(refs)} instruments lack a verified source",
            recommended_action="Build missing-source queue; retrieve via local/cache/OKCounty (live). Never invent.",
            confidence=0.95)]
