"""
Instrument Source Audit Gate.

Every recorded instrument referenced in the workbook (Book/Page, instrument
number) should have a corresponding source document. Missing sources are FAIL
(not repairable) and feed the source-retrieval / escalation queues. Contents of
missing instruments are NEVER invented.
"""
from __future__ import annotations

from typing import List, Set

from .base_validator import BaseValidator, ValidationResult, PASS, FAIL, SEV_MED, SEV_HIGH
from .wb_access import find_book_page_refs


class InstrumentValidator(BaseValidator):
    gate_name = "Instrument Source Audit Gate"

    def run(self) -> List[ValidationResult]:
        if not self.workbook_path:
            return [self._result(FAIL, severity=SEV_MED, reason="No workbook path provided")]
        refs = find_book_page_refs(self.workbook_path)
        have: Set[str] = set(self.config.get("available_source_refs", []))
        results: List[ValidationResult] = []
        missing = [r for r in refs if r["reference"] not in have]
        found = [r for r in refs if r["reference"] in have]

        if not missing:
            results.append(self._result(PASS, severity=SEV_MED,
                evidence={"total_referenced": len(refs), "with_source": len(found)},
                reason=f"{len(refs)} instrument references parsed; all have a located source"))
        else:
            # One summary finding (not 200 rows). Full list lives in the missing-doc queue.
            results.append(self._result(FAIL, severity=SEV_HIGH, repairable=False,
                affected_subject=f"{len(missing)} instruments",
                evidence={"total_referenced": len(refs), "with_source": len(found),
                          "missing": len(missing), "sample": [m["reference"] for m in missing[:25]]},
                reason=f"{len(missing)} of {len(refs)} instrument references have no located source document",
                recommended_action="Queue for source retrieval (local -> cache -> OKCounty in live mode); never invent contents",
                confidence=0.95))
        return results
