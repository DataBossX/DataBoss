"""The Audit Log -- the engine's trust record.

Every material action the chain / matcher / verifier takes is appended here with
its evidence and, when relevant, a review flag. The log is the answer to "why
does the report say this?" -- it is exported as its own sheet and as the
standalone ``SECTION31_AUDIT_LOG.xlsx`` deliverable.

Timestamps are injected by the caller (the environment forbids wall-clock calls
deep in library code); :func:`AuditLog.stamp` sets the base time once.
"""

from __future__ import annotations

from typing import List, Optional

from .models import AuditEntry


class AuditLog:
    def __init__(self, now_iso: str = ""):
        self._now = now_iso
        self.entries: List[AuditEntry] = []

    def stamp(self, now_iso: str) -> None:
        self._now = now_iso

    def record(self, action: str, *, tract: Optional[str] = None,
               source_sheet: str = "", source_row: Optional[int] = None,
               before: str = "", after: str = "", evidence: str = "",
               flag: str = "") -> AuditEntry:
        entry = AuditEntry(
            timestamp=self._now,
            tract=tract,
            source_sheet=source_sheet,
            source_row=source_row,
            action=action,
            before=str(before),
            after=str(after),
            evidence=evidence,
            flag=flag,
        )
        self.entries.append(entry)
        return entry

    def __len__(self) -> int:
        return len(self.entries)
