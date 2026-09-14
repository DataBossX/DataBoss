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
from .isolated_delta import sha256_file
from .source_acquisition import DEFAULT_REQUIRED_ROLES, PRIORITY_SECTIONS

PLAN_SCHEMA_ID = "dbx.section_remaining_plan"
PLAN_SCHEMA_VERSION = "1.3"
BUNDLE_SCHEMA_ID = "dbx.remaining_plan_bundle"
BUNDLE_SCHEMA_VERSION = "1.1"
EXAMINER_QUEUE_SCHEMA_ID = "dbx.examiner_fill_queue"
KNOWN_PLAN_FIELDS = (
    "document_type",
    "grantor",
    "grantee",
    "instrument_number",
    "book_page",
    "document_date",
    "recorded_date",
    "legal_description",
)
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


def _load_examiner_queue(receipt_dir: Path, section: int) -> Dict[str, object]:
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
    return payload


def _field_gaps_from_queue(receipt_dir: Path, section: int) -> Dict[str, int]:
    payload = _load_examiner_queue(receipt_dir, section)
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


def _by_field_from_queue(receipt_dir: Path, section: int) -> Dict[str, Dict[str, int]]:
    payload = _load_examiner_queue(receipt_dir, section)
    items = payload.get("items")
    if not isinstance(items, list):
        return {}
    counts: Dict[str, Dict[str, int]] = {
        field: {"blank": 0, "conflict": 0} for field in KNOWN_PLAN_FIELDS
    }
    for item in items:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        action = item.get("action")
        if field not in counts:
            continue
        if action == "resolve_conflict":
            counts[field]["conflict"] += 1
        elif action in {"source_proved_fill", "proposed_delta_pending"}:
            counts[field]["blank"] += 1
    return {
        field: slot
        for field, slot in counts.items()
        if slot["blank"] or slot["conflict"]
    }


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
    by_field: Dict[str, Dict[str, int]],
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
    for field in KNOWN_PLAN_FIELDS:
        slot = by_field.get(field) or {}
        blank = slot.get("blank") or 0
        conflict = slot.get("conflict") or 0
        if blank:
            lines.append(f"{field} has {blank} blank(s)")
        if conflict:
            lines.append(f"{field} has {conflict} conflict(s)")
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
    isolated_workbook: Optional[Path] = None,
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
        _field_gaps_from_queue(receipt_dir, section),
        _field_gaps_from_finish(gates),
    )
    by_field = _by_field_from_queue(receipt_dir, section)
    extra = _gap_lines(
        missing_required_roles=required_roles,
        missing_candidate_roles=candidate_roles,
        field_gaps=field_gaps,
        by_field=by_field,
    )
    missing = extra + [item for item in missing if item not in extra]
    if extra:
        complete = False
    isolated: Dict[str, object] = {}
    if isolated_workbook is not None:
        try:
            book = isolated_workbook.expanduser()
            if book.is_file():
                isolated = {
                    "name": book.name,
                    "sha256": sha256_file(book),
                }
        except OSError:
            isolated = {}
    name = isolated.get("name")
    if isinstance(name, str) and name:
        preview = f"Print Preview {name} on Windows Excel"
        native_ok = any(
            gate.name == "native_print" and gate.technical_pass for gate in gates
        )
        if not native_ok and preview not in missing:
            missing.append(preview)
    return {
        "schema_id": PLAN_SCHEMA_ID,
        "schema_version": PLAN_SCHEMA_VERSION,
        "section": section,
        "packages_complete": bool(complete),
        "isolated_workbook": isolated,
        "missing": missing,
        "missing_required_roles": required_roles,
        "missing_candidate_roles": candidate_roles,
        "field_gaps": {**field_gaps, "by_field": by_field},
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
            "by_field counts names only; it does not copy cell text",
            "Examiner-queue blank/conflict counts win over packet-scored finish recon",
            "isolated_workbook names the current Letter or delta; it does not copy cell text",
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


def _public_connections(raw: Optional[Dict[str, object]]) -> Dict[str, object]:
    if not isinstance(raw, dict):
        return {}
    roots: List[Dict[str, object]] = []
    for item in raw.get("roots") or []:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        if not isinstance(label, str) or not label:
            continue
        roots.append(
            {
                "label": label,
                "exists": bool(item.get("exists")),
                "is_dir": bool(item.get("is_dir")),
                "readable": bool(item.get("readable")),
            }
        )
    tools_raw = raw.get("tools")
    tools = (
        {key: bool(value) for key, value in tools_raw.items() if isinstance(key, str)}
        if isinstance(tools_raw, dict)
        else {}
    )
    desktop_raw = raw.get("desktop_sessions")
    desktop = (
        {
            key: value
            for key, value in desktop_raw.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        if isinstance(desktop_raw, dict)
        else {}
    )
    actions = [
        item for item in raw.get("next_actions") or [] if isinstance(item, str)
    ]
    count = raw.get("connected_root_count")
    return {
        "connected_root_count": count if isinstance(count, int) and count >= 0 else 0,
        "technical_pass": bool(raw.get("technical_pass")),
        "packages_complete": False,
        "roots": roots,
        "tools": tools,
        "desktop_sessions": desktop,
        "next_actions": actions,
    }


def write_remaining_plan_bundle(
    plans: Sequence[Dict[str, object]],
    output: Path,
    *,
    connections: Optional[Dict[str, object]] = None,
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
        "connections": _public_connections(connections),
        "notes": [
            "Priority order is 15, then 13, then 11",
            "Start cursor worker on the PC; authenticate Slack/Notion in Cursor Desktop",
            "This bundle does not invent legal facts or release a package",
        ],
    }
    dest = output.expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    return bundle
