"""Build a remaining-gates plan from finish evidence.

The plan does not invent legal, party, or date values. It only names
gates that have not passed and queue files that already exist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .human_release import evaluate_package_completion
from .source_acquisition import PRIORITY_SECTIONS

PLAN_SCHEMA_ID = "dbx.section_remaining_plan"
PLAN_SCHEMA_VERSION = "1.0"
BUNDLE_SCHEMA_ID = "dbx.remaining_plan_bundle"
BUNDLE_SCHEMA_VERSION = "1.0"
OPEN_QUEUE_FILES = {
    "examiner_queue": "section{section}-examiner-queue.json",
    "onesource_template": "section{section}-onesource-template.json",
    "delta_draft": "section{section}-delta-draft.json",
    "crop_fill_queue": "section{section}-crop-fill-queue.json",
    "crops_draft": "section{section}-crops-draft.json",
    "empty_text_queue": "section{section}-empty-text-queue.json",
    "handwritten_scan_queue": "section{section}-handwritten-scan-queue.json",
    "native_print_draft": "section{section}-native-print-draft.json",
    "owner_review_draft": "section{section}-owner-review-draft.json",
}


class RemainingPlanError(ValueError):
    """Raised when a remaining-gates plan cannot be built safely."""


@dataclass
class _GateView:
    name: str
    ran: bool
    technical_pass: Optional[bool]
    detail: Dict[str, object] = field(default_factory=dict)


def _gates_from_finish(finish: Optional[Dict[str, object]]) -> List[_GateView]:
    if not isinstance(finish, dict):
        return []
    raw = finish.get("gates")
    if not isinstance(raw, list):
        return []
    views: List[_GateView] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name:
            continue
        detail = item.get("detail")
        views.append(
            _GateView(
                name=name,
                ran=bool(item.get("ran")),
                technical_pass=item.get("technical_pass"),
                detail=detail if isinstance(detail, dict) else {},
            )
        )
    return views


def _open_queues(receipt_dir: Path, section: int) -> Dict[str, str]:
    found: Dict[str, str] = {}
    for slot, template in OPEN_QUEUE_FILES.items():
        path = receipt_dir / template.format(section=section)
        if path.is_file():
            found[slot] = str(path)
    return found


def remaining_plan(
    *,
    section: int,
    finish: Optional[Dict[str, object]],
    receipt_dir: Path,
    holds: Sequence[str] = (),
    next_commands: Sequence[str] = (),
) -> Dict[str, object]:
    if section not in PRIORITY_SECTIONS:
        raise RemainingPlanError(f"section must be one of {PRIORITY_SECTIONS}")
    gates = _gates_from_finish(finish)
    if gates:
        complete, missing = evaluate_package_completion(
            gates, requested_sections=[section]
        )
    else:
        complete = False
        missing = [
            "no finish receipt",
            "required gate source_acquisition did not pass",
            "required gate reextraction did not pass",
            "required gate occurrence_ledger did not pass",
            "required gate workbook_qa did not pass",
            "required gate native_print did not pass",
            "required gate drive_readback did not pass",
            "required gate human_release did not pass",
            "index fields are not complete (reconciliation or repair loop)",
        ]
    return {
        "schema_id": PLAN_SCHEMA_ID,
        "schema_version": PLAN_SCHEMA_VERSION,
        "section": section,
        "packages_complete": bool(complete),
        "missing": missing,
        "gates": [
            {
                "name": gate.name,
                "ran": gate.ran,
                "technical_pass": gate.technical_pass,
            }
            for gate in gates
        ],
        "open_queues": _open_queues(receipt_dir, section),
        "holds": [item for item in holds if isinstance(item, str)],
        "next_commands": [item for item in next_commands if isinstance(item, str)],
        "notes": [
            "This plan does not invent legal, party, or date values",
            "technical_pass is not package release",
            "Owner review is not an external client delivery",
        ],
    }


def write_remaining_plan(
    plan: Dict[str, object],
    output: Path,
) -> Dict[str, object]:
    dest = output.expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    return plan


def write_remaining_plan_bundle(
    plans: Sequence[Dict[str, object]],
    output: Path,
) -> Dict[str, object]:
    ordered = sorted(
        (plan for plan in plans if isinstance(plan, dict)),
        key=lambda item: PRIORITY_SECTIONS.index(int(item["section"]))
        if item.get("section") in PRIORITY_SECTIONS
        else 99,
    )
    bundle = {
        "schema_id": BUNDLE_SCHEMA_ID,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "priority_sections": list(PRIORITY_SECTIONS),
        "packages_complete": bool(ordered)
        and all(plan.get("packages_complete") is True for plan in ordered),
        "sections": ordered,
        "notes": [
            "Priority order is 15, then 13, then 11",
            "This bundle does not invent legal facts or release a package",
        ],
    }
    dest = output.expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    return bundle
