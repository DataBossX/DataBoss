"""Source Verification Gate + Sheet Classification Gate.

Source Verification confirms every queued source document has a terminal, honest
status (found/retrieved/blocked/unavailable) and never a fabricated body.
Sheet Classification escalates low-confidence classifications and fails fatally
if core sheets are missing.
"""
from __future__ import annotations

from typing import Any, Dict, List

from validators.base_validator import (Validator, make_result, PASS, FAIL, ESCALATE,
                                       SEV_FATAL, SEV_MEDIUM, SEV_HIGH)


class SheetClassificationGate(Validator):
    gate_name = "Sheet Classification Gate"

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        classification = (context.get("manifest") or {}).get("classification") or {}
        results: List[Dict[str, Any]] = []
        if classification.get("fatal"):
            for miss in classification.get("missing_core", []):
                results.append(make_result(self.gate_name, ESCALATE, severity=SEV_FATAL,
                    reason=f"Missing core sheet: {miss}",
                    recommended_action="Confirm the correct workbook; core sheets are required.",
                    failure_class="Unsafe Legal Inference", confidence=0.9))
        for c in classification.get("sheets", []):
            if c.get("needs_escalation"):
                results.append(make_result(self.gate_name, ESCALATE, severity=SEV_MEDIUM,
                    affected_sheet=c.get("sheet"),
                    evidence={"confidence": c.get("confidence"), "category": c.get("category")},
                    reason="Low-confidence sheet classification — not guessed.",
                    recommended_action="Examiner to confirm sheet role.",
                    failure_class="Unsafe Legal Inference", confidence=c.get("confidence", 0.4)))
        if not results:
            return [make_result(self.gate_name, PASS, severity=SEV_MEDIUM,
                                reason="All sheets classified with adequate confidence; core sheets present.",
                                confidence=0.9)]
        return results


class SourceVerificationGate(Validator):
    gate_name = "Source Verification Gate"

    TERMINAL = {"found_local", "retrieved", "blocked", "unavailable"}

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        docs = context.get("source_documents", [])
        open_docs = [d for d in docs if d.get("status") in ("blocked", "unavailable", "queued")]
        results: List[Dict[str, Any]] = []
        if open_docs:
            refs = [d.get("book_page") or d.get("instrument_number") or "?" for d in open_docs]
            preview = ", ".join(str(r) for r in refs[:25])
            more = f" (+{len(refs) - 25} more)" if len(refs) > 25 else ""
            results.append(make_result(self.gate_name, ESCALATE, severity=SEV_HIGH,
                affected_subject=f"{len(open_docs)} source documents unverified",
                evidence={"count": len(open_docs), "examples": refs[:25]},
                reason=(f"{len(open_docs)} source documents are unverified (contents NOT known). "
                        f"Examples: {preview}{more}."),
                recommended_action="Retrieve lawfully or escalate; never infer contents.",
                failure_class="Unverifiable Source", confidence=0.9))
        if not results:
            return [make_result(self.gate_name, PASS, severity=SEV_MEDIUM,
                                reason="All source documents are present and verified.", confidence=0.9)]
        return results
