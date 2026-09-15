"""Build a remaining-gates plan from finish evidence.

The plan does not invent legal, party, or date values. It names
unfinished gates, missing source files, classified roles that still
need Phase-2 authority, blank/conflict counts from finish receipts or
examiner queues that already exist, open crop / handwritten-scan /
empty-text fill queues, and Print Preview / Drive Isolated /
owner-review hops bound to the current isolated Letter or delta.
Drive Isolated/ stays until the bound copy is under Isolated/.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .human_release import evaluate_package_completion
from .isolated_delta import sha256_file
from .source_acquisition import DEFAULT_REQUIRED_ROLES, PRIORITY_SECTIONS

_SECTION_MARK = re.compile(r"(?:section|p)(\d+)", re.IGNORECASE)

PLAN_SCHEMA_ID = "dbx.section_remaining_plan"
PLAN_SCHEMA_VERSION = "1.5"
BUNDLE_SCHEMA_ID = "dbx.remaining_plan_bundle"
BUNDLE_SCHEMA_VERSION = "1.2"
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
FILL_QUEUE_GAPS = (
    (
        "crop_fill_queue",
        "dbx.crop_fill_queue",
        "items",
        "{n} page-render crop(s) still need face text",
    ),
    (
        "handwritten_scan_queue",
        "dbx.handwritten_scan_queue",
        "items",
        "{n} handwritten scan(s) still need a Penterra xlsx",
    ),
    (
        "empty_text_queue",
        "dbx.empty_text_pdf_queue",
        "items",
        "{n} image-only PDF(s) still have empty extracted text",
    ),
    (
        "onesource_template",
        "dbx.source_proved_delta_template",
        "deltas",
        "{n} one-source row(s) still need writer-held text",
    ),
    (
        "delta_draft",
        "dbx.source_proved_delta_draft",
        "deltas",
        "{n} source-proved delta(s) still need attest",
    ),
)
CROP_FILL_SECTION = 11


def _score_fill_slot(slot: str, section: int) -> bool:
    return slot != "crop_fill_queue" or section == CROP_FILL_SECTION


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


def _roles_from_finish(
    gates: Sequence[_GateView], section: int
) -> Optional[List[str]]:
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
    return None


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


def _load_queue(
    receipt_dir: Path,
    filename: str,
    schema_id: str,
) -> Dict[str, object]:
    path = receipt_dir / filename
    try:
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    if payload.get("schema_id") != schema_id:
        return {}
    return payload


def _iter_schema_files(
    receipt_dir: Path, schema_id: str
) -> List[tuple[str, Dict[str, object]]]:
    found: List[tuple[str, Dict[str, object]]] = []
    try:
        paths = sorted(receipt_dir.glob("*.json"))
    except OSError:
        return found
    for path in paths:
        payload = _load_queue(receipt_dir, path.name, schema_id)
        if payload:
            found.append((path.name, payload))
    return found


def _preferred_queue_payload(
    receipt_dir: Path,
    section: int,
    schema_id: str,
    conventional: str,
    isolated_sha256: str = "",
    digest_field: str = "",
) -> Dict[str, object]:
    """Prefer sectionN-* when it matches; leftover hash-matched files are fallback."""
    exclusive = [
        (name, payload)
        for name, payload in _iter_schema_files(receipt_dir, schema_id)
        if _queue_exclusive_section(payload, name, section)
    ]
    if digest_field and isolated_sha256:
        matched: List[tuple[str, Dict[str, object]]] = []
        for name, payload in exclusive:
            bound = payload.get(digest_field)
            if (
                isinstance(bound, str)
                and bound
                and bound.casefold() == isolated_sha256.casefold()
            ):
                matched.append((name, payload))
        if matched:
            preferred = [item for item in matched if item[0] == conventional]
            rest = [item for item in matched if item[0] != conventional]
            return (preferred + rest)[0][1]
        return _load_queue(receipt_dir, conventional, schema_id)
    if not digest_field:
        preferred = [item for item in exclusive if item[0] == conventional]
        if preferred:
            return preferred[0][1]
        if exclusive:
            return exclusive[0][1]
        return {}
    return _load_queue(receipt_dir, conventional, schema_id)


def _load_examiner_queue(
    receipt_dir: Path, section: int, isolated_sha256: str = ""
) -> Dict[str, object]:
    return _preferred_queue_payload(
        receipt_dir,
        section,
        EXAMINER_QUEUE_SCHEMA_ID,
        OPEN_QUEUE_FILES["examiner_queue"].format(section=section),
        isolated_sha256=isolated_sha256,
        digest_field="workbook_sha256",
    )


def _priority_section_marks(*texts: str) -> set[int]:
    marks: set[int] = set()
    for text in texts:
        if not text:
            continue
        marks.update(int(match.group(1)) for match in _SECTION_MARK.finditer(text))
    return {mark for mark in marks if mark in PRIORITY_SECTIONS}


def _queue_exclusive_section(
    payload: Dict[str, object],
    filename: str,
    section: int,
) -> bool:
    if not payload:
        return True
    marks = _priority_section_marks(filename, str(payload.get("packet_id") or ""))
    raw_sections = payload.get("sections")
    if isinstance(raw_sections, list):
        marks.update(
            item
            for item in raw_sections
            if type(item) is int and item in PRIORITY_SECTIONS
        )
    if not marks:
        return True
    return marks == {section}


def _queue_section_gap(
    payload: Dict[str, object],
    filename: str,
    section: int,
    label: str,
) -> str:
    if not payload or _queue_exclusive_section(payload, filename, section):
        return ""
    return f"{label} is bound to another section"


def _queue_bound_to_isolated(
    payload: Dict[str, object],
    isolated_sha256: str,
) -> bool:
    """True when the queue can be scored against this isolated file.

    A leftover queue without workbook_sha256 is not bound once an
    isolated hash is known. Missing isolated hash still accepts the
    queue so field-gap counts remain available before a Letter exists.
    """
    if not isolated_sha256:
        return True
    bound = payload.get("workbook_sha256")
    if not isinstance(bound, str) or not bound:
        return False
    return bound.casefold() == isolated_sha256.casefold()


def _examiner_queue_hash_gap(
    payload: Dict[str, object],
    isolated_sha256: str,
) -> str:
    if not isolated_sha256 or not payload:
        return ""
    if _queue_bound_to_isolated(payload, isolated_sha256):
        return ""
    bound = payload.get("workbook_sha256")
    if not isinstance(bound, str) or not bound:
        return "examiner queue is missing a workbook hash"
    return "examiner queue is bound to a different workbook"


def _fill_queue_lines(
    receipt_dir: Path,
    section: int,
    isolated_sha256: str = "",
) -> List[str]:
    lines: List[str] = []
    for slot, schema_id, collection, template in FILL_QUEUE_GAPS:
        if not _score_fill_slot(slot, section):
            continue
        filename = OPEN_QUEUE_FILES[slot].format(section=section)
        digest_field = (
            "source_workbook_sha256"
            if slot in {"onesource_template", "delta_draft"}
            else ""
        )
        payload = _preferred_queue_payload(
            receipt_dir,
            section,
            schema_id,
            filename,
            isolated_sha256=isolated_sha256,
            digest_field=digest_field,
        )
        if not payload:
            continue
        if slot in {"onesource_template", "delta_draft"}:
            if payload.get("status") != "UNAPPROVED_DRAFT":
                continue
            if isolated_sha256:
                bound = payload.get("source_workbook_sha256")
                if not isinstance(bound, str) or not bound:
                    continue
                if bound.casefold() != isolated_sha256.casefold():
                    continue
        rows = payload.get(collection)
        if not isinstance(rows, list):
            continue
        count = sum(1 for item in rows if isinstance(item, dict))
        if count:
            lines.append(template.format(n=count))
    return lines


def _fill_draft_hash_gaps(
    receipt_dir: Path,
    section: int,
    isolated_sha256: str,
) -> List[str]:
    if not isolated_sha256:
        return []
    lines: List[str] = []
    for slot, schema_id, label in (
        (
            "onesource_template",
            "dbx.source_proved_delta_template",
            "onesource template",
        ),
        ("delta_draft", "dbx.source_proved_delta_draft", "delta draft"),
    ):
        payload = _load_queue(
            receipt_dir, OPEN_QUEUE_FILES[slot].format(section=section), schema_id
        )
        if payload.get("status") != "UNAPPROVED_DRAFT":
            continue
        bound = payload.get("source_workbook_sha256")
        if not isinstance(bound, str) or not bound:
            lines.append(f"{label} is missing a workbook hash")
    return lines


def _fill_section_gaps(receipt_dir: Path, section: int) -> List[str]:
    lines: List[str] = []
    slots = (
        ("examiner_queue", EXAMINER_QUEUE_SCHEMA_ID, "examiner queue"),
        ("crop_fill_queue", "dbx.crop_fill_queue", "crop fill queue"),
        (
            "handwritten_scan_queue",
            "dbx.handwritten_scan_queue",
            "handwritten scan queue",
        ),
        ("empty_text_queue", "dbx.empty_text_pdf_queue", "empty-text queue"),
        (
            "onesource_template",
            "dbx.source_proved_delta_template",
            "onesource template",
        ),
        ("delta_draft", "dbx.source_proved_delta_draft", "delta draft"),
    )
    for slot, schema_id, label in slots:
        if not _score_fill_slot(slot, section):
            continue
        filename = OPEN_QUEUE_FILES[slot].format(section=section)
        payload = _load_queue(receipt_dir, filename, schema_id)
        gap = _queue_section_gap(payload, filename, section, label)
        if gap:
            lines.append(gap)
    return lines


def _field_gaps_from_queue(
    receipt_dir: Path,
    section: int,
    isolated_sha256: str = "",
) -> Dict[str, int]:
    payload = _load_examiner_queue(receipt_dir, section, isolated_sha256)
    if not _queue_bound_to_isolated(payload, isolated_sha256):
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


def _by_field_from_queue(
    receipt_dir: Path,
    section: int,
    isolated_sha256: str = "",
) -> Dict[str, Dict[str, int]]:
    payload = _load_examiner_queue(receipt_dir, section, isolated_sha256)
    if not _queue_bound_to_isolated(payload, isolated_sha256):
        return {}
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


def named_isolated_hops(name: str, section: int) -> Dict[str, str]:
    """Name Print Preview, Drive Isolated/, and owner-review of one file."""
    return {
        "native_print": f"Print Preview {name} on Windows Excel",
        "drive_readback": f"Copy {name} into Drive Section {section}/Isolated/",
        "human_release": f"Attest owner-review of {name}",
    }


def _named_hop_done(
    gate_name: str,
    gates: Sequence[_GateView],
    isolated_sha256: str = "",
) -> bool:
    for gate in gates:
        if gate.name != gate_name:
            continue
        if not gate.technical_pass:
            return False
        if gate_name == "drive_readback":
            if gate.detail.get("isolated_copy") is not True:
                return False
            if isolated_sha256:
                bound = gate.detail.get("workbook_sha256") or gate.detail.get(
                    "readback_sha256"
                )
                if not isinstance(bound, str) or not bound:
                    return False
                return bound.casefold() == isolated_sha256.casefold()
            return True
        if isolated_sha256 and gate_name in {"native_print", "human_release"}:
            bound = gate.detail.get("workbook_sha256")
            if not isinstance(bound, str) or not bound:
                return False
            return bound.casefold() == isolated_sha256.casefold()
        return True
    return False


def _gap_lines(
    *,
    missing_required_roles: Sequence[str],
    missing_candidate_roles: Sequence[str],
    unauthorized_classified_roles: Sequence[str],
    field_gaps: Dict[str, int],
    by_field: Dict[str, Dict[str, int]],
) -> List[str]:
    lines: List[str] = []
    unauthorized = set(unauthorized_classified_roles)
    for role in missing_required_roles:
        if role in unauthorized:
            lines.append(
                f"required role {role} is classified but not Phase-2 authorized"
            )
        else:
            lines.append(f"missing required role {role}")
    if unauthorized:
        lines.append(
            "Promote classified files with horizon.authority_promote "
            "before Phase 2 snapshots"
        )
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
    unauthorized_classified_roles: Sequence[str] = (),
    isolated_workbook: Optional[Path] = None,
) -> Dict[str, object]:
    if section not in PRIORITY_SECTIONS:
        raise RemainingPlanError(f"section must be one of {PRIORITY_SECTIONS}")
    gates = _gates_from_finish(finish)
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
    digest = isolated.get("sha256")
    isolated_sha = digest if isinstance(digest, str) and digest else ""
    if gates:
        complete, missing = evaluate_package_completion(
            gates,
            requested_sections=[section],
            workbook_sha256=isolated_sha or None,
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
    finish_roles = _roles_from_finish(gates, section)
    required_roles = _ordered_roles(
        finish_roles
        if finish_roles is not None
        else _string_list(list(missing_required_roles))
    )
    candidate_roles = _ordered_roles(_string_list(list(missing_candidate_roles)))
    unauthorized_roles = [
        role
        for role in _ordered_roles(_string_list(list(unauthorized_classified_roles)))
        if role in required_roles
    ]
    field_gaps = _merge_field_gaps(
        _field_gaps_from_queue(receipt_dir, section, isolated_sha),
        _field_gaps_from_finish(gates),
    )
    by_field = _by_field_from_queue(receipt_dir, section, isolated_sha)
    extra = _gap_lines(
        missing_required_roles=required_roles,
        missing_candidate_roles=candidate_roles,
        unauthorized_classified_roles=unauthorized_roles,
        field_gaps=field_gaps,
        by_field=by_field,
    )
    queue_payload = _load_queue(
        receipt_dir,
        OPEN_QUEUE_FILES["examiner_queue"].format(section=section),
        EXAMINER_QUEUE_SCHEMA_ID,
    )
    queue_gap = _examiner_queue_hash_gap(queue_payload, isolated_sha)
    if queue_gap:
        extra.append(queue_gap)
    extra.extend(
        line
        for line in _fill_queue_lines(receipt_dir, section, isolated_sha)
        if line not in extra
    )
    extra.extend(
        line
        for line in _fill_draft_hash_gaps(receipt_dir, section, isolated_sha)
        if line not in extra
    )
    extra.extend(
        line
        for line in _fill_section_gaps(receipt_dir, section)
        if line not in extra
    )
    missing = extra + [item for item in missing if item not in extra]
    if extra:
        complete = False
    commands = [item for item in next_commands if isinstance(item, str)]
    if unauthorized_roles and not any(
        "authority_promote" in item for item in commands
    ):
        commands = [
            (
                f"Promote classified files with horizon.authority_promote "
                f"--confirm-section {section} using the named examiner "
                "and live --root hashes"
            ),
            *commands,
        ]
    if isinstance(name, str) and name:
        named = named_isolated_hops(name, section)
        for gate_name, line in named.items():
            if (
                not _named_hop_done(gate_name, gates, isolated_sha)
                and line not in missing
            ):
                missing.append(line)
                complete = False
        for gate in gates:
            if not gate.ran:
                continue
            if gate.name == "index_reconciliation":
                source = gate.detail.get("candidate_from")
                if isolated_sha and source != "workbook":
                    line = (
                        f"index reconciliation scored {source}, not {name}"
                        if isinstance(source, str) and source
                        else f"index reconciliation did not score {name}"
                    )
                    if line not in missing:
                        missing.append(line)
                    complete = False
                    continue
                bound = gate.detail.get("workbook_sha256")
                if isolated_sha and (
                    not isinstance(bound, str)
                    or not bound
                    or bound.casefold() != isolated_sha.casefold()
                ):
                    line = f"index reconciliation did not hash {name}"
                    if isinstance(bound, str) and bound:
                        line = f"index reconciliation scored a different workbook, not {name}"
                    if line not in missing:
                        missing.append(line)
                    complete = False
            elif gate.name == "repair_loop":
                bound = gate.detail.get("final_workbook_sha256") or gate.detail.get(
                    "workbook_sha256"
                )
                if isolated_sha and (
                    not isinstance(bound, str)
                    or not bound
                    or bound.casefold() != isolated_sha.casefold()
                ):
                    line = f"repair loop did not hash {name}"
                    if isinstance(bound, str) and bound:
                        line = f"repair loop scored a different workbook, not {name}"
                    if line not in missing:
                        missing.append(line)
                    complete = False
            elif gate.name == "workbook_qa":
                bound = gate.detail.get("workbook_sha256")
                if isolated_sha and (
                    not isinstance(bound, str)
                    or not bound
                    or bound.casefold() != isolated_sha.casefold()
                ):
                    line = f"workbook QA did not hash {name}"
                    if isinstance(bound, str) and bound:
                        line = f"workbook QA scored a different workbook, not {name}"
                    if line not in missing:
                        missing.append(line)
                    complete = False
    return {
        "schema_id": PLAN_SCHEMA_ID,
        "schema_version": PLAN_SCHEMA_VERSION,
        "section": section,
        "packages_complete": bool(complete),
        "isolated_workbook": isolated,
        "missing": missing,
        "missing_required_roles": required_roles,
        "missing_candidate_roles": candidate_roles,
        "unauthorized_classified_roles": unauthorized_roles,
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
        "next_commands": commands,
        "notes": [
            "This plan does not invent legal, party, or date values",
            "Typed index and handwritten_index are separate required roles",
            "Classified-but-unauthorized roles are Phase-2 holds, not missing files",
            "Classified files still need Phase-2 authority before extraction",
            "Finish source_acquisition role gaps win over Phase-1 work-order gaps",
            "next_commands lists authority_promote first while classified roles await Phase 2",
            "After an isolated Letter or delta exists, fills and Print Preview come before re-export",
            "by_field counts names only; it does not copy cell text",
            "Examiner-queue blank/conflict counts win over packet-scored finish recon",
            "Open handwritten-scan, empty-text, one-source, and delta-draft queues keep the plan incomplete",
            "Open crop-fill queues keep section 11 incomplete",
            "Chat/OCR supporting queues are review-only and do not complete or fill",
            "isolated_workbook names the current Letter or delta; it does not copy cell text",
            "missing names Print Preview, Drive Isolated/, and owner-review of that file only",
            "Print Preview and owner-review stay until finish hashes that isolated file",
            "index reconciliation must score the isolated workbook, not a leftover packet",
            "index reconciliation without candidate_from=workbook does not complete",
            "index reconciliation, repair loop, and workbook QA must hash that isolated file",
            "examiner-queue counts bound to a different workbook hash are ignored",
            "examiner-queue counts without a workbook hash are ignored once an isolated file exists",
            "onesource and delta drafts without a workbook hash are ignored once an isolated file exists",
            "leftover examiner, one-source, and fill queues that hash the isolated file are scored when the conventional file is absent or stale",
            "fill queues whose packet_id names another priority section are ignored",
            "crop-fill queues are scored only for section 11",
            "Drive Isolated/ stays until the bound copy is under Isolated/",
            "Drive Isolated/ stays until that copy hashes the current isolated file",
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


def _safe_connection_action(action: str) -> bool:
    if not action or "\n" in action:
        return False
    if re.search(r"=[A-Za-z]:[\\/]", action):
        return False
    if re.search(r"=\s*/", action):
        return False
    return True


def _bundle_next(
    plans: Sequence[Dict[str, object]],
    connections: Dict[str, object],
) -> Optional[Dict[str, object]]:
    count = connections.get("connected_root_count")
    actions = connections.get("next_actions")
    if not (isinstance(count, int) and count > 0):
        for action in actions if isinstance(actions, list) else []:
            if isinstance(action, str) and _safe_connection_action(action):
                return {"section": None, "action": action}
    for plan in plans:
        if plan.get("packages_complete") is True:
            continue
        section = plan.get("section")
        for item in plan.get("missing") or []:
            if isinstance(item, str) and item and "\n" not in item:
                return {"section": section, "action": item}
    return None


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
    public = _public_connections(connections)
    bundle = {
        "schema_id": BUNDLE_SCHEMA_ID,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "priority_sections": list(PRIORITY_SECTIONS),
        "packages_complete": bool(ordered)
        and all(plan.get("packages_complete") is True for plan in ordered),
        "next": _bundle_next(ordered, public),
        "sections": ordered,
        "connections": public,
        "notes": [
            "Priority order is 15, then 13, then 11",
            "next is the first unfinished hop in that order",
            "Connection mounts come first when no labeled root is readable",
            "Start cursor worker on the PC; authenticate Slack/Notion in Cursor Desktop",
            "This bundle does not invent legal facts or release a package",
        ],
    }
    dest = output.expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    return bundle
