"""PC work-order operator for sections 15, 13, and 11.

Probe connections, run Phase 1 inventory when roots are readable, and emit
per-section next commands. This module never copies client files, never
starts Phase 2 without a human-approved authority manifest, never starts a
second controller, and never claims package completion.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .connect_status import ConnectStatusError, ConnectStatusReceipt, probe_connections
from .index_export import IndexExportError, export_index_packet
from .package_finish import PackageFinishError, run_finish
from .source_acquisition import (
    DEFAULT_REQUIRED_ROLES,
    PRIORITY_SECTIONS,
    SOURCE_ROLES,
    WORKBOOK_EXTENSIONS,
    AcquisitionReceipt,
    SourceAcquisitionError,
    SourceFile,
    SourceIssue,
    build_receipt,
    parse_root,
)

_CANDIDATE_ROLE_EQUIVALENTS = {
    "index": {"index", "handwritten_index"},
}

RECEIPT_SCHEMA_ID = "dbx.pc_operator_receipt"
RECEIPT_SCHEMA_VERSION = "1.1"
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


class PcOperatorError(ValueError):
    """Raised when the PC operator cannot build a safe work order."""


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
            "Do not copy client files into the public repository",
            "Do not start a second Landman Helper controller",
            "technical_pass means readable roots were probed and Phase 1 ran",
            "--execute writes isolated packets under receipt-dir only",
        ]
    )

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


def _pick_role_files(
    files: Sequence[SourceFile],
    section: int,
    role: str,
) -> List[SourceFile]:
    return [
        item
        for item in files
        if item.section == section and item.candidate_role == role
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
    missing: List[str] = []
    for role in required_roles:
        equivalents = _CANDIDATE_ROLE_EQUIVALENTS.get(role, {role})
        if present.isdisjoint(equivalents):
            missing.append(role)
    return missing


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


def _section_commands(
    section: int,
    *,
    root_args: Sequence[str],
    picks: Sequence[CandidatePick],
    receipt_dir: str,
    missing_roles: Sequence[str],
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
        commands.append(_quote_command(finish_parts))
    else:
        commands.append(
            "Export master, PDF, and handwritten indexes to Penterra xlsx "
            "on the PC, then rerun python3 -m horizon.pc_operator"
        )
    if section == 15:
        commands.append(
            "On Windows Excel, Print Preview the isolated Letter copy and "
            "pass --native-print-receipt plus --drive-readback of the same bytes"
        )
    if section == 13:
        commands.append(
            "Pass only a writer-held --delta-packet for source-proved fills; "
            "do not invent legal text from federal page counts"
        )
    if section == 11:
        commands.append(
            "Compile --page-render-packet crops with Book/Page, dates, and "
            "parties; leave bare document numbers bare"
        )
    return commands


def _section_work_order(
    section: int,
    *,
    inventory: Optional[AcquisitionReceipt],
    root_args: Sequence[str],
    receipt_dir: str,
    required_roles: Sequence[str],
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
        ),
        holds=holds,
    )


def _issue_lines(issues: Sequence[SourceIssue], limit: int = 20) -> List[str]:
    lines = [
        f"{issue.code}:{issue.section or '-'}:{issue.relative_path}:{issue.message}"
        for issue in issues
    ]
    return lines[:limit]


def _execute_section(
    order: SectionWorkOrder,
    *,
    root_args: Sequence[str],
    receipt_dir: Path,
) -> None:
    master = _slot_path(order.candidate_picks, "master")
    pdf_index = _slot_path(order.candidate_picks, "pdf_index")
    handwritten = _slot_path(order.candidate_picks, "handwritten")
    candidate = _slot_path(order.candidate_picks, "candidate")
    if not any((master, pdf_index, handwritten)):
        order.execute_error = "no exportable source workbooks"
        return
    packet_path = receipt_dir / f"section{order.section}-index-packet.json"
    finish_path = receipt_dir / f"section{order.section}-finish.json"
    repair_dir = receipt_dir / f"section{order.section}-repair"
    letter_path = receipt_dir / f"section{order.section}-letter.xlsx"
    try:
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
        finish = run_finish(
            sections=[order.section],
            roots=list(root_args),
            connect_status=True,
            index_packet=packet_path,
            workbook=Path(candidate) if candidate else None,
            repair_dir=repair_dir if candidate else None,
            print_layout_output=letter_path if candidate else None,
        )
        finish_path.write_text(
            json.dumps(finish.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        order.executed = True
        order.finish_technical_pass = finish.technical_pass
        order.finish_packages_complete = finish.packages_complete
        order.executed_outputs = [str(packet_path), str(finish_path)]
        if candidate:
            order.executed_outputs.append(str(letter_path))
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


def build_work_order(
    *,
    roots: Sequence[str] = (),
    sections: Sequence[int] = PRIORITY_SECTIONS,
    receipt_dir: Optional[Path] = None,
    required_roles: Sequence[str] = DEFAULT_REQUIRED_ROLES,
    execute: bool = False,
) -> OperatorReceipt:
    if not sections or any(section not in PRIORITY_SECTIONS for section in sections):
        raise PcOperatorError(f"Requested sections must come from {PRIORITY_SECTIONS}")
    if len(sections) != len(set(sections)):
        raise PcOperatorError("Requested sections must be unique")
    if any(role not in SOURCE_ROLES for role in required_roles):
        raise PcOperatorError(f"Required roles must come from {sorted(SOURCE_ROLES)}")
    dest_path: Optional[Path] = None
    if execute:
        if receipt_dir is None:
            raise PcOperatorError(
                "--execute requires --receipt-dir outside this repository"
            )
        dest_path = assert_private_receipt_dir(receipt_dir)
        dest_path.mkdir(parents=True, exist_ok=True)
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
    work_orders = [
        _section_work_order(
            section,
            inventory=inventory,
            root_args=readable,
            receipt_dir=dest,
            required_roles=required_roles,
        )
        for section in sections
    ]
    if execute and dest_path is not None and phase == "phase1_inventory":
        for order in work_orders:
            _execute_section(
                order,
                root_args=readable,
                receipt_dir=dest_path,
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
        help="Private directory named in generated commands; required with --execute",
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
