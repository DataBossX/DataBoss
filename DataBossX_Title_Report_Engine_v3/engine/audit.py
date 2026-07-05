"""Task 15 -- build the audit log from chain events.

Every material chain event becomes one auditable row: before/conveyed/after/
retained acres, evidence citation, assumption, flag, confidence. Written both as
a sheet in the final workbook and as a standalone log file.
"""

from __future__ import annotations

from typing import List

from .models import AuditEntry, TractResult
from .utils import now_stamp

AUDIT_COLUMNS = [
    "timestamp", "tract", "source_file", "source_sheet", "source_row",
    "instrument_type", "grantor", "grantee", "action", "before_acres",
    "conveyed_acres", "after_acres", "retained_acres", "ogl_reference",
    "assn_reference", "evidence", "assumption", "flag", "confidence", "notes",
]


def build_audit(results: List[TractResult]) -> List[AuditEntry]:
    stamp = now_stamp()
    entries: List[AuditEntry] = []
    for res in results:
        # assumption text keyed by tract for annotation
        assn_text = "; ".join(a.statement for a in res.assumptions)
        for ev in res.events:
            entries.append(AuditEntry(
                timestamp=stamp, tract=ev.tract,
                source_file=_src_file(ev.evidence),
                source_sheet=_src_sheet(ev.evidence),
                source_row=_src_row(ev.evidence),
                instrument_type=ev.instrument_type,
                grantor=ev.grantor, grantee=ev.grantee, action=ev.action,
                before_acres=ev.before_acres, conveyed_acres=ev.conveyed_acres,
                after_acres=ev.after_acres, retained_acres=ev.retained_acres,
                ogl_reference=ev.ogl_reference, assn_reference=ev.assn_reference,
                evidence=ev.evidence,
                assumption=ev.assumption or (assn_text if ev.seq == 1 else ""),
                flag=ev.flag, confidence=ev.confidence, notes=ev.notes,
            ))
    return entries


def _src_file(ev: str) -> str:
    return ev.split("#", 1)[0] if "#" in ev else ev


def _src_sheet(ev: str) -> str:
    if "#" in ev and "!" in ev:
        return ev.split("#", 1)[1].split("!", 1)[0]
    return ""


def _src_row(ev: str):
    if "!row" in ev:
        try:
            return int(ev.split("!row", 1)[1])
        except ValueError:
            return None
    return None
