"""Open-item management (Move #24) — every unresolved matter is tracked,
severity-ranked, and closes only through an explicit resolution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .util import random_id, utcnow_iso

SEVERITIES = ("critical", "high", "medium", "low")
STATUSES = ("open", "in_research", "resolved", "approved")


@dataclass
class OpenItem:
    description: str
    severity: str = "medium"
    affected_tract: str = ""
    affected_conclusion: str = ""      # conclusion_id from the evidence ledger
    required_research: str = ""
    assigned_agent: str = ""
    evidence_reviewed: list = field(default_factory=list)
    status: str = "open"
    resolution: str = ""
    approved_by: str = ""
    issue_id: str = field(default_factory=lambda: random_id("ISS"))
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError(f"unknown severity {self.severity!r}; valid: {SEVERITIES}")
        if self.status not in STATUSES:
            raise ValueError(f"unknown status {self.status!r}; valid: {STATUSES}")


class IssueRegister:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.items: dict[str, OpenItem] = {}
        if self.path.exists():
            for rec in json.loads(self.path.read_text(encoding="utf-8")):
                item = OpenItem(**rec)
                self.items[item.issue_id] = item

    def _save(self) -> None:
        self.path.write_text(
            json.dumps([asdict(i) for i in self.items.values()], indent=2,
                       ensure_ascii=False) + "\n", encoding="utf-8")

    def open_item(self, item: OpenItem) -> str:
        self.items[item.issue_id] = item
        self._save()
        return item.issue_id

    def resolve(self, issue_id: str, resolution: str, approved_by: str = "") -> OpenItem:
        """Resolving requires a stated resolution; 'approved' additionally
        requires a named human approver."""
        item = self.items[issue_id]
        if not resolution.strip():
            raise ValueError("resolution text is required to close an item")
        item.resolution = resolution
        item.status = "approved" if approved_by else "resolved"
        item.approved_by = approved_by
        item.updated_at = utcnow_iso()
        self._save()
        return item

    def open_items(self, severity: str | None = None) -> list[OpenItem]:
        out = [i for i in self.items.values() if i.status in ("open", "in_research")]
        if severity:
            out = [i for i in out if i.severity == severity]
        order = {s: n for n, s in enumerate(SEVERITIES)}
        return sorted(out, key=lambda i: order[i.severity])
