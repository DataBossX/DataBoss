"""Structured, append-only audit logging for the Horizon Command Center.

Every meaningful action (scan, dedup move, validation gate, repair, version
write, escalation) is appended to ``horizon_audit.log`` as a timestamped line
*and* mirrored to an in-memory list so orchestration/tests can assert on it.

The log is append-only and never rewrites history -- consistent with the
Zero-Destruction law.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class AuditEvent:
    ts: _dt.datetime
    level: str
    action: str
    detail: str

    def format(self) -> str:
        return (
            f"{self.ts:%Y-%m-%d %H:%M:%S} | {self.level:8s} | "
            f"{self.action:22s} | {self.detail}"
        )


class AuditLog:
    """Append-only audit trail.

    Accepts a ``clock`` callable so tests get deterministic timestamps and so we
    never depend on wall-clock behaviour that would be non-reproducible.
    """

    def __init__(self, path: Optional[Path] = None, clock=_dt.datetime.now, echo: bool = True) -> None:
        self.path = Path(path) if path is not None else None
        self._clock = clock
        self._echo = echo
        self.events: List[AuditEvent] = []
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, action: str, detail: str = "", level: str = "INFO") -> AuditEvent:
        event = AuditEvent(ts=self._clock(), level=level.upper(), action=action, detail=detail)
        self.events.append(event)
        line = event.format()
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        if self._echo:
            print(line)
        return event

    # convenience wrappers -------------------------------------------------
    def info(self, action: str, detail: str = "") -> AuditEvent:
        return self.record(action, detail, "INFO")

    def warn(self, action: str, detail: str = "") -> AuditEvent:
        return self.record(action, detail, "WARN")

    def error(self, action: str, detail: str = "") -> AuditEvent:
        return self.record(action, detail, "ERROR")

    def escalate(self, action: str, detail: str = "") -> AuditEvent:
        """Flag an unsupported fact / missing document. Never guess -- escalate."""
        return self.record(action, detail, "ESCALATED")

    def examiner_review(self, action: str, detail: str = "") -> AuditEvent:
        return self.record(action, detail, "REVIEW")

    def count(self, level: str) -> int:
        level = level.upper()
        return sum(1 for e in self.events if e.level == level)
