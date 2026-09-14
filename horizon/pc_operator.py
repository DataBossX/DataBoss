"""PC work-order operator for sections 15, 13, and 11.

Probe connections, run Phase 1 inventory when roots are readable, and emit
per-section next commands. This module never copies client files, never
starts Phase 2 without a human-approved authority manifest, never starts a
second controller, and never claims package completion.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import sys
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .authority_draft import draft_from_files, write_draft
from .authority_promote import build_promote_command
from .connect_status import ConnectStatusError, ConnectStatusReceipt, probe_connections
from .index_export import IndexExportError, export_index_packet
from .isolated_delta import (
    IsolatedDeltaError,
    sha256_file,
    write_delta_draft,
    write_onesource_template,
)
from .human_release import HumanReleaseError, write_human_release_draft
from .native_print import NativePrintError, write_native_print_draft
from .page_render_export import (
    PageRenderExportError,
    crop_fill_queue_from_draft,
    write_crops_draft,
)
from .package_finish import PackageFinishError, run_finish
from .pdf_census import (
    PdfCensusError,
    census_packet,
    write_empty_text_queue,
    write_inventory_packet,
)
from .workbook_ledger import (
    WorkbookLedgerError,
    workbook_to_occurrence_packet,
    workbook_to_tract_export,
)
from .examiner_queue import (
    ExaminerQueueError,
    build_examiner_queue,
    onesource_rows_from_queue,
    proposed_deltas_from_queue,
)
from .handwritten_scan import (
    HandwrittenScanError,
    handwritten_scan_queue_from_draft,
    write_handwritten_scan_draft,
)
from .remaining_plan import (
    RemainingPlanError,
    remaining_plan,
    write_remaining_plan,
    write_remaining_plan_bundle,
)
from .supporting_record import (
    SupportingRecordError,
    supporting_record_queue_from_draft,
    write_supporting_record_draft,
)
from .source_acquisition import (
    DEFAULT_REQUIRED_ROLES,
    IMAGE_EXTENSIONS,
    PRIORITY_SECTIONS,
    SOURCE_ROLES,
    WORKBOOK_EXTENSIONS,
    AcquisitionReceipt,
    SourceAcquisitionError,
    SourceFile,
    SourceIssue,
    build_receipt,
    ensure_authority_snapshot,
    parse_root,
    snapshot_path_for,
)

RECEIPT_SCHEMA_ID = "dbx.pc_operator_receipt"
RECEIPT_SCHEMA_VERSION = "1.3"
REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_RECEIPT_PLACEHOLDER = "<private-receipts>"
SECTION_HOLDS = {
    15: (
        "Isolated Letter print-layout repair, then native Windows Excel "
        "Print Preview with a writer-held page count",
        "Drive readback of the same isolated bytes on a distinct path",
        "Do not use portrait FitWidth as the Penterra default",
    ),
    13: (
        "Apply only writer-held source-proved isolated deltas",
        "Build a three-index packet and run up to 10 isolated repair passes",
        "Hold SRP rows whose Rec Date is a pull date, serial numbers in "
        "Grantee, and image-only PDFs with empty extracted text",
        "Do not merge a neighboring lease serial into another casefile",
    ),
    11: (
        "Re-extract Book/Page, dates, and parties from writer-held "
        "page-render crops",
        "Bare document numbers stay bare; do not guess neighbors",
        "Do not work insertion or allowlist queues to invent rows",
    ),
}
ROLE_EXPORT_SLOT = {
    "master_workbook": "master",
    "handwritten_index": "handwritten",
    "index": "pdf_index",
    "workbook": "candidate",
}
DISCOVERABLE_SCHEMAS = {
    "dbx.page_render_crop_packet": "page_render_packet",
    "dbx.native_print_receipt": "native_print_receipt",
    "dbx.human_release_token": "human_release_token",
    "dbx.pdf_page_census_packet": "pdf_census_packet",
    "dbx.source_proved_delta_packet": "delta_packet",
}


class PcOperatorError(ValueError):
    """Raised when the PC operator cannot build a safe work order."""


@dataclass
class FinishBindings:
    page_render_packet: Optional[Path] = None
    native_print_receipt: Optional[Path] = None
    human_release_token: Optional[Path] = None
    pdf_census_packet: Optional[Path] = None
    pdf_bind_dir: Optional[Path] = None
    drive_readback: Optional[Path] = None
    authority_manifest: Optional[Path] = None
    project_manifest: Optional[Path] = None
    snapshot_directory: Optional[Path] = None
    delta_packet: Optional[Path] = None


@dataclass
class CandidatePick:
    section: int
    slot: str
    role: str
    root_label: str
    relative_path: str
    path: str
    sha256: str
    size_bytes: int
    extension: str
    exportable: bool
    note: str = ""


@dataclass
class SectionWorkOrder:
    section: int
    ready_for_extraction: bool
    missing_required_roles: List[str]
    missing_candidate_roles: List[str]
    candidate_role_counts: Dict[str, int]
    file_count: int
    roots_present: List[str]
    candidate_picks: List[CandidatePick]
    next_commands: List[str]
    holds: List[str]
    executed: bool = False
    finish_technical_pass: Optional[bool] = None
    finish_packages_complete: Optional[bool] = None
    executed_outputs: List[str] = field(default_factory=list)
    execute_error: str = ""


@dataclass
class OperatorReceipt:
    generated_utc: str
    requested_sections: List[int]
    connections: Dict[str, object]
    acquisition_phase: str
    inventory_technical_pass: Optional[bool]
    inventory_issue_count: int
    inventory_issues: List[str]
    sections: List[SectionWorkOrder]
    next_actions: List[str]
    packages_complete: bool
    technical_pass: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            "packages_complete stays false",
            "Phase 1 inventory is not legal authority and is not Phase 2",
            "Do not copy client source files into the public repository",
            "Isolated Letter/delta copies may be published onto a mounted drive= root",
            "Do not start a second Landman Helper controller",
            "technical_pass means readable roots were probed and Phase 1 ran",
            "--execute writes isolated packets under receipt-dir only",
            "authority-draft.json is UNAPPROVED_DRAFT and cannot bind Phase 2",
            "authority_promote requires a named examiner and live hash re-check",
        ]
    )
    authority_draft_path: Optional[str] = None
    authority_draft: Optional[Dict[str, object]] = None
    authority_promote_command: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _quote_command(parts: Sequence[object]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def _receipt_dir(receipt_dir: Optional[Path]) -> str:
    if receipt_dir is None:
        return PRIVATE_RECEIPT_PLACEHOLDER
    return str(receipt_dir.expanduser().resolve())


def assert_private_receipt_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise PcOperatorError(
            "receipt-dir must be outside this repository; do not write "
            "client packets or isolated copies here"
        )
    return resolved


def _absolute_file(roots: Dict[str, str], item: SourceFile) -> str:
    return str(Path(roots[item.root_label]) / item.relative_path)


def _readable_root_args(connections: ConnectStatusReceipt) -> List[str]:
    args: List[str] = []
    for probe in connections.roots:
        if probe.exists and probe.is_dir and probe.readable:
            args.append(f"{probe.label}={probe.path}")
    return args


_ISOLATED_OUTPUT_NAME = re.compile(
    r"^section\d+-(letter|delta|workbook-export|workbook-occurrence)\.",
    re.IGNORECASE,
)


def _is_isolated_output(item: SourceFile) -> bool:
    relative = Path(item.relative_path)
    if _ISOLATED_OUTPUT_NAME.match(relative.name):
        return True
    return any(part.casefold() == "isolated" for part in relative.parts)


def _pick_role_files(
    files: Sequence[SourceFile],
    section: int,
    role: str,
) -> List[SourceFile]:
    return [
        item
        for item in files
        if item.section == section
        and item.candidate_role == role
        and not _is_isolated_output(item)
    ]


def _pick_slot(
    files: Sequence[SourceFile],
    roots: Dict[str, str],
    section: int,
    role: str,
    slot: str,
) -> Optional[CandidatePick]:
    matches = _pick_role_files(files, section, role)
    if not matches:
        return None
    chosen = matches[0]
    exportable = chosen.extension in WORKBOOK_EXTENSIONS
    note = ""
    if len(matches) > 1:
        note = (
            f"{len(matches)} {role} candidates; using first sorted path; "
            "examiner must confirm authority"
        )
    if not exportable:
        note = (
            (note + "; ") if note else ""
        ) + "not a Penterra workbook; export or OCR to xlsx before index_export"
    return CandidatePick(
        section=section,
        slot=slot,
        role=role,
        root_label=chosen.root_label,
        relative_path=chosen.relative_path,
        path=_absolute_file(roots, chosen),
        sha256=chosen.sha256,
        size_bytes=chosen.size_bytes,
        extension=chosen.extension,
        exportable=exportable,
        note=note,
    )


def _missing_candidate_roles(
    files: Sequence[SourceFile],
    section: int,
    required_roles: Sequence[str],
) -> List[str]:
    present = {item.candidate_role for item in files if item.section == section}
    return [role for role in required_roles if role not in present]


def _section_picks(
    files: Sequence[SourceFile],
    roots: Dict[str, str],
    section: int,
) -> List[CandidatePick]:
    picks: List[CandidatePick] = []
    for role, slot in ROLE_EXPORT_SLOT.items():
        pick = _pick_slot(files, roots, section, role, slot)
        if pick is not None:
            picks.append(pick)
    if not any(pick.slot == "candidate" for pick in picks):
        master = next((pick for pick in picks if pick.slot == "master"), None)
        if master is not None and master.exportable:
            picks.append(
                CandidatePick(
                    section=section,
                    slot="candidate",
                    role=master.role,
                    root_label=master.root_label,
                    relative_path=master.relative_path,
                    path=master.path,
                    sha256=master.sha256,
                    size_bytes=master.size_bytes,
                    extension=master.extension,
                    exportable=True,
                    note=(
                        "No separate working workbook; candidate falls back "
                        "to the master path. Repair still writes a new copy."
                    ),
                )
            )
    return picks


def _slot_path(picks: Sequence[CandidatePick], slot: str) -> Optional[str]:
    for pick in picks:
        if pick.slot == slot and pick.exportable:
            return pick.path
    return None


def _append_binding_flags(
    parts: List[object],
    bindings: FinishBindings,
    *,
    receipt_dir: str,
    section: int,
) -> None:
    if bindings.page_render_packet is not None:
        parts.extend(["--page-render-packet", bindings.page_render_packet])
    if bindings.native_print_receipt is not None:
        parts.extend(["--native-print-receipt", bindings.native_print_receipt])
    if bindings.human_release_token is not None:
        parts.extend(["--human-release-token", bindings.human_release_token])
    if bindings.pdf_census_packet is not None:
        parts.extend(["--pdf-census-packet", bindings.pdf_census_packet])
    if bindings.pdf_bind_dir is not None:
        parts.extend(["--pdf-bind-dir", bindings.pdf_bind_dir])
    if bindings.drive_readback is not None:
        parts.extend(["--drive-readback", bindings.drive_readback])
    if bindings.delta_packet is not None:
        parts.extend(
            [
                "--delta-packet",
                bindings.delta_packet,
                "--delta-output",
                f"{receipt_dir}/section{section}-delta.xlsx",
            ]
        )
    if (
        bindings.authority_manifest is not None
        and bindings.project_manifest is not None
    ):
        parts.extend(
            [
                "--authority-manifest",
                bindings.authority_manifest,
                "--project-manifest",
                bindings.project_manifest,
                "--snapshot-directory",
                f"{receipt_dir}/snapshot-section{section}",
            ]
        )


def _section_commands(
    section: int,
    *,
    root_args: Sequence[str],
    picks: Sequence[CandidatePick],
    receipt_dir: str,
    missing_roles: Sequence[str],
    bindings: FinishBindings,
) -> List[str]:
    commands: List[str] = []
    if missing_roles:
        commands.append(
            "Locate examiner-held files for missing roles: "
            + ", ".join(missing_roles)
        )
    master = _slot_path(picks, "master")
    pdf_index = _slot_path(picks, "pdf_index")
    handwritten = _slot_path(picks, "handwritten")
    candidate = _slot_path(picks, "candidate")
    packet = f"{receipt_dir}/section{section}-index-packet.json"
    if any((master, pdf_index, handwritten)):
        export_parts: List[object] = [
            "python3",
            "-m",
            "horizon.index_export",
            "--packet-id",
            f"SECTION{section}-INDEX",
            "--output",
            packet,
        ]
        if master:
            export_parts.extend(["--master", master])
        if pdf_index:
            export_parts.extend(["--pdf-index", pdf_index])
        if handwritten:
            export_parts.extend(["--handwritten", handwritten])
        if candidate:
            export_parts.extend(["--candidate", candidate])
        commands.append(_quote_command(export_parts))
        finish_parts: List[object] = [
            "python3",
            "-m",
            "horizon.package_finish",
            "--section",
            section,
            "--index-packet",
            packet,
            "--output",
            f"{receipt_dir}/section{section}-finish.json",
        ]
        for root in root_args:
            finish_parts.extend(["--root", root])
        finish_parts.append("--connect-status")
        if candidate:
            finish_parts.extend(
                [
                    "--workbook",
                    candidate,
                    "--repair-dir",
                    f"{receipt_dir}/section{section}-repair",
                    "--print-layout-output",
                    f"{receipt_dir}/section{section}-letter.xlsx",
                ]
            )
        _append_binding_flags(
            finish_parts,
            bindings,
            receipt_dir=receipt_dir,
            section=section,
        )
        commands.append(_quote_command(finish_parts))
    elif bindings.page_render_packet is not None:
        finish_parts: List[object] = [
            "python3",
            "-m",
            "horizon.package_finish",
            "--section",
            section,
            "--output",
            f"{receipt_dir}/section{section}-finish.json",
        ]
        for root in root_args:
            finish_parts.extend(["--root", root])
        finish_parts.append("--connect-status")
        _append_binding_flags(
            finish_parts,
            bindings,
            receipt_dir=receipt_dir,
            section=section,
        )
        commands.append(_quote_command(finish_parts))
    else:
        commands.append(
            "Export master, PDF, and handwritten indexes to Penterra xlsx "
            "on the PC, then rerun python3 -m horizon.pc_operator"
        )
    if bindings.pdf_census_packet is None:
        bind_dir = bindings.pdf_bind_dir or f"{receipt_dir}/section{section}-pdfs"
        commands.append(
            _quote_command(
                [
                    "python3",
                    "-m",
                    "horizon.pdf_census",
                    "--inventory",
                    "--bind-dir",
                    bind_dir,
                    "--output",
                    f"{receipt_dir}/section{section}-pdf-census-packet.json",
                    "--packet-id",
                    f"SECTION{section}-CENSUS",
                ]
            )
        )
        commands.append(
            "Census source_document PDFs or copies in sectionN-pdfs; "
            "expected_pages is the counted page total, not a row count"
        )
    queue_path = Path(receipt_dir) / f"section{section}-empty-text-queue.json"
    if queue_path.is_file():
        commands.append(
            "Review image-only PDFs in "
            f"section{section}-empty-text-queue.json from the hashed faces; "
            "do not invent legal text from page count"
        )
    handwritten_queue = (
        Path(receipt_dir) / f"section{section}-handwritten-scan-queue.json"
    )
    if handwritten_queue.is_file():
        commands.append(
            "Transcribe hashed handwritten scans from "
            f"section{section}-handwritten-scan-queue.json into a Penterra "
            "xlsx; Horizon does not OCR or invent index rows"
        )
    supporting_queue = (
        Path(receipt_dir) / f"section{section}-supporting-record-queue.json"
    )
    if supporting_queue.is_file():
        commands.append(
            "Review hashed chat/OCR files in "
            f"section{section}-supporting-record-queue.json only; they are "
            "not legal authority and must not fill index cells"
        )
    workbook = _current_isolated_workbook(receipt_dir, section)
    queue_path = Path(receipt_dir) / f"section{section}-examiner-queue.json"
    queue_needs_fill = _queue_has_items(queue_path)
    if section == 11 and bindings.page_render_packet is None:
        render_dir = _section_render_bind_dir(Path(receipt_dir), section)
        if render_dir is None:
            draft = Path(receipt_dir) / f"section{section}-crops-draft.json"
            try:
                payload = json.loads(draft.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                payload = {}
            bind_text = payload.get("bind_dir") if isinstance(payload, dict) else ""
            if isinstance(bind_text, str) and bind_text.strip():
                render_dir = Path(bind_text)
        commands.append(
            _quote_command(
                [
                    "python3",
                    "-m",
                    "horizon.page_render_export",
                    "--attest",
                    "--from-draft",
                    f"{receipt_dir}/section{section}-crops-draft.json",
                    "--bind-dir",
                    str(render_dir) if render_dir is not None else "RENDER_DIR",
                    "--output",
                    f"{receipt_dir}/section{section}-crops.json",
                    "--operator",
                    "EXAMINER_NAME",
                ]
            )
        )
        commands.append(
            "Fill only face text in section11-crops-draft.json from the "
            "hashed page renders, then attest; leave bare document numbers "
            "bare. Horizon does not invent docnos"
        )
    draft_path = Path(receipt_dir) / f"section{section}-delta-draft.json"
    if bindings.delta_packet is None and draft_path.is_file():
        commands.append(
            _quote_command(
                [
                    "python3",
                    "-m",
                    "horizon.isolated_delta",
                    "--attest",
                    "--from-draft",
                    str(draft_path),
                    "--workbook",
                    workbook,
                    "--output",
                    f"{receipt_dir}/section{section}-delta-packet.json",
                    "--operator",
                    "EXAMINER_NAME",
                ]
            )
        )
        commands.append(
            "Attest the 2+ source delta draft with EXAMINER_NAME; "
            "one-source blanks stay out of that draft"
        )
    template_path = Path(receipt_dir) / f"section{section}-onesource-template.json"
    if bindings.delta_packet is None and template_path.is_file():
        commands.append(
            _quote_command(
                [
                    "python3",
                    "-m",
                    "horizon.isolated_delta",
                    "--attest",
                    "--from-template",
                    str(template_path),
                    "--workbook",
                    workbook,
                    "--output",
                    f"{receipt_dir}/section{section}-delta-packet.json",
                    "--operator",
                    "EXAMINER_NAME",
                ]
            )
        )
        commands.append(
            "Fill only source-proved values in the one-source template, "
            "then attest; do not copy source_values without a face"
        )
    if bindings.delta_packet is None and (section == 13 or queue_needs_fill):
        commands.append(
            _quote_command(
                [
                    "python3",
                    "-m",
                    "horizon.isolated_delta",
                    "--write",
                    "--workbook",
                    workbook,
                    "--deltas",
                    f"{receipt_dir}/section{section}-deltas.json",
                    "--output",
                    f"{receipt_dir}/section{section}-delta-packet.json",
                    "--packet-id",
                    f"SECTION{section}-DELTA",
                ]
            )
        )
        commands.append(
            f"Put only source-proved fills in section{section}-deltas.json; "
            "do not invent legal, party, or date values from the fill queue"
        )
    if bindings.native_print_receipt is None:
        draft = f"{receipt_dir}/section{section}-native-print-draft.json"
        commands.append(
            _quote_command(
                [
                    "python3",
                    "-m",
                    "horizon.native_print",
                    "--attest",
                    "--from-draft",
                    draft,
                    "--workbook",
                    workbook,
                    "--output",
                    f"{receipt_dir}/section{section}-native-print.json",
                    "--operator",
                    "EXAMINER_NAME",
                    "--page-count",
                    "PAGE_COUNT",
                ]
            )
        )
        commands.append(
            "On Windows Excel, Print Preview the current isolated workbook, "
            "then attest the draft with PAGE_COUNT and EXAMINER_NAME"
        )
    if bindings.drive_readback is None:
        commands.append(
            "Copy the current isolated workbook onto the mounted drive= "
            f"section folder as section{section}-letter.xlsx or "
            f"section{section}-delta.xlsx so the next execute can bind readback"
        )
    if bindings.human_release_token is None:
        draft = f"{receipt_dir}/section{section}-owner-review-draft.json"
        commands.append(
            _quote_command(
                [
                    "python3",
                    "-m",
                    "horizon.human_release",
                    "--attest",
                    "--from-draft",
                    draft,
                    "--workbook",
                    workbook,
                    "--output",
                    f"{receipt_dir}/section{section}-owner-review.json",
                    "--operator",
                    "EXAMINER_NAME",
                ]
            )
        )
        commands.append(
            "Attest the owner-review draft with EXAMINER_NAME after the "
            "current isolated workbook is ready for owner review only"
        )
    return commands


def _section_work_order(
    section: int,
    *,
    inventory: Optional[AcquisitionReceipt],
    root_args: Sequence[str],
    receipt_dir: str,
    required_roles: Sequence[str],
    bindings: FinishBindings,
) -> SectionWorkOrder:
    holds = list(SECTION_HOLDS.get(section, ()))
    if inventory is None:
        return SectionWorkOrder(
            section=section,
            ready_for_extraction=False,
            missing_required_roles=list(required_roles),
            missing_candidate_roles=list(required_roles),
            candidate_role_counts={},
            file_count=0,
            roots_present=[],
            candidate_picks=[],
            next_commands=[
                "Mount pc= and drive= roots on the host that can see the files, "
                "then rerun python3 -m horizon.pc_operator"
            ],
            holds=holds,
        )
    summary = next(
        (item for item in inventory.sections if item.section == section),
        None,
    )
    files = [item for item in inventory.files if item.section == section]
    picks = _section_picks(files, inventory.roots, section)
    for pick in picks:
        if pick.note:
            holds.append(pick.note)
    missing_authority = (
        list(summary.missing_required_roles) if summary else list(required_roles)
    )
    missing_candidates = _missing_candidate_roles(files, section, required_roles)
    bound = _bind_section_census(
        _merge_bindings(
            bindings,
            _discover_packets(files, inventory.roots, section),
        ),
        receipt_dir,
        section,
        inventory=inventory,
    )
    isolated = Path(_current_isolated_workbook(receipt_dir, section))
    bound, stale_holds = _unbind_stale_workbook_packets(
        bound, isolated if isolated.is_file() else None
    )
    holds.extend(stale_holds)
    crops_bind = _crops_bind_dir(
        Path(receipt_dir),
        section,
        inventory,
        str(Path(receipt_dir) / f"section{section}-crops-draft.json"),
    )
    bound, crop_holds = _unbind_stale_crop_packet(bound, crops_bind)
    holds.extend(crop_holds)
    try:
        receipt_json = sorted(Path(receipt_dir).glob("*.json"))
    except OSError:
        receipt_json = []
    delta_candidates = _discover_schema_paths(
        [
            *receipt_json,
            *[
                Path(inventory.roots[item.root_label]) / item.relative_path
                for item in files
                if item.extension == ".json" and item.root_label in inventory.roots
            ],
        ],
        "dbx.source_proved_delta_packet",
    )
    bound, delta_holds = _select_delta_packet(
        bound, delta_candidates, isolated if isolated.is_file() else None
    )
    holds.extend(delta_holds)
    return SectionWorkOrder(
        section=section,
        ready_for_extraction=bool(summary and summary.ready_for_extraction),
        missing_required_roles=missing_authority,
        missing_candidate_roles=missing_candidates,
        candidate_role_counts=dict(summary.candidate_role_counts) if summary else {},
        file_count=summary.file_count if summary else 0,
        roots_present=list(summary.roots_present) if summary else [],
        candidate_picks=picks,
        next_commands=_section_commands(
            section,
            root_args=root_args,
            picks=picks,
            receipt_dir=receipt_dir,
            missing_roles=missing_candidates,
            bindings=bound,
        ),
        holds=holds,
    )


def _issue_lines(issues: Sequence[SourceIssue], limit: int = 20) -> List[str]:
    lines = [
        f"{issue.code}:{issue.section or '-'}:{issue.relative_path}:{issue.message}"
        for issue in issues
    ]
    return lines[:limit]


def _discover_json_packets(paths: Sequence[Path]) -> Dict[str, Path]:
    found: Dict[str, Path] = {}
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        slot = DISCOVERABLE_SCHEMAS.get(str(payload.get("schema_id") or ""))
        if slot and slot not in found:
            found[slot] = path
    return found


def _discover_packets(
    files: Sequence[SourceFile],
    roots: Dict[str, str],
    section: int,
) -> Dict[str, Path]:
    return _discover_json_packets(
        [
            Path(roots[item.root_label]) / item.relative_path
            for item in files
            if item.section == section and item.extension == ".json"
        ]
    )


def _discover_receipt_dir_packets(receipt_dir: Path) -> Dict[str, Path]:
    return _discover_json_packets(sorted(receipt_dir.glob("*.json")))


def _queue_has_items(path: Path) -> bool:
    try:
        if not path.is_file():
            return False
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("schema_id") != "dbx.examiner_fill_queue":
        return False
    items = payload.get("items")
    return isinstance(items, list) and bool(items)


def _write_proposed_delta_draft(
    queue_path: Optional[str],
    workbook: Path,
    receipt_dir: Path,
    section: int,
) -> tuple[Optional[str], Optional[str]]:
    dest = receipt_dir / f"section{section}-delta-draft.json"
    if not queue_path:
        if dest.is_file():
            dest.unlink()
        return None, None
    try:
        queue = json.loads(Path(queue_path).read_text(encoding="utf-8"))
        if not isinstance(queue, dict):
            return None, "examiner queue is not a JSON object"
        deltas = proposed_deltas_from_queue(queue)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ExaminerQueueError,
    ) as exc:
        return None, str(exc)
    if not deltas:
        if dest.is_file():
            dest.unlink()
        return None, None
    try:
        write_delta_draft(
            workbook=workbook,
            deltas=deltas,
            output=dest,
            packet_id=f"SECTION{section}-DELTA",
        )
    except (OSError, IsolatedDeltaError) as exc:
        return None, str(exc)
    return str(dest), None


def _write_onesource_template(
    queue_path: Optional[str],
    workbook: Path,
    receipt_dir: Path,
    section: int,
) -> tuple[Optional[str], Optional[str]]:
    dest = receipt_dir / f"section{section}-onesource-template.json"
    if not queue_path:
        if dest.is_file():
            dest.unlink()
        return None, None
    try:
        queue = json.loads(Path(queue_path).read_text(encoding="utf-8"))
        if not isinstance(queue, dict):
            return None, "examiner queue is not a JSON object"
        rows = onesource_rows_from_queue(queue)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ExaminerQueueError,
    ) as exc:
        return None, str(exc)
    if not rows:
        if dest.is_file():
            dest.unlink()
        return None, None
    try:
        write_onesource_template(
            workbook=workbook,
            rows=rows,
            output=dest,
            packet_id=f"SECTION{section}-ONESOURCE",
        )
    except (OSError, IsolatedDeltaError) as exc:
        return None, str(exc)
    return str(dest), None


def _write_examiner_queue(
    index_packet: Optional[Path],
    workbook: Path,
    receipt_dir: Path,
    section: int,
) -> tuple[Optional[str], Optional[str], int, int]:
    if index_packet is None or not index_packet.is_file() or not workbook.is_file():
        return None, None, 0, 0
    try:
        packet = json.loads(index_packet.read_text(encoding="utf-8"))
        if not isinstance(packet, dict):
            return None, "index packet is not a JSON object", 0, 0
        queue = build_examiner_queue(
            packet,
            workbook,
            packet_id=f"SECTION{section}-QUEUE",
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ExaminerQueueError) as exc:
        return None, str(exc), 0, 0
    dest = receipt_dir / f"section{section}-examiner-queue.json"
    dest.write_text(json.dumps(queue, indent=2, sort_keys=True), encoding="utf-8")
    return (
        str(dest),
        None,
        int(queue.get("blank_count") or 0),
        int(queue.get("conflict_count") or 0),
    )


def _packet_digest_field(path: Path, field: str) -> Optional[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    digest = payload.get(field)
    if isinstance(digest, str) and len(digest) == 64:
        return digest.casefold()
    return None


def _packet_workbook_sha256(path: Path) -> Optional[str]:
    return _packet_digest_field(path, "workbook_sha256")


def _packet_source_workbook_sha256(path: Path) -> Optional[str]:
    return _packet_digest_field(path, "source_workbook_sha256")


def _discover_schema_paths(paths: Sequence[Path], schema_id: str) -> List[Path]:
    found: List[Path] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("schema_id") == schema_id:
            found.append(path)
    return found


def _isolated_delta_generation(path: Path, section: int) -> Optional[int]:
    name = path.name
    if name == f"section{section}-delta.xlsx":
        return 1
    prefix = f"section{section}-delta-"
    if name.startswith(prefix) and name.endswith(".xlsx"):
        token = name[len(prefix) : -5]
        if token.isdigit() and int(token) >= 2:
            return int(token)
    return None


def _latest_isolated_path(receipt_dir: Path, section: int) -> Optional[Path]:
    best: Optional[Path] = None
    best_gen = 0
    try:
        candidates = list(receipt_dir.glob(f"section{section}-delta*.xlsx"))
    except OSError:
        candidates = []
    for path in candidates:
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        generation = _isolated_delta_generation(path, section)
        if generation is None:
            continue
        if generation > best_gen:
            best_gen = generation
            best = path
    if best is not None:
        return best
    letter = receipt_dir / f"section{section}-letter.xlsx"
    try:
        if letter.is_file():
            return letter
    except OSError:
        return None
    return None


def _next_delta_output(receipt_dir: Path, section: int) -> Path:
    latest = _latest_isolated_path(receipt_dir, section)
    generation = (
        _isolated_delta_generation(latest, section)
        if latest is not None
        else None
    )
    if generation is None:
        return receipt_dir / f"section{section}-delta.xlsx"
    return receipt_dir / f"section{section}-delta-{generation + 1}.xlsx"


def _select_delta_packet(
    bindings: FinishBindings,
    candidates: Sequence[Path],
    workbook: Optional[Path],
) -> tuple[FinishBindings, List[str]]:
    """Bind a delta packet only when it matches the current isolated hash."""
    ordered: List[Path] = []
    if bindings.delta_packet is not None:
        ordered.append(bindings.delta_packet)
    for path in candidates:
        if path not in ordered:
            ordered.append(path)
    if workbook is None or not workbook.is_file() or not ordered:
        return bindings, []
    actual = sha256_file(workbook)
    for path in ordered:
        if _packet_source_workbook_sha256(path) == actual:
            if bindings.delta_packet == path:
                return bindings, []
            return replace(bindings, delta_packet=path), []
    if bindings.delta_packet is not None:
        return (
            replace(bindings, delta_packet=None),
            [
                "Source-proved delta packet is bound to a different workbook "
                "hash; attest a new draft against the current isolated workbook"
            ],
        )
    return bindings, []


def _archive_applied_delta_packet(
    packet: Path,
    receipt_dir: Path,
) -> Optional[str]:
    try:
        if packet.parent.resolve() != receipt_dir.resolve():
            return None
        digest = _packet_source_workbook_sha256(packet) or "unknown"
        dest = receipt_dir / f"{packet.stem}-applied-{digest[:8]}.json"
        if dest.exists():
            return None
        packet.rename(dest)
    except OSError:
        return None
    return str(dest)


def _unbind_stale_workbook_packets(
    bindings: FinishBindings,
    workbook: Optional[Path],
) -> tuple[FinishBindings, List[str]]:
    """Drop native-print and owner-review packets that do not match isolated bytes."""
    if workbook is None or not workbook.is_file():
        return bindings, []
    actual = sha256_file(workbook)
    holds: List[str] = []
    native = bindings.native_print_receipt
    release = bindings.human_release_token
    if native is not None and _packet_workbook_sha256(native) != actual:
        holds.append(
            "Native print receipt is bound to a different workbook hash; "
            "reprint the current isolated workbook"
        )
        native = None
    if release is not None and _packet_workbook_sha256(release) != actual:
        holds.append(
            "Owner-review token is bound to a different workbook hash; "
            "reissue it against the current isolated workbook"
        )
        release = None
    if (
        native is bindings.native_print_receipt
        and release is bindings.human_release_token
    ):
        return bindings, holds
    return (
        replace(
            bindings,
            native_print_receipt=native,
            human_release_token=release,
        ),
        holds,
    )


def _crop_packet_matches_renders(path: Path, bind_dir: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("schema_id") != "dbx.page_render_crop_packet":
        return False
    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        return False
    bind = bind_dir.expanduser().resolve()
    checked = False
    for raw in pages:
        if not isinstance(raw, dict):
            return False
        relative = raw.get("path")
        digest = raw.get("source_sha256")
        if not isinstance(relative, str) or not relative.strip():
            continue
        checked = True
        render = (bind / relative).resolve()
        if bind not in render.parents and render != bind:
            return False
        if not render.is_file():
            return False
        if sha256_file(render) != str(digest or "").casefold():
            return False
    return True if checked else True


def _unbind_stale_crop_packet(
    bindings: FinishBindings,
    bind_dir: Optional[Path],
) -> tuple[FinishBindings, List[str]]:
    """Drop a crop packet whose page hashes no longer match live renders."""
    packet = bindings.page_render_packet
    if packet is None or bind_dir is None:
        return bindings, []
    try:
        resolved = bind_dir.expanduser().resolve()
        if not resolved.is_dir() or _crop_packet_matches_renders(packet, resolved):
            return bindings, []
    except OSError:
        return bindings, []
    return (
        replace(bindings, page_render_packet=None),
        [
            "Page-render crop packet hashes do not match the current renders; "
            "re-attest section11-crops-draft.json"
        ],
    )


def _current_isolated_workbook(receipt_dir: str, section: int) -> str:
    latest = _latest_isolated_path(Path(receipt_dir), section)
    if latest is not None:
        try:
            return str(latest.resolve())
        except OSError:
            return str(latest)
    return f"{receipt_dir}/section{section}-letter.xlsx"


def _source_document_pdfs(
    inventory: Optional[AcquisitionReceipt],
    section: int,
) -> tuple[Optional[Path], List[Path]]:
    if inventory is None:
        return None, []
    authorized = {
        (match.assertion.root_label, match.assertion.relative_path)
        for match in inventory.authority_matches
        if match.status == "matched"
        and match.assertion.section == section
        and match.assertion.role == "source_document"
    }
    items = [
        item
        for item in inventory.files
        if item.section == section
        and item.extension == ".pdf"
        and item.candidate_role == "source_document"
    ]
    paths: List[Path] = []
    if inventory.snapshot_root:
        snapshot = Path(inventory.snapshot_root)
        for item in items:
            if (item.root_label, item.relative_path) not in authorized:
                continue
            path = snapshot_path_for(inventory, item)
            if path.is_file():
                paths.append(path.resolve())
        if not paths:
            return None, []
        return snapshot.resolve(), paths
    for item in items:
        path = Path(inventory.roots[item.root_label]) / item.relative_path
        if path.is_file():
            paths.append(path.resolve())
    if not paths:
        return None, []
    bind = Path(os.path.commonpath([str(path) for path in paths]))
    if bind.is_file():
        bind = bind.parent
    return bind, paths


def _source_document_renders(
    inventory: Optional[AcquisitionReceipt],
    section: int,
) -> tuple[Optional[Path], List[Path]]:
    """Authorized Phase 2 snapshot renders only. Phase 1 live files stay out."""
    if inventory is None or not inventory.snapshot_root:
        return None, []
    authorized = {
        (match.assertion.root_label, match.assertion.relative_path)
        for match in inventory.authority_matches
        if match.status == "matched"
        and match.assertion.section == section
        and match.assertion.role == "source_document"
    }
    render_ext = {".pdf", *IMAGE_EXTENSIONS}
    paths: List[Path] = []
    snapshot = Path(inventory.snapshot_root)
    for item in inventory.files:
        if item.section != section:
            continue
        if item.extension not in render_ext:
            continue
        if item.candidate_role != "source_document":
            continue
        if (item.root_label, item.relative_path) not in authorized:
            continue
        path = snapshot_path_for(inventory, item)
        if path.is_file():
            paths.append(path.resolve())
    if not paths:
        return None, []
    return snapshot.resolve(), paths


def _write_section_crops_draft(
    receipt_dir: Path,
    section: int,
    inventory: Optional[AcquisitionReceipt] = None,
) -> tuple[Optional[str], Optional[str]]:
    if section != 11:
        return None, None
    dest = receipt_dir / f"section{section}-crops-draft.json"
    examiner = _section_render_bind_dir(receipt_dir, section)
    snap_bind, snap_paths = _source_document_renders(inventory, section)
    try:
        if examiner is not None:
            write_crops_draft(
                output=dest,
                packet_id=f"SECTION{section}-CROPS",
                bind_dir=examiner,
            )
        elif snap_bind is not None:
            write_crops_draft(
                output=dest,
                packet_id=f"SECTION{section}-CROPS",
                bind_dir=snap_bind,
                paths=snap_paths,
            )
        else:
            write_crops_draft(
                output=dest,
                packet_id=f"SECTION{section}-CROPS",
            )
    except (OSError, PageRenderExportError) as exc:
        return None, str(exc)
    return str(dest), None


def _write_crop_fill_queue(
    crops_draft: Optional[str],
    receipt_dir: Path,
    section: int,
) -> tuple[Optional[str], Optional[str], int]:
    dest = receipt_dir / f"section{section}-crop-fill-queue.json"
    if section != 11 or not crops_draft:
        if dest.is_file():
            dest.unlink()
        return None, None, 0
    try:
        draft = json.loads(Path(crops_draft).read_text(encoding="utf-8"))
        if not isinstance(draft, dict):
            return None, "crops draft is not a JSON object", 0
        queue = crop_fill_queue_from_draft(draft)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        PageRenderExportError,
    ) as exc:
        return None, str(exc), 0
    items = queue.get("items")
    count = len(items) if isinstance(items, list) else 0
    if count == 0:
        if dest.is_file():
            dest.unlink()
        return None, None, 0
    dest.write_text(json.dumps(queue, indent=2, sort_keys=True), encoding="utf-8")
    return str(dest), None, count


def _crops_bind_dir(
    receipt_dir: Path,
    section: int,
    inventory: Optional[AcquisitionReceipt],
    crops_draft: Optional[str],
) -> Optional[Path]:
    examiner = _section_render_bind_dir(receipt_dir, section)
    if examiner is not None:
        return examiner
    snap_bind, _ = _source_document_renders(inventory, section)
    if snap_bind is not None:
        return snap_bind
    if not crops_draft:
        return None
    try:
        payload = json.loads(Path(crops_draft).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    bind_text = payload.get("bind_dir") if isinstance(payload, dict) else ""
    if isinstance(bind_text, str) and bind_text.strip():
        candidate = Path(bind_text)
        try:
            if candidate.is_dir():
                return candidate.resolve()
        except OSError:
            return None
    return None


def _section_render_bind_dir(receipt_dir: Path, section: int) -> Optional[Path]:
    for name in (f"section{section}-renders", f"section{section}-crops"):
        candidate = receipt_dir / name
        try:
            if candidate.is_dir():
                return candidate.resolve()
        except OSError:
            continue
    return None


def _source_handwritten_scans(
    inventory: Optional[AcquisitionReceipt],
    section: int,
) -> tuple[Optional[Path], List[Path]]:
    """Authorized Phase 2 snapshot handwritten scans only. Phase 1 stays out."""
    if inventory is None or not inventory.snapshot_root:
        return None, []
    authorized = {
        (match.assertion.root_label, match.assertion.relative_path)
        for match in inventory.authority_matches
        if match.status == "matched"
        and match.assertion.section == section
        and match.assertion.role == "handwritten_index"
    }
    scan_ext = {".pdf", *IMAGE_EXTENSIONS}
    paths: List[Path] = []
    snapshot = Path(inventory.snapshot_root)
    for item in inventory.files:
        if item.section != section:
            continue
        if item.extension not in scan_ext:
            continue
        if item.candidate_role != "handwritten_index":
            continue
        if (item.root_label, item.relative_path) not in authorized:
            continue
        path = snapshot_path_for(inventory, item)
        if path.is_file():
            paths.append(path.resolve())
    if not paths:
        return None, []
    return snapshot.resolve(), paths


def _section_handwritten_scan_dir(receipt_dir: Path, section: int) -> Optional[Path]:
    candidate = receipt_dir / f"section{section}-handwritten-scans"
    try:
        if candidate.is_dir():
            return candidate.resolve()
    except OSError:
        return None
    return None


def _write_section_handwritten_scan_draft(
    receipt_dir: Path,
    section: int,
    inventory: Optional[AcquisitionReceipt] = None,
) -> tuple[Optional[str], Optional[str]]:
    dest = receipt_dir / f"section{section}-handwritten-scan-draft.json"
    examiner = _section_handwritten_scan_dir(receipt_dir, section)
    snap_bind, snap_paths = _source_handwritten_scans(inventory, section)
    try:
        if examiner is not None:
            write_handwritten_scan_draft(
                output=dest,
                packet_id=f"SECTION{section}-HANDWRITTEN",
                bind_dir=examiner,
            )
        elif snap_bind is not None:
            write_handwritten_scan_draft(
                output=dest,
                packet_id=f"SECTION{section}-HANDWRITTEN",
                bind_dir=snap_bind,
                paths=snap_paths,
            )
        else:
            write_handwritten_scan_draft(
                output=dest,
                packet_id=f"SECTION{section}-HANDWRITTEN",
            )
    except (OSError, HandwrittenScanError) as exc:
        return None, str(exc)
    return str(dest), None


def _write_handwritten_scan_queue(
    draft_path: Optional[str],
    receipt_dir: Path,
    section: int,
) -> tuple[Optional[str], Optional[str], int]:
    dest = receipt_dir / f"section{section}-handwritten-scan-queue.json"
    if not draft_path:
        if dest.is_file():
            dest.unlink()
        return None, None, 0
    try:
        draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
        if not isinstance(draft, dict):
            return None, "handwritten-scan draft is not a JSON object", 0
        queue = handwritten_scan_queue_from_draft(draft)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        HandwrittenScanError,
    ) as exc:
        return None, str(exc), 0
    items = queue.get("items")
    count = len(items) if isinstance(items, list) else 0
    if count == 0:
        if dest.is_file():
            dest.unlink()
        return None, None, 0
    dest.write_text(json.dumps(queue, indent=2, sort_keys=True), encoding="utf-8")
    return str(dest), None, count


def _source_supporting_records(
    inventory: Optional[AcquisitionReceipt],
    section: int,
) -> tuple[Optional[Path], List[Path]]:
    """Authorized Phase 2 snapshot chat/OCR only. Phase 1 live files stay out."""
    if inventory is None or not inventory.snapshot_root:
        return None, []
    authorized = {
        (match.assertion.root_label, match.assertion.relative_path)
        for match in inventory.authority_matches
        if match.status == "matched"
        and match.assertion.section == section
        and match.assertion.role in {"chat_export", "ocr_text", "supporting_record"}
    }
    paths: List[Path] = []
    snapshot = Path(inventory.snapshot_root)
    for item in inventory.files:
        if item.section != section:
            continue
        if item.candidate_role not in {"chat_export", "ocr_text", "supporting_record"}:
            continue
        if (item.root_label, item.relative_path) not in authorized:
            continue
        path = snapshot_path_for(inventory, item)
        if path.is_file():
            paths.append(path.resolve())
    if not paths:
        return None, []
    return snapshot.resolve(), paths


def _section_supporting_dir(receipt_dir: Path, section: int) -> Optional[Path]:
    for name in (
        f"section{section}-supporting",
        f"section{section}-chat",
        f"section{section}-ocr",
    ):
        candidate = receipt_dir / name
        try:
            if candidate.is_dir():
                return candidate.resolve()
        except OSError:
            continue
    return None


def _write_section_supporting_record_draft(
    receipt_dir: Path,
    section: int,
    inventory: Optional[AcquisitionReceipt] = None,
) -> tuple[Optional[str], Optional[str]]:
    dest = receipt_dir / f"section{section}-supporting-record-draft.json"
    examiner = _section_supporting_dir(receipt_dir, section)
    snap_bind, snap_paths = _source_supporting_records(inventory, section)
    try:
        if examiner is not None:
            write_supporting_record_draft(
                output=dest,
                packet_id=f"SECTION{section}-SUPPORTING",
                bind_dir=examiner,
            )
        elif snap_bind is not None:
            write_supporting_record_draft(
                output=dest,
                packet_id=f"SECTION{section}-SUPPORTING",
                bind_dir=snap_bind,
                paths=snap_paths,
            )
        else:
            write_supporting_record_draft(
                output=dest,
                packet_id=f"SECTION{section}-SUPPORTING",
            )
    except (OSError, SupportingRecordError) as exc:
        return None, str(exc)
    return str(dest), None


def _write_supporting_record_queue(
    draft_path: Optional[str],
    receipt_dir: Path,
    section: int,
) -> tuple[Optional[str], Optional[str], int]:
    dest = receipt_dir / f"section{section}-supporting-record-queue.json"
    if not draft_path:
        if dest.is_file():
            dest.unlink()
        return None, None, 0
    try:
        draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
        if not isinstance(draft, dict):
            return None, "supporting-record draft is not a JSON object", 0
        queue = supporting_record_queue_from_draft(draft)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        SupportingRecordError,
    ) as exc:
        return None, str(exc), 0
    items = queue.get("items")
    count = len(items) if isinstance(items, list) else 0
    if count == 0:
        if dest.is_file():
            dest.unlink()
        return None, None, 0
    dest.write_text(json.dumps(queue, indent=2, sort_keys=True), encoding="utf-8")
    return str(dest), None, count


def _write_section_remaining_plan(
    order: SectionWorkOrder,
    receipt_dir: Path,
) -> tuple[Optional[str], Optional[str]]:
    finish_path = receipt_dir / f"section{order.section}-finish.json"
    finish: Optional[Dict[str, object]] = None
    if finish_path.is_file():
        try:
            payload = json.loads(finish_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return None, str(exc)
        if isinstance(payload, dict):
            finish = payload
    try:
        plan = remaining_plan(
            section=order.section,
            finish=finish,
            receipt_dir=receipt_dir,
            holds=order.holds,
            next_commands=order.next_commands,
            missing_required_roles=order.missing_required_roles,
            missing_candidate_roles=order.missing_candidate_roles,
        )
        dest = receipt_dir / f"section{order.section}-remaining-plan.json"
        write_remaining_plan(plan, dest)
    except (OSError, RemainingPlanError) as exc:
        return None, str(exc)
    return str(dest), None


def _section_pdf_bind_dir(receipt_dir: str, section: int) -> Optional[Path]:
    candidate = Path(receipt_dir) / f"section{section}-pdfs"
    try:
        if candidate.is_dir():
            return candidate.resolve()
    except OSError:
        return None
    return None


_SECTION_MARK = re.compile(r"(?:section|p)(\d+)", re.IGNORECASE)


def _census_packet_matches_section(path: Path, section: int) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("schema_id") != "dbx.pdf_page_census_packet":
        return False
    token = str(payload.get("packet_id") or "")
    name = path.name
    for text in (token, name):
        for match in _SECTION_MARK.finditer(text):
            if int(match.group(1)) == section:
                return True
    return False


def _section_census_packet(
    candidate: Optional[Path],
    receipt_dir: str,
    section: int,
) -> Optional[Path]:
    if candidate is not None and _census_packet_matches_section(candidate, section):
        return candidate
    conventional = Path(receipt_dir) / f"section{section}-pdf-census-packet.json"
    try:
        if conventional.is_file() and _census_packet_matches_section(
            conventional, section
        ):
            return conventional
    except OSError:
        return candidate
    return None


def _bind_section_census(
    bindings: FinishBindings,
    receipt_dir: str,
    section: int,
    inventory: Optional[AcquisitionReceipt] = None,
) -> FinishBindings:
    packet = _section_census_packet(
        bindings.pdf_census_packet, receipt_dir, section
    )
    bind_dir = bindings.pdf_bind_dir
    if bind_dir is None:
        bind_dir = _section_pdf_bind_dir(receipt_dir, section)
    if bind_dir is None:
        bind_dir, _paths = _source_document_pdfs(inventory, section)
    return replace(bindings, pdf_census_packet=packet, pdf_bind_dir=bind_dir)


def _inventory_pdf_census(
    bindings: FinishBindings,
    receipt_dir: Path,
    section: int,
    inventory: Optional[AcquisitionReceipt] = None,
) -> tuple[FinishBindings, Optional[str], Optional[str]]:
    bound = _bind_section_census(
        bindings, str(receipt_dir), section, inventory=inventory
    )
    examiner_dir = _section_pdf_bind_dir(str(receipt_dir), section)
    snapshot_bind, snapshot_paths = _source_document_pdfs(inventory, section)
    auto_paths: Optional[List[Path]] = None
    if bound.pdf_bind_dir is None:
        return bound, None, None
    can_write = examiner_dir is not None and bound.pdf_bind_dir == examiner_dir
    if (
        not can_write
        and snapshot_bind is not None
        and inventory is not None
        and inventory.snapshot_root
    ):
        bound = replace(bound, pdf_bind_dir=snapshot_bind)
        auto_paths = snapshot_paths
        can_write = True
    if bound.pdf_census_packet is not None:
        return bound, None, None
    if not can_write:
        return bound, None, None
    dest = receipt_dir / f"section{section}-pdf-census-packet.json"
    try:
        write_inventory_packet(
            bind_dir=bound.pdf_bind_dir,
            output=dest,
            packet_id=f"SECTION{section}-CENSUS",
            paths=auto_paths,
        )
    except (OSError, PdfCensusError) as exc:
        return bound, None, str(exc)
    return replace(bound, pdf_census_packet=dest), str(dest), None


def _write_empty_text_queue(
    bound: FinishBindings,
    receipt_dir: Path,
    section: int,
) -> tuple[Optional[str], Optional[str], int]:
    dest = receipt_dir / f"section{section}-empty-text-queue.json"
    receipt_path = receipt_dir / f"section{section}-pdf-census-receipt.json"
    if bound.pdf_census_packet is None or bound.pdf_bind_dir is None:
        if dest.is_file():
            dest.unlink()
        return None, None, 0
    try:
        packet = json.loads(Path(bound.pdf_census_packet).read_text(encoding="utf-8"))
        if not isinstance(packet, dict):
            return None, "PDF census packet is not a JSON object", 0
        receipt = census_packet(packet, bind_dir=bound.pdf_bind_dir)
        receipt_path.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        queue = write_empty_text_queue(packet, receipt, dest)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        PdfCensusError,
    ) as exc:
        return None, str(exc), 0
    items = queue.get("items")
    count = len(items) if isinstance(items, list) else 0
    if count == 0:
        if dest.is_file():
            dest.unlink()
        return str(receipt_path), None, 0
    return str(dest), None, count


def _merge_bindings(
    explicit: FinishBindings,
    discovered: Dict[str, Path],
) -> FinishBindings:
    merged = FinishBindings(
        page_render_packet=explicit.page_render_packet,
        native_print_receipt=explicit.native_print_receipt,
        human_release_token=explicit.human_release_token,
        pdf_census_packet=explicit.pdf_census_packet,
        pdf_bind_dir=explicit.pdf_bind_dir,
        drive_readback=explicit.drive_readback,
        authority_manifest=explicit.authority_manifest,
        project_manifest=explicit.project_manifest,
        snapshot_directory=explicit.snapshot_directory,
        delta_packet=explicit.delta_packet,
    )
    if merged.delta_packet is None:
        merged.delta_packet = discovered.get("delta_packet")
    if merged.page_render_packet is None:
        merged.page_render_packet = discovered.get("page_render_packet")
    if merged.native_print_receipt is None:
        merged.native_print_receipt = discovered.get("native_print_receipt")
    if merged.human_release_token is None:
        merged.human_release_token = discovered.get("human_release_token")
    if merged.pdf_census_packet is None:
        merged.pdf_census_packet = discovered.get("pdf_census_packet")
    return merged


def _discover_promoted_controls(
    receipt_dir: Path,
) -> tuple[Optional[Path], Optional[Path]]:
    authority = receipt_dir / "source-authority.json"
    project = receipt_dir / "project_manifest.json"
    if not authority.is_file() or not project.is_file():
        return None, None
    try:
        authority_payload = json.loads(authority.read_text(encoding="utf-8"))
        project_payload = json.loads(project.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None
    if not isinstance(authority_payload, dict) or not isinstance(project_payload, dict):
        return None, None
    if (
        authority_payload.get("schema_id") != "dbx.source_authority_manifest"
        or project_payload.get("schema_id") != "dbx.project_manifest"
    ):
        return None, None
    return authority, project


def _complete_draft_sections(
    draft: Dict[str, object],
    required_roles: Sequence[str],
) -> List[int]:
    complete: List[int] = []
    authorities = draft.get("authorities") or []
    if not isinstance(authorities, list):
        return complete
    for section in PRIORITY_SECTIONS:
        present = {
            item.get("role")
            for item in authorities
            if isinstance(item, dict) and item.get("section") == section
        }
        if all(role in present for role in required_roles):
            complete.append(section)
    return complete


def _bind_picks_to_snapshot(
    picks: Sequence[CandidatePick],
    receipt: AcquisitionReceipt,
) -> List[CandidatePick]:
    authorized = {
        (match.assertion.root_label, match.assertion.relative_path)
        for match in receipt.authority_matches
        if match.status == "matched"
    }
    snapshot = Path(receipt.snapshot_root)
    bound: List[CandidatePick] = []
    for pick in picks:
        key = (pick.root_label, pick.relative_path)
        if key not in authorized:
            continue
        path = snapshot / pick.root_label / pick.relative_path
        if not path.is_file():
            continue
        note = pick.note
        extra = "bound to verified authority snapshot"
        note = f"{note}; {extra}" if note else extra
        bound.append(replace(pick, path=str(path), note=note))
    if not any(pick.slot == "candidate" for pick in bound):
        master = next((pick for pick in bound if pick.slot == "master"), None)
        if master is not None and master.exportable:
            bound.append(
                replace(
                    master,
                    slot="candidate",
                    note=(
                        "Candidate is the snapshot master; live working "
                        "workbooks are not authorized"
                    ),
                )
            )
    return bound


def _same_hash_readback(
    inventory: Optional[AcquisitionReceipt],
    workbook: Path,
    receipt_dir: Path,
) -> Optional[Path]:
    digest = sha256_file(workbook)
    exclude = workbook.resolve()
    candidates: List[Path] = []
    if inventory is not None:
        for item in inventory.files:
            if item.sha256 != digest:
                continue
            candidates.append(
                Path(inventory.roots[item.root_label]) / item.relative_path
            )
    candidates.extend(path for path in receipt_dir.glob("*.xlsx"))
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved == exclude:
            continue
        try:
            if sha256_file(resolved) == digest:
                return resolved
        except OSError:
            continue
    return None


def _drive_section_dir(
    inventory: Optional[AcquisitionReceipt],
    section: int,
) -> Optional[Path]:
    if inventory is None or "drive" not in inventory.roots:
        return None
    root = Path(inventory.roots["drive"])
    try:
        if not root.is_dir():
            return None
        if root.resolve() == REPO_ROOT or REPO_ROOT in root.resolve().parents:
            return None
    except OSError:
        return None
    for item in inventory.files:
        if item.root_label != "drive" or item.section != section:
            continue
        parts = Path(item.relative_path).parts
        if not parts:
            continue
        candidate = root / parts[0]
        try:
            if candidate.is_dir():
                return candidate.resolve()
        except OSError:
            continue
    fallback = root / f"Section {section}"
    try:
        if fallback.is_dir():
            return fallback.resolve()
    except OSError:
        return None
    return None


def _publish_isolated_to_drive(
    inventory: Optional[AcquisitionReceipt],
    section: int,
    isolated: Path,
) -> tuple[Optional[Path], Optional[str]]:
    dest_dir = _drive_section_dir(inventory, section)
    if dest_dir is None or not isolated.is_file():
        return None, None
    dest_dir = dest_dir / "Isolated"
    dest = dest_dir / isolated.name
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_resolved = dest.resolve()
        isolated_resolved = isolated.resolve()
        if dest_resolved == isolated_resolved:
            return None, "Drive publish path is the isolated workbook"
        if dest_resolved == REPO_ROOT or REPO_ROOT in dest_resolved.parents:
            return None, "Refusing to publish isolated workbook into this repository"
        if dest.exists():
            if sha256_file(dest) == sha256_file(isolated):
                return dest_resolved, None
            return None, (
                f"Drive already has {dest.name} with a different hash; "
                "not overwritten"
            )
        shutil.copy2(isolated, dest)
        return dest.resolve(), None
    except OSError as exc:
        return None, str(exc)


def _write_workbook_ledger_packets(
    workbook: Path,
    receipt_dir: Path,
    section: int,
) -> tuple[List[str], Optional[str]]:
    try:
        export = workbook_to_tract_export(
            workbook, packet_id=f"SECTION{section}-WORKBOOK"
        )
        occurrence = workbook_to_occurrence_packet(
            workbook, packet_id=f"SECTION{section}-WORKBOOK"
        )
    except (OSError, WorkbookLedgerError) as exc:
        return [], str(exc)
    written: List[str] = []
    export_path = receipt_dir / f"section{section}-workbook-export.json"
    occurrence_path = receipt_dir / f"section{section}-workbook-occurrence.json"
    export_path.write_text(
        json.dumps(export, indent=2, sort_keys=True), encoding="utf-8"
    )
    occurrence_path.write_text(
        json.dumps(occurrence, indent=2, sort_keys=True), encoding="utf-8"
    )
    written.extend([str(export_path), str(occurrence_path)])
    return written, None


def _execute_section(
    order: SectionWorkOrder,
    *,
    root_args: Sequence[str],
    receipt_dir: Path,
    bindings: FinishBindings,
    inventory: Optional[AcquisitionReceipt],
) -> None:
    master = _slot_path(order.candidate_picks, "master")
    pdf_index = _slot_path(order.candidate_picks, "pdf_index")
    handwritten = _slot_path(order.candidate_picks, "handwritten")
    candidate = _slot_path(order.candidate_picks, "candidate")
    discovered = _discover_receipt_dir_packets(receipt_dir)
    if inventory is not None:
        from_roots = _discover_packets(inventory.files, inventory.roots, order.section)
        for slot, path in from_roots.items():
            discovered.setdefault(slot, path)
    bound = _merge_bindings(bindings, discovered)
    snapshot = bound.snapshot_directory
    if snapshot is not None:
        snapshot = snapshot / f"section{order.section}"
    acquisition_receipt = receipt_dir / f"section{order.section}-acquisition.json"
    phase2: Optional[AcquisitionReceipt] = None
    if (
        bound.authority_manifest is not None
        and bound.project_manifest is not None
        and snapshot is not None
    ):
        try:
            phase2 = ensure_authority_snapshot(
                roots=root_args,
                sections=[order.section],
                authority_manifest=bound.authority_manifest,
                project_manifest=bound.project_manifest,
                snapshot_directory=snapshot,
                acquisition_receipt=acquisition_receipt,
            )
        except (OSError, SourceAcquisitionError) as exc:
            order.execute_error = str(exc)
            return
        order.candidate_picks = _bind_picks_to_snapshot(
            order.candidate_picks, phase2
        )
        master = _slot_path(order.candidate_picks, "master")
        pdf_index = _slot_path(order.candidate_picks, "pdf_index")
        handwritten = _slot_path(order.candidate_picks, "handwritten")
        candidate = _slot_path(order.candidate_picks, "candidate")
    bound, inventoried, inventory_error = _inventory_pdf_census(
        bound,
        receipt_dir,
        order.section,
        inventory=phase2,
    )
    if inventory_error:
        order.holds.append(f"PDF census inventory failed: {inventory_error}")
    empty_queue, empty_error, empty_count = _write_empty_text_queue(
        bound, receipt_dir, order.section
    )
    if empty_queue:
        order.executed_outputs.append(empty_queue)
    if empty_error:
        order.holds.append(f"Empty-text PDF queue failed: {empty_error}")
    elif empty_count:
        order.holds.append(
            f"{empty_count} image-only PDF(s) still have empty extracted text; "
            f"see section{order.section}-empty-text-queue.json"
        )
    handwritten_draft, handwritten_error = _write_section_handwritten_scan_draft(
        receipt_dir, order.section, inventory=phase2
    )
    if handwritten_draft:
        order.executed_outputs.append(handwritten_draft)
    if handwritten_error:
        order.holds.append(
            f"Handwritten-scan draft failed: {handwritten_error}"
        )
    handwritten_queue, handwritten_queue_error, scan_count = (
        _write_handwritten_scan_queue(
            handwritten_draft, receipt_dir, order.section
        )
    )
    if handwritten_queue:
        order.executed_outputs.append(handwritten_queue)
    if handwritten_queue_error:
        order.holds.append(
            f"Handwritten-scan queue failed: {handwritten_queue_error}"
        )
    elif scan_count:
        order.holds.append(
            f"{scan_count} handwritten scan(s) still need a Penterra xlsx; "
            f"see section{order.section}-handwritten-scan-queue.json"
        )
    supporting_draft, supporting_error = _write_section_supporting_record_draft(
        receipt_dir, order.section, inventory=phase2
    )
    if supporting_draft:
        order.executed_outputs.append(supporting_draft)
    if supporting_error:
        order.holds.append(
            f"Supporting-record draft failed: {supporting_error}"
        )
    supporting_queue, supporting_queue_error, support_count = (
        _write_supporting_record_queue(
            supporting_draft, receipt_dir, order.section
        )
    )
    if supporting_queue:
        order.executed_outputs.append(supporting_queue)
    if supporting_queue_error:
        order.holds.append(
            f"Supporting-record queue failed: {supporting_queue_error}"
        )
    elif support_count:
        order.holds.append(
            f"{support_count} chat/OCR file(s) are review-only; "
            f"see section{order.section}-supporting-record-queue.json"
        )
    crops_draft, crops_error = _write_section_crops_draft(
        receipt_dir, order.section, inventory=phase2
    )
    if crops_draft:
        order.executed_outputs.append(crops_draft)
    if crops_error:
        order.holds.append(f"Page-render crops draft failed: {crops_error}")
    queue_path, queue_error, crop_blanks = _write_crop_fill_queue(
        crops_draft, receipt_dir, order.section
    )
    if queue_path:
        order.executed_outputs.append(queue_path)
    if queue_error:
        order.holds.append(f"Crop fill queue failed: {queue_error}")
    elif crop_blanks:
        order.holds.append(
            f"{crop_blanks} page-render crop(s) still need face text; "
            f"see section{order.section}-crop-fill-queue.json"
        )
    crops_bind = _crops_bind_dir(
        receipt_dir, order.section, phase2, crops_draft
    )
    bound, crop_holds = _unbind_stale_crop_packet(bound, crops_bind)
    order.holds.extend(crop_holds)
    if not any((master, pdf_index, handwritten, bound.page_render_packet)):
        order.execute_error = "no exportable source workbooks or page-render packet"
        order.next_commands = _section_commands(
            order.section,
            root_args=root_args,
            picks=order.candidate_picks,
            receipt_dir=str(receipt_dir),
            missing_roles=order.missing_candidate_roles,
            bindings=bound,
        )
        return
    packet_path = receipt_dir / f"section{order.section}-index-packet.json"
    finish_path = receipt_dir / f"section{order.section}-finish.json"
    repair_dir = receipt_dir / f"section{order.section}-repair"
    letter_path = receipt_dir / f"section{order.section}-letter.xlsx"
    reuse_isolated = letter_path.exists()
    try:
        index_packet_path = None
        if any((master, pdf_index, handwritten)):
            packet = export_index_packet(
                f"SECTION{order.section}-INDEX",
                master=Path(master) if master else None,
                pdf_index=Path(pdf_index) if pdf_index else None,
                handwritten=Path(handwritten) if handwritten else None,
                candidate=Path(candidate) if candidate else None,
            )
            packet_path.write_text(
                json.dumps(packet, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            index_packet_path = packet_path
        workbook = None
        repair = None
        letter = None
        if reuse_isolated:
            workbook = letter_path
        elif candidate:
            workbook = Path(candidate)
            if not repair_dir.exists() or not any(repair_dir.iterdir()):
                repair = repair_dir
            letter = letter_path
        latest = _latest_isolated_path(receipt_dir, order.section)
        if latest is not None and _isolated_delta_generation(latest, order.section):
            workbook = latest
            repair = None
            letter = None
        delta_paths = list(sorted(receipt_dir.glob("*.json")))
        if inventory is not None:
            delta_paths.extend(
                Path(inventory.roots[item.root_label]) / item.relative_path
                for item in inventory.files
                if item.section == order.section
                and item.extension == ".json"
                and item.root_label in inventory.roots
            )
        delta_candidates = _discover_schema_paths(
            delta_paths, "dbx.source_proved_delta_packet"
        )
        bound, delta_holds = _select_delta_packet(bound, delta_candidates, workbook)
        order.holds.extend(delta_holds)
        delta_packet = None
        delta_output = None
        applying_delta = False
        if bound.delta_packet is not None and workbook is not None:
            repair = None
            letter = None
            delta_packet = bound.delta_packet
            delta_output = _next_delta_output(receipt_dir, order.section)
            applying_delta = True
        current_book = (
            latest
            if latest is not None and not applying_delta
            else None
            if applying_delta
            else letter_path
            if reuse_isolated
            else None
        )
        if current_book is not None:
            bound, stale_holds = _unbind_stale_workbook_packets(bound, current_book)
            order.holds.extend(stale_holds)
        if bound.drive_readback is None and current_book is not None:
            bound.drive_readback = _same_hash_readback(
                inventory,
                current_book,
                receipt_dir,
            )
        finish_native = None if applying_delta else bound.native_print_receipt
        finish_release = None if applying_delta else bound.human_release_token
        finish_readback = None if applying_delta else bound.drive_readback
        finish = run_finish(
            sections=[order.section],
            roots=list(root_args),
            connect_status=True,
            index_packet=index_packet_path,
            workbook=workbook,
            repair_dir=repair,
            print_layout_output=letter,
            page_render_packet=bound.page_render_packet,
            native_print_receipt=finish_native,
            human_release_token=finish_release,
            pdf_census_packet=bound.pdf_census_packet,
            pdf_bind_dir=bound.pdf_bind_dir,
            drive_readback=finish_readback,
            delta_packet=delta_packet,
            delta_output=delta_output,
            authority_manifest=bound.authority_manifest,
            project_manifest=bound.project_manifest,
            snapshot_directory=snapshot,
            acquisition_receipt=acquisition_receipt
            if bound.authority_manifest is not None
            else None,
        )
        finish_path.write_text(
            json.dumps(finish.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        order.executed = True
        order.finish_technical_pass = finish.technical_pass
        order.finish_packages_complete = finish.packages_complete
        order.executed_outputs = [str(finish_path)]
        if crops_draft:
            order.executed_outputs.append(crops_draft)
        if queue_path:
            order.executed_outputs.append(queue_path)
        if empty_queue:
            order.executed_outputs.append(empty_queue)
        if handwritten_draft:
            order.executed_outputs.append(handwritten_draft)
        if handwritten_queue:
            order.executed_outputs.append(handwritten_queue)
        if supporting_draft:
            order.executed_outputs.append(supporting_draft)
        if supporting_queue:
            order.executed_outputs.append(supporting_queue)
        if index_packet_path is not None:
            order.executed_outputs.append(str(index_packet_path))
        if letter_path.exists():
            order.executed_outputs.append(str(letter_path))
        isolated_ok = any(
            getattr(gate, "name", "") == "isolated_delta"
            and getattr(gate, "technical_pass", False)
            for gate in finish.gates
        )
        if applying_delta and isolated_ok and bound.delta_packet is not None:
            archived = _archive_applied_delta_packet(
                bound.delta_packet, receipt_dir
            )
            if archived:
                order.executed_outputs.append(archived)
            bound = replace(bound, delta_packet=None)
        latest = _latest_isolated_path(receipt_dir, order.section)
        if latest is not None:
            order.executed_outputs.append(str(latest))
        if acquisition_receipt.is_file():
            order.executed_outputs.append(str(acquisition_receipt))
        if inventoried:
            order.executed_outputs.append(inventoried)
        isolated = latest if latest is not None else (
            letter_path if letter_path.exists() else None
        )
        if isolated is not None:
            ledger_outputs, ledger_error = _write_workbook_ledger_packets(
                isolated, receipt_dir, order.section
            )
            order.executed_outputs.extend(ledger_outputs)
            if ledger_error:
                order.holds.append(f"Workbook ledger projection failed: {ledger_error}")
            queue_path, queue_error, blanks, conflicts = _write_examiner_queue(
                index_packet_path, isolated, receipt_dir, order.section
            )
            if queue_path:
                order.executed_outputs.append(queue_path)
            if queue_error:
                order.holds.append(f"Examiner fill queue failed: {queue_error}")
            elif blanks or conflicts:
                order.holds.append(
                    f"{blanks} blank required field(s) and {conflicts} "
                    f"conflict(s) remain; see section{order.section}-examiner-queue.json"
                )
            draft_path, draft_error = _write_proposed_delta_draft(
                queue_path, isolated, receipt_dir, order.section
            )
            if draft_path:
                order.executed_outputs.append(draft_path)
            if draft_error:
                order.holds.append(f"Source-proved delta draft failed: {draft_error}")
            template_path, template_error = _write_onesource_template(
                queue_path, isolated, receipt_dir, order.section
            )
            if template_path:
                order.executed_outputs.append(template_path)
            if template_error:
                order.holds.append(
                    f"One-source fill template failed: {template_error}"
                )
            bound, stale_holds = _unbind_stale_workbook_packets(bound, isolated)
            order.holds.extend(stale_holds)
            try:
                draft_path = receipt_dir / f"section{order.section}-native-print-draft.json"
                write_native_print_draft(
                    workbook=isolated,
                    output=draft_path,
                    packet_id=f"SECTION{order.section}-PRINT",
                )
                order.executed_outputs.append(str(draft_path))
            except (OSError, NativePrintError) as exc:
                order.holds.append(f"Native print draft failed: {exc}")
            try:
                release_draft = (
                    receipt_dir / f"section{order.section}-owner-review-draft.json"
                )
                write_human_release_draft(
                    workbook=isolated,
                    output=release_draft,
                    sections=[order.section],
                    packet_id=f"SECTION{order.section}-OWNER-REVIEW",
                )
                order.executed_outputs.append(str(release_draft))
            except (OSError, HumanReleaseError) as exc:
                order.holds.append(f"Owner-review draft failed: {exc}")
            published, publish_hold = _publish_isolated_to_drive(
                inventory, order.section, isolated
            )
            if publish_hold:
                order.holds.append(publish_hold)
            if published is not None:
                order.executed_outputs.append(str(published))
                if bound.drive_readback is None:
                    bound.drive_readback = published
                    finish = run_finish(
                        sections=[order.section],
                        roots=list(root_args),
                        connect_status=True,
                        index_packet=index_packet_path,
                        workbook=isolated,
                        page_render_packet=bound.page_render_packet,
                        native_print_receipt=bound.native_print_receipt,
                        human_release_token=bound.human_release_token,
                        pdf_census_packet=bound.pdf_census_packet,
                        pdf_bind_dir=bound.pdf_bind_dir,
                        drive_readback=published,
                        authority_manifest=bound.authority_manifest,
                        project_manifest=bound.project_manifest,
                        snapshot_directory=snapshot,
                        acquisition_receipt=acquisition_receipt
                        if bound.authority_manifest is not None
                        else None,
                    )
                    finish_path.write_text(
                        json.dumps(finish.to_dict(), indent=2, sort_keys=True),
                        encoding="utf-8",
                    )
                    order.finish_technical_pass = finish.technical_pass
                    order.finish_packages_complete = finish.packages_complete
        if finish.packages_complete:
            order.holds.append(
                "Finish runner reported packages_complete; owner review "
                "only, not an external client delivery"
            )
    except (
        OSError,
        IndexExportError,
        PackageFinishError,
        PcOperatorError,
    ) as exc:
        order.executed = True
        order.execute_error = str(exc)
    order.next_commands = _section_commands(
        order.section,
        root_args=root_args,
        picks=order.candidate_picks,
        receipt_dir=str(receipt_dir),
        missing_roles=order.missing_candidate_roles,
        bindings=bound,
    )
    plan_path, plan_error = _write_section_remaining_plan(order, receipt_dir)
    if plan_path:
        order.executed_outputs.append(plan_path)
    if plan_error:
        order.holds.append(f"Remaining-gates plan failed: {plan_error}")


def build_work_order(
    *,
    roots: Sequence[str] = (),
    sections: Sequence[int] = PRIORITY_SECTIONS,
    receipt_dir: Optional[Path] = None,
    required_roles: Sequence[str] = DEFAULT_REQUIRED_ROLES,
    execute: bool = False,
    bindings: Optional[FinishBindings] = None,
) -> OperatorReceipt:
    if not sections or any(section not in PRIORITY_SECTIONS for section in sections):
        raise PcOperatorError(f"Requested sections must come from {PRIORITY_SECTIONS}")
    if len(sections) != len(set(sections)):
        raise PcOperatorError("Requested sections must be unique")
    if any(role not in SOURCE_ROLES for role in required_roles):
        raise PcOperatorError(f"Required roles must come from {sorted(SOURCE_ROLES)}")
    dest_path: Optional[Path] = None
    if receipt_dir is not None:
        dest_path = assert_private_receipt_dir(receipt_dir)
        dest_path.mkdir(parents=True, exist_ok=True)
    elif execute:
        raise PcOperatorError(
            "--execute requires --receipt-dir outside this repository"
        )
    connections = probe_connections(roots)
    readable = _readable_root_args(connections)
    dest = str(dest_path) if dest_path is not None else _receipt_dir(receipt_dir)
    inventory: Optional[AcquisitionReceipt] = None
    inventory_error = ""
    phase = "blocked"
    if readable:
        try:
            inventory = build_receipt(
                [parse_root(raw) for raw in readable],
                requested_sections=list(sections),
                required_roles=list(required_roles),
            )
            phase = "phase1_inventory"
        except (OSError, SourceAcquisitionError) as exc:
            inventory_error = str(exc)
            phase = "blocked"
    explicit = bindings or FinishBindings()
    if dest_path is not None and explicit.authority_manifest is None:
        found_authority, found_project = _discover_promoted_controls(dest_path)
        if found_authority is not None and found_project is not None:
            explicit.authority_manifest = found_authority
            explicit.project_manifest = found_project
            if explicit.snapshot_directory is None:
                explicit.snapshot_directory = dest_path / "intake-snapshot"
    if dest_path is not None:
        explicit = _merge_bindings(
            explicit, _discover_receipt_dir_packets(dest_path)
        )
    work_orders = [
        _section_work_order(
            section,
            inventory=inventory,
            root_args=readable,
            receipt_dir=dest,
            required_roles=required_roles,
            bindings=explicit,
        )
        for section in sections
    ]
    if (
        execute
        and explicit.snapshot_directory is not None
    ):
        explicit.snapshot_directory = assert_private_receipt_dir(
            explicit.snapshot_directory
        )
        explicit.snapshot_directory.mkdir(parents=True, exist_ok=True)
    if execute and dest_path is not None and phase == "phase1_inventory":
        for order in work_orders:
            _execute_section(
                order,
                root_args=readable,
                receipt_dir=dest_path,
                bindings=explicit,
                inventory=inventory,
            )
    next_actions = list(connections.next_actions)
    if phase != "phase1_inventory":
        next_actions.append(
            "Phase 1 inventory did not run; mount readable pc=/drive= roots "
            "and rerun this operator. Do not start Phase 2 without a "
            "human-approved authority manifest."
        )
    else:
        next_actions.append(
            "Review Phase 1 hashes, then create a human-approved authority "
            "manifest before any Phase 2 snapshot"
        )
        if execute:
            next_actions.append(
                "Executed isolated recon/repair under "
                f"{dest}; review finish receipts and do not copy them into "
                "the public repository"
            )
        else:
            next_actions.append(
                "Run the per-section next_commands on the PC, or rerun with "
                f"--execute --receipt-dir {dest}; never write into the "
                "public repository"
            )
    authority_draft = None
    authority_draft_path = None
    authority_promote_command = None
    if dest_path is not None:
        authority_draft = draft_from_files(
            [] if inventory is None else inventory.files,
            requested_sections=sections,
            required_roles=required_roles,
        )
        draft_path = write_draft(authority_draft, dest_path / "authority-draft.json")
        authority_draft_path = str(draft_path)
        next_actions.append(
            f"Review {authority_draft_path}; it is UNAPPROVED_DRAFT and "
            "cannot bind Phase 2 until a named examiner promotes it to "
            "dbx.source_authority_manifest"
        )
        confirm_sections = _complete_draft_sections(authority_draft, required_roles)
        if confirm_sections and explicit.authority_manifest is None:
            authority_promote_command = build_promote_command(
                draft_path=authority_draft_path,
                output=str(dest_path / "source-authority.json"),
                project_manifest_output=str(dest_path / "project_manifest.json"),
                confirm_sections=confirm_sections,
                roots=readable,
            )
            next_actions.append(
                "Replace EXAMINER_PROJECT_ID, EXAMINER_DECISION_ID, and "
                "EXAMINER_NAME, then run: "
                + authority_promote_command
            )
        if explicit.authority_manifest is not None:
            next_actions.append(
                "Discovered or bound source-authority.json; Phase 2 snapshot "
                "uses intake-snapshot/sectionN under receipt-dir"
            )
    if inventory_error:
        next_actions.append(f"Resolve inventory error: {inventory_error}")
    ready = [order.section for order in work_orders if order.ready_for_extraction]
    missing_files = [
        order.section for order in work_orders if order.missing_candidate_roles
    ]
    missing_authority = [
        order.section for order in work_orders if order.missing_required_roles
    ]
    if missing_files:
        next_actions.append(
            f"Sections still missing classified source files: {missing_files}"
        )
    if missing_authority:
        next_actions.append(
            f"Sections still missing authorized roles: {missing_authority}"
        )
    if ready:
        next_actions.append(
            f"Filename classification marked {ready} ready_for_extraction; "
            "that is not legal authority"
        )
    if execute and phase != "phase1_inventory":
        next_actions.append(
            "Cannot execute recon/repair until readable pc=/drive= roots exist"
        )
    next_actions.append("Do not treat this receipt as package release")
    if dest_path is not None:
        plans: List[Dict[str, object]] = []
        for order in work_orders:
            plan_path, plan_error = _write_section_remaining_plan(order, dest_path)
            if plan_path:
                if plan_path not in order.executed_outputs:
                    order.executed_outputs.append(plan_path)
                try:
                    payload = json.loads(Path(plan_path).read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    payload = None
                if isinstance(payload, dict):
                    plans.append(payload)
            if plan_error:
                order.holds.append(f"Remaining-gates plan failed: {plan_error}")
        if plans:
            bundle_path = dest_path / "remaining-plan.json"
            try:
                write_remaining_plan_bundle(
                    plans,
                    bundle_path,
                    connections=connections.to_dict(),
                )
                next_actions.append(
                    f"Review {bundle_path} in priority order 15, then 13, then 11"
                )
            except (OSError, RemainingPlanError) as exc:
                next_actions.append(f"Remaining-plan bundle failed: {exc}")
    packages_complete = bool(work_orders) and all(
        order.finish_packages_complete is True for order in work_orders
    )
    return OperatorReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        requested_sections=list(sections),
        connections=connections.to_dict(),
        acquisition_phase=phase,
        inventory_technical_pass=(
            None if inventory is None else inventory.technical_pass
        ),
        inventory_issue_count=0 if inventory is None else len(inventory.issues),
        inventory_issues=(
            [inventory_error] if inventory_error else _issue_lines(inventory.issues)
            if inventory is not None
            else []
        ),
        sections=work_orders,
        next_actions=next_actions,
        packages_complete=packages_complete,
        technical_pass=phase == "phase1_inventory",
        authority_draft_path=authority_draft_path,
        authority_draft=authority_draft,
        authority_promote_command=authority_promote_command,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Probe connections and emit a Phase 1 work order for sections "
            "15/13/11. Does not promote a package."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument(
        "--section",
        dest="sections",
        type=int,
        action="append",
        choices=PRIORITY_SECTIONS,
    )
    parser.add_argument(
        "--receipt-dir",
        type=Path,
        help=(
            "Private directory outside this repo. Writes authority-draft.json. "
            "Required with --execute"
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Run isolated index export, recon, and repair into receipt-dir. "
            "Does not copy sources into this repository."
        ),
    )
    parser.add_argument(
        "--require-role",
        action="append",
        dest="required_roles",
        help="Repeat to override required source roles",
    )
    parser.add_argument("--page-render-packet", type=Path)
    parser.add_argument("--native-print-receipt", type=Path)
    parser.add_argument("--human-release-token", type=Path)
    parser.add_argument("--pdf-census-packet", type=Path)
    parser.add_argument("--pdf-bind-dir", type=Path)
    parser.add_argument("--drive-readback", type=Path)
    parser.add_argument("--authority-manifest", type=Path)
    parser.add_argument("--project-manifest", type=Path)
    parser.add_argument("--snapshot-directory", type=Path)
    parser.add_argument("--delta-packet", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        receipt = build_work_order(
            roots=args.root,
            sections=args.sections or list(PRIORITY_SECTIONS),
            receipt_dir=args.receipt_dir,
            required_roles=args.required_roles or DEFAULT_REQUIRED_ROLES,
            execute=args.execute,
            bindings=FinishBindings(
                page_render_packet=args.page_render_packet,
                native_print_receipt=args.native_print_receipt,
                human_release_token=args.human_release_token,
                pdf_census_packet=args.pdf_census_packet,
                pdf_bind_dir=args.pdf_bind_dir,
                drive_readback=args.drive_readback,
                authority_manifest=args.authority_manifest,
                project_manifest=args.project_manifest,
                snapshot_directory=args.snapshot_directory,
                delta_packet=args.delta_packet,
            ),
        )
        args.output.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except (OSError, ConnectStatusError, PcOperatorError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "acquisition_phase": receipt.acquisition_phase,
                "technical_pass": receipt.technical_pass,
                "packages_complete": receipt.packages_complete,
                "authority_draft_path": receipt.authority_draft_path,
                "authority_promote_command": receipt.authority_promote_command,
                "sections": [
                    {
                        "section": order.section,
                        "ready_for_extraction": order.ready_for_extraction,
                        "missing_candidate_roles": order.missing_candidate_roles,
                        "missing_required_roles": order.missing_required_roles,
                        "command_count": len(order.next_commands),
                        "executed": order.executed,
                        "finish_technical_pass": order.finish_technical_pass,
                        "finish_packages_complete": order.finish_packages_complete,
                        "execute_error": order.execute_error,
                    }
                    for order in receipt.sections
                ],
                "next_actions": receipt.next_actions,
            },
            indent=2,
        )
    )
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
