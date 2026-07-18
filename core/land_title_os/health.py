"""Project health scoring (Move #77) and factual client-status reports
(Move #84).

Everything here is computed from the data layer — manifests, evidence
ledgers, issue registers, promotion state. Health is expressed as
per-dimension states (OK / ATTENTION / BLOCKED) derived from facts, and the
status report states counts and items. **No invented completion
percentages, ever.**
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .evidence import EvidenceLedger
from .issues import IssueRegister
from .manifest import ProjectManifest

OK, ATTENTION, BLOCKED = "OK", "ATTENTION", "BLOCKED"


@dataclass
class Dimension:
    name: str
    state: str
    detail: str


@dataclass
class ProjectHealth:
    project_id: str
    dimensions: list = field(default_factory=list)

    @property
    def overall(self) -> str:
        states = [d.state for d in self.dimensions]
        if BLOCKED in states:
            return BLOCKED
        if ATTENTION in states:
            return ATTENTION
        return OK


def assess(project_dir: str | Path) -> ProjectHealth:
    project_dir = Path(project_dir)
    m = ProjectManifest.load(project_dir / "manifest.json")
    health = ProjectHealth(project_id=m.project_id)
    dims = health.dimensions

    n_sources = len(m.source_locations)
    dims.append(Dimension(
        "sources", OK if n_sources else BLOCKED,
        f"{n_sources} source location(s) declared" if n_sources
        else "no source locations declared"))

    ledger_path = project_dir / "evidence.jsonl"
    if ledger_path.exists():
        ledger = EvidenceLedger(ledger_path)
        unverified = [c for c in ledger.conclusions.values()
                      if c.verification_status != "human_verified"
                      and c.kind in ("ownership", "working_interest")]
        n_hv = sum(1 for e in ledger.entries.values()
                   if e.verification_status == "human_verified")
        dims.append(Dimension(
            "evidence", ATTENTION if unverified else OK,
            f"{len(ledger.entries)} evidence entries ({n_hv} human-verified), "
            f"{len(ledger.conclusions)} conclusions"
            + (f"; {len(unverified)} ownership/WI conclusions await human verification"
               if unverified else "")))
    else:
        dims.append(Dimension("evidence", ATTENTION, "no evidence ledger yet"))

    open_manifest = [i for i in m.open_issues if isinstance(i, dict)]
    crit_manifest = [i for i in open_manifest if i.get("severity") == "critical"]
    n_open, n_crit = len(open_manifest), len(crit_manifest)
    issues_path = project_dir / "issues.json"
    if issues_path.exists():
        reg_open = IssueRegister(issues_path).open_items()
        n_open += len(reg_open)
        n_crit += sum(1 for i in reg_open if i.severity == "critical")
    dims.append(Dimension(
        "open_items",
        BLOCKED if n_crit else (ATTENTION if n_open else OK),
        f"{n_open} open item(s), {n_crit} critical"))

    n_deliv = len(m.deliverables)
    dims.append(Dimension(
        "deliverables", OK if n_deliv else ATTENTION,
        f"{n_deliv} deliverable(s) declared"
        + ("" if n_deliv else " — none recorded yet")))

    promo_path = project_dir / "promotion_state.json"
    if promo_path.exists():
        state = json.loads(promo_path.read_text(encoding="utf-8"))
        parked = [p for p, rec in state.items() if rec.get("stage") == "QA"]
        dims.append(Dimension(
            "promotion", ATTENTION if parked else OK,
            f"{len(state)} tracked file(s)"
            + (f"; {len(parked)} at QA awaiting human approval" if parked else "")))
    return health


def status_report(project_dir: str | Path) -> str:
    """Factual client-status report: completed work, blockers, open research,
    decisions needed. Counts and items only — no percentages."""
    project_dir = Path(project_dir)
    m = ProjectManifest.load(project_dir / "manifest.json")
    health = assess(project_dir)

    lines = [
        f"STATUS — {m.project_id} (client: {m.client})",
        f"Overall: {health.overall}",
        "",
        "Health dimensions:",
    ]
    for d in health.dimensions:
        lines.append(f"  [{d.state:>9}] {d.name}: {d.detail}")

    if m.approved_facts:
        lines += ["", f"Completed / approved facts ({len(m.approved_facts)}):"]
        lines += [f"  - {f}" for f in m.approved_facts]

    if m.deliverables:
        lines += ["", "Deliverables:"]
        for d in m.deliverables:
            if isinstance(d, dict):
                lines.append(f"  - {d.get('name', '(unnamed)')}: {d.get('status', '')}")
            else:
                lines.append(f"  - {d}")

    blockers, research = [], []
    for i in m.open_issues:
        if isinstance(i, dict):
            (blockers if i.get("severity") == "critical" else research).append(
                i.get("description", ""))
    issues_path = project_dir / "issues.json"
    if issues_path.exists():
        for item in IssueRegister(issues_path).open_items():
            (blockers if item.severity == "critical" else research).append(item.description)

    if blockers:
        lines += ["", f"Current blockers ({len(blockers)}):"]
        lines += [f"  ! {b}" for b in blockers]
    if research:
        lines += ["", f"Open research ({len(research)}):"]
        lines += [f"  - {r}" for r in research]

    lines += ["", "Decisions needed: run `python -m core.land_title_os needs-me` "
                  "for the live queue."]
    return "\n".join(lines)
