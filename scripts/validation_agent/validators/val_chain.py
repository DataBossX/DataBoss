"""
Chain Continuity Gate.

Detects title-chain gaps (undetermined owners, missing vesting, heirship-only
vesting, unresolved reservations). These are ALWAYS escalated to the human
examiner — never auto-repaired — because they are legal/title judgments.
"""
from __future__ import annotations

from typing import List

from .base_validator import BaseValidator, ValidationResult, PASS, ESCALATE, SEV_HIGH, SEV_MED
from .wb_access import scan_for_markers

GAP_MARKERS = [
    "undetermined of record", "owners undetermined", "vesting instrument not located",
    "not located of record", "chain over-conveys", "balance of tract",
    "estate/succession not of record", "by affidavit only", "affidavit of heirship",
    "probate", "not judicially determined", "operative base lease not determined",
    "unresolved conveyances",
]


class ChainValidator(BaseValidator):
    gate_name = "Chain Continuity Gate"

    def run(self) -> List[ValidationResult]:
        if not self.workbook_path:
            return [self._result(ESCALATE, severity=SEV_MED, reason="No workbook path provided")]
        hits = scan_for_markers(self.workbook_path, GAP_MARKERS)
        if not hits:
            return [self._result(PASS, severity=SEV_MED,
                                 reason="No chain-gap markers detected")]
        results: List[ValidationResult] = []
        # Group by sheet for readability.
        seen = set()
        for h in hits:
            key = (h["sheet"], h["marker"])
            if key in seen:
                continue
            seen.add(key)
            results.append(self._result(ESCALATE, severity=SEV_HIGH, repairable=False,
                affected_sheet=h["sheet"], affected_cell_or_range=h["cell"],
                affected_subject=h["marker"],
                evidence={"text": h["text"]},
                reason=f"Chain gap / unverified vesting: '{h['marker']}'",
                recommended_action="Human examiner: obtain vesting/probate/heirship curative; do not auto-repair",
                confidence=0.9))
        return results
