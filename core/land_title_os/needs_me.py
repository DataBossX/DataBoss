""""What needs me?" queue (Move #74) — the single list of decisions only a
human can make, aggregated across every project.

Sources:
- each project manifest's ``open_issues``
- each project's issue register (``issues.json``) open/in-research items
- each project's evidence ledger (``evidence.jsonl``) conclusions not yet
  human-verified
- promotion state (``promotion_state.json``): files parked at QA awaiting a
  human APPROVED/DELIVERED decision
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .evidence import EvidenceLedger
from .issues import IssueRegister
from .manifest import ProjectManifest, find_manifests

_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "": 4}


@dataclass
class NeedsMeItem:
    project: str
    source: str          # manifest | issues | evidence | promotion
    severity: str
    description: str


def collect(projects_root: str | Path) -> list[NeedsMeItem]:
    items: list[NeedsMeItem] = []
    for manifest_path in find_manifests(projects_root):
        project_dir = manifest_path.parent
        m = ProjectManifest.load(manifest_path)

        for issue in m.open_issues:
            if isinstance(issue, dict):
                items.append(NeedsMeItem(m.project_id, "manifest",
                                         issue.get("severity", ""), issue.get("description", "")))
            else:
                items.append(NeedsMeItem(m.project_id, "manifest", "", str(issue)))

        issues_path = project_dir / "issues.json"
        if issues_path.exists():
            for item in IssueRegister(issues_path).open_items():
                items.append(NeedsMeItem(m.project_id, "issues", item.severity,
                                         item.description))

        ledger_path = project_dir / "evidence.jsonl"
        if ledger_path.exists():
            for c in EvidenceLedger(ledger_path).unverified_conclusions():
                items.append(NeedsMeItem(m.project_id, "evidence", "high",
                                         f"conclusion awaiting human verification: {c.statement}"))

        promo_path = project_dir / "promotion_state.json"
        if promo_path.exists():
            state = json.loads(promo_path.read_text(encoding="utf-8"))
            for path, rec in state.items():
                if rec.get("stage") == "QA":
                    items.append(NeedsMeItem(m.project_id, "promotion", "high",
                                             f"file passed QA, awaiting human APPROVED: {path}"))

    items.sort(key=lambda i: (_SEV_ORDER.get(i.severity, 4), i.project))
    return items


def render(items: list[NeedsMeItem]) -> str:
    if not items:
        return "Nothing needs you. All tracked decisions are resolved."
    lines = [f"WHAT NEEDS YOU — {len(items)} item(s)", ""]
    for i in items:
        sev = (i.severity or "info").upper()
        lines.append(f"[{sev:>8}] {i.project} ({i.source})")
        lines.append(f"           {i.description}")
    return "\n".join(lines)
