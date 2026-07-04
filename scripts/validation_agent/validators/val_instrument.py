"""Instrument Source Audit Gate.

Checks that instruments cited on tract/OGL/WI sheets carry a book/page or
instrument number and that the referenced source document is present (found
locally or retrieved). Missing/unverifiable sources ESCALATE.
"""
from __future__ import annotations

from typing import Any, Dict, List

from validators.base_validator import Validator, make_result, PASS, FAIL, ESCALATE, SEV_MEDIUM, SEV_HIGH


class InstrumentSourceAuditGate(Validator):
    gate_name = "Instrument Source Audit Gate"

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        instruments = context.get("instruments")
        available = {s.get("book_page") for s in context.get("source_documents", [])
                     if s.get("status") in ("found_local", "retrieved")}
        available |= {s.get("instrument_number") for s in context.get("source_documents", [])
                      if s.get("status") in ("found_local", "retrieved")}
        if instruments is None:
            return [make_result(self.gate_name, ESCALATE, severity=SEV_MEDIUM,
                                reason="No instrument list available to audit.",
                                failure_class="Missing Source", confidence=0.4)]
        results: List[Dict[str, Any]] = []
        no_ref = [i for i in instruments if not (i.get("book_page") or i.get("instrument_number"))]
        missing = [(i.get("book_page") or i.get("instrument_number")) for i in instruments
                   if (i.get("book_page") or i.get("instrument_number"))
                   and (i.get("book_page") or i.get("instrument_number")) not in available]
        for inst in no_ref:
            results.append(make_result(
                self.gate_name, FAIL, severity=SEV_MEDIUM,
                affected_subject=inst.get("parties", "?"),
                reason="Instrument has no book/page or instrument number.",
                recommended_action="Add the recording reference from the source image.",
                failure_class="Missing Source", confidence=0.85))
        # Aggregate the (often large) set of un-present source references into a
        # single escalation with an explicit count — nothing silently dropped.
        if missing:
            preview = ", ".join(str(m) for m in missing[:25])
            more = f" (+{len(missing) - 25} more)" if len(missing) > 25 else ""
            results.append(make_result(
                self.gate_name, ESCALATE, severity=SEV_HIGH,
                affected_subject=f"{len(missing)} instruments without a present source document",
                evidence={"count": len(missing), "examples": missing[:25]},
                reason=f"{len(missing)} cited instruments have no source document present. Examples: {preview}{more}.",
                recommended_action="Retrieve/queue these; do not infer their contents.",
                failure_class="Missing Source", confidence=0.9))
        if not results:
            return [make_result(self.gate_name, PASS, severity=SEV_MEDIUM,
                                reason="All cited instruments have a reference and a present source.",
                                confidence=1.0)]
        return results
