"""Build a remaining-gates plan from finish evidence.

The plan does not invent legal, party, or date values. It names
unfinished gates, missing source roles, and blank/conflict counts
from finish receipts or examiner queues that already exist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .human_release import evaluate_package_completion
from .source_acquisition import DEFAULT_REQUIRED_ROLES, PRIORITY_SECTIONS

PLAN_SCHEMA_ID = "dbx.section_remaining_plan"
PLAN_SCHEMA_VERSION = "1.1"
BUNDLE_SCHEMA_ID = "dbx.remaining_plan_bundle"
BUNDLE_SCHEMA_VERSION = "1.0"
EXAMINER_QUEUE_SCHEMA_ID = "dbx.examiner_fill_queue"
_FIELD_GAP_KEYS = (
    "blank_required_count",
    "conflict_count",
    "low_confidence_blank_count",
    "remaining_blanks",
    "remaining_conflicts",
)
OPEN_QUEUE_FILES = {
    "examiner_queue": "section{section}-examiner-queue.json",
    "onesource_template": "section{section}-onesource-template.json",
    "delta_draft": "section{section}-delta-draft.json",
    "crop_fill_queue": "section{section}-crop-fill-queue.json",
    "crops_draft": "section{section}-crops-draft.json",
    "empty_text_queue": "section{section}-empty-text-queue.json",
    "handwritten_scan_queue": "section{section}-handwritten-scan-queue.json",
    "supporting_record_queue": "section{section}-supporting-record-queue.json",
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


def _string_list(raw: object) -> List[str]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item]


def _ordered_roles(*groups: Sequence[str]) -> List[str]:
    seen: List[str] = []
    present = set()
    for group in groups:
        for role in group:
            if not role or role in present:
                continue
            present.add(role)
            seen.append(role)
    ordered = [role for role in DEFAULT_REQUIRED_ROLES if role in present]
    ordered.extend(role for role in seen if role not in ordered)
    return ordered


def _roles_from_finish(gates: Sequence[_GateView], section: int) -> List[str]:
    for gate in gates:
        if gate.name != "source_acquisition":
            continue
        sections = gate.detail.get("sections")
        if not isinstance(sections, list):
            continue
        for item in sections:
            if not isinstance(item, dict) or item.get("section") != section:
                continue
            return _string_list(item.get("missing_required_roles"))
    return []


def _nonneg_int(raw: object) -> Optional[int]:
    return raw if isinstance(raw, int) and raw >= 0 else None


def _field_gaps_from_finish(gates: Sequence[_GateView]) -> Dict[str, int]:
    gaps: Dict[str, int] = {}
    for gate in gates:
        keys = ()
        if gate.name == "index_reconciliation":
            keys = (
                "blank_required_count",
                "conflict_count",
                "low_confidence_blank_count",
            )
        elif gate.name == "repair_loop":
            keys = ("remaining_blanks", "remaining_conflicts")
        for key in keys:
            value = _nonneg_int(gate.detail.get(key))
            if value is not None:
                gaps[key] = value
    return gaps


def _field_gaps_from_queue(receipt_dir: Path, section: int) -> Dict[str, int]:
    path = receipt_dir / f"section{section}-examiner-queue.json"
    try:
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    if payload.get("schema_id") != EXAMINER_QUEUE_SCHEMA_ID:
        return {}
    gaps: Dict[str, int] = {}
    mapping = {
        "blank_count": "blank_required_count",
        "conflict_count": "conflict_count",
    }
    for source, dest in mapping.items():
        value = _nonneg_int(payload.get(source))
        if value is not None:
            gaps[dest] = value
    return gaps


def _merge_field_gaps(*groups: Dict[str, int]) -> Dict[str, int]:
    merged: Dict[str, int] = {}
    for group in groups:
        for key in _FIELD_GAP_KEYS:
            if key in group and key not in merged:
                merged[key] = group[key]
    return merged


def _gap_lines(
    *,
    missing_required_roles: Sequence[str],
    missing_candidate_roles: Sequence[str],
    field_gaps: Dict[str, int],
) -> List[str]:
    lines: List[str] = []
    for role in missing_required_roles:
        lines.append(f"missing required role {role}")
    for role in missing_candidate_roles:
        label = f"missing classified candidate {role}"
        if label not in lines and f"missing required role {role}" not in lines:
            lines.append(label)
    labels = {
        "blank_required_count": "index has {n} blank required field(s)",
        "conflict_count": "index has {n} conflict(s)",
        "low_confidence_blank_count": "index has {n} low-confidence blank(s)",
        "remaining_blanks": "repair loop left {n} blank required field(s)",
        "remaining_conflicts": "repair loop left {n} conflict(s)",
    }
    for key, template in labels.items():
        count = field_gaps.get(key)
        if isinstance(count, int) and count > 0:
            lines.append(template.format(n=count))
    return lines


def remaining_plan(
    *,
    section: int,
    finish: Optional[Dict[str, object]],
    receipt_dir: Path,
    holds: Sequence[str] = (),
    next_commands: Sequence[str] = (),
    missing_required_roles: Sequence[str] = (),
    missing_candidate_roles: Sequence[str] = (),
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
    required_roles = _ordered_roles(
        _string_list(list(missing_required_roles)),
        _roles_from_finish(gates, section),
    )
    candidate_roles = _ordered_roles(_string_list(list(missing_candidate_roles)))
    field_gaps = _merge_field_gaps(
        _field_gaps_from_finish(gates),
        _field_gaps_from_queue(receipt_dir, section),
    )
    extra = _gap_lines(
        missing_required_roles=required_roles,
        missing_candidate_roles=candidate_roles,
        field_gaps=field_gaps,
    )
    missing = extra + [item for item in missing if item not in extra]
    if extra:
        complete = False
    return {
        "schema_id": PLAN_SCHEMA_ID,
        "schema_version": PLAN_SCHEMA_VERSION,
        "section": section,
        "packages_complete": bool(complete),
        "missing": missing,
        "missing_required_roles": required_roles,
        "missing_candidate_roles": candidate_roles,
        "field_gaps": field_gaps,
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
            "Typed index and handwritten_index are separate required roles",
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
