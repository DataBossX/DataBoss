"""One runner that chains Horizon finish gates without promoting a package.

Run this on the PC or WSL host that can see section roots. It never writes
READY_TO_SUBMIT, never mutates production, and never treats a green gate as
release. Missing inputs produce a blocked receipt that names the next
required packet.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .occurrence_ledger import (
    OccurrenceLedgerError,
    compare_packet,
    parse_occurrence_packet,
)
from .public_cadastral import (
    PublicCadastralError,
    bind_local_plat,
    build_receipt as build_cadastral_receipt,
    fetch_plat,
)
from .reextraction_gate import (
    ReextractionError,
    assess_ledger,
    parse_ledger_export,
    parse_oracle,
)
from .index_export import (
    IndexExportError,
    export_faces,
    export_index_packet,
    refresh_candidate,
)
from .index_reconciliation import (
    IndexReconciliationError,
    reconcile_indexes,
)
from .connect_status import ConnectStatusError, probe_connections
from .drive_readback import (
    DriveReadbackError,
    assess_drive_readback,
    is_drive_isolated_copy,
    isolated_workbook_filename,
)
from .remaining_plan import named_isolated_hops
from .human_release import (
    HumanReleaseError,
    assess_human_release,
    evaluate_package_completion,
)
from .isolated_delta import IsolatedDeltaError, apply_deltas, sha256_file
from .native_print import NativePrintError, assess_native_print
from .occurrence_build import OccurrenceBuildError, build_occurrence_packet
from .workbook_ledger import (
    WorkbookLedgerError,
    workbook_to_occurrence_packet,
    workbook_to_tract_export,
)
from .page_render_export import PageRenderExportError, compile_page_renders
from .pdf_census import PdfCensusError, census_packet
from .print_layout_repair import PrintLayoutRepairError, repair_print_layout
from .repair_loop import RepairLoopError, run_repair_loop
from .project_manifest import ControlFileError
from .source_acquisition import (
    PRIORITY_SECTIONS,
    SourceAcquisitionError,
    bind_phase_two_controls,
    build_receipt as build_acquisition_receipt,
    ensure_authority_snapshot,
    filter_authority_assertions,
    parse_root,
    verify_snapshot,
)
from .workbook_qa import inspect_workbook, load_workbook_profile

RECEIPT_SCHEMA_ID = "dbx.package_finish_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
DEFAULT_WORKBOOK_PROFILE = (
    Path(__file__).resolve().parent / "profiles" / "penterra_index_v1.json"
)
DEFAULT_WORKBOOK_CHECKS = (
    "abstract_required_fields",
    "abstract_print_layout",
)


class PackageFinishError(ValueError):
    """Raised when finish-runner controls are malformed."""


@dataclass
class GateResult:
    name: str
    ran: bool
    technical_pass: Optional[bool]
    detail: Dict[str, object] = field(default_factory=dict)
    error: str = ""


@dataclass
class FinishReceipt:
    generated_utc: str
    requested_sections: List[int]
    gates: List[GateResult]
    next_actions: List[str]
    packages_complete: bool
    technical_pass: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(default_factory=lambda: [
        "packages_complete stays false until a verified snapshot, "
        "source-backed rows, native Excel, Drive Isolated/, human release, "
        "and an empty examiner queue all exist",
        "technical_pass is only the gates that actually ran",
    ])

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def apply_examiner_queue_gaps(
    receipt: FinishReceipt,
    *,
    blank_count: int,
    conflict_count: int,
) -> FinishReceipt:
    """Keep packages_complete false while the examiner queue has gaps."""
    blanks = blank_count if isinstance(blank_count, int) and blank_count > 0 else 0
    conflicts = (
        conflict_count if isinstance(conflict_count, int) and conflict_count > 0 else 0
    )
    if blanks == 0 and conflicts == 0:
        return receipt
    actions = list(receipt.next_actions)
    if blanks:
        line = f"examiner queue has {blanks} blank required field(s)"
        if line not in actions:
            actions.append(line)
    if conflicts:
        line = f"examiner queue has {conflicts} conflict(s)"
        if line not in actions:
            actions.append(line)
    return replace(receipt, packages_complete=False, next_actions=actions)


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageFinishError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PackageFinishError(f"{path} must contain a JSON object")
    return payload


def _acquisition_gate(
    roots: Sequence[str],
    sections: Sequence[int],
    *,
    authority_manifest: Optional[Path] = None,
    project_manifest: Optional[Path] = None,
    snapshot_directory: Optional[Path] = None,
    acquisition_receipt: Optional[Path] = None,
) -> GateResult:
    try:
        if (
            authority_manifest is not None
            and project_manifest is not None
            and snapshot_directory is not None
        ):
            receipt_path = acquisition_receipt or (
                snapshot_directory.expanduser().parent
                / f"{snapshot_directory.expanduser().name}-acquisition.json"
            )
            reused = snapshot_directory.expanduser().exists()
            receipt = ensure_authority_snapshot(
                roots=roots,
                sections=sections,
                authority_manifest=authority_manifest,
                project_manifest=project_manifest,
                snapshot_directory=snapshot_directory,
                acquisition_receipt=receipt_path,
            )
            return GateResult(
                name="source_acquisition",
                ran=True,
                technical_pass=receipt.technical_pass,
                detail={
                    "snapshot_root": receipt.snapshot_root,
                    "phase": "phase2_snapshot",
                    "reused_snapshot": reused,
                    "acquisition_receipt": str(receipt_path),
                    "issue_count": len(receipt.issues),
                },
            )
        assertions, context, snapshot = bind_phase_two_controls(
            authority_manifest=authority_manifest,
            project_manifest=project_manifest,
            snapshot_directory=snapshot_directory,
        )
        assertions = filter_authority_assertions(assertions, sections)
        receipt = build_acquisition_receipt(
            [parse_root(root) for root in roots],
            requested_sections=list(sections),
            authority_assertions=assertions,
            authority_context=context,
            snapshot_directory=snapshot,
        )
        if receipt.snapshot_root and not verify_snapshot(receipt):
            return GateResult(
                name="source_acquisition",
                ran=True,
                technical_pass=False,
                error="Authority snapshot failed verification",
                detail={"snapshot_root": receipt.snapshot_root},
            )
    except (OSError, SourceAcquisitionError, ControlFileError) as exc:
        return GateResult(
            name="source_acquisition",
            ran=True,
            technical_pass=False,
            error=str(exc),
        )
    return GateResult(
        name="source_acquisition",
        ran=True,
        technical_pass=receipt.technical_pass,
        detail={
            "snapshot_root": receipt.snapshot_root,
            "phase": "phase2_snapshot" if receipt.snapshot_root else "phase1_inventory",
            "issue_count": len(receipt.issues),
            "sections": [
                {
                    "section": summary.section,
                    "ready_for_extraction": summary.ready_for_extraction,
                    "missing_required_roles": summary.missing_required_roles,
                }
                for summary in receipt.sections
            ],
        },
    )


def _reextraction_gate(
    packet_path: Path,
    oracle_path: Optional[Path],
) -> GateResult:
    try:
        packet_id, rows = parse_ledger_export(_load_json(packet_path))
        oracle = parse_oracle(_load_json(oracle_path)) if oracle_path else None
        receipt = assess_ledger(packet_id, rows, oracle=oracle)
    except (OSError, ReextractionError, PackageFinishError) as exc:
        return GateResult(
            name="reextraction",
            ran=True,
            technical_pass=False,
            error=str(exc),
        )
    return GateResult(
        name="reextraction",
        ran=True,
        technical_pass=receipt.technical_pass,
        detail={
            "row_count": receipt.row_count,
            "bare_docno_count": receipt.bare_docno_count,
            "next_action": receipt.next_action,
        },
    )


def _occurrence_gate(packet_path: Path) -> GateResult:
    try:
        receipt = compare_packet(parse_occurrence_packet(_load_json(packet_path)))
    except (OSError, OccurrenceLedgerError, PackageFinishError) as exc:
        return GateResult(
            name="occurrence_ledger",
            ran=True,
            technical_pass=False,
            error=str(exc),
        )
    return GateResult(
        name="occurrence_ledger",
        ran=True,
        technical_pass=receipt.technical_pass,
        detail={
            "occurrence_count": receipt.occurrence_count,
            "unique_keys_from_occurrences": receipt.unique_keys_from_occurrences,
            "unique_keys_from_ledger": receipt.unique_keys_from_ledger,
            "candidate_row_count": receipt.candidate_row_count,
            "issue_count": len(receipt.issues),
        },
    )


def _workbook_gate(
    workbook_path: Path,
    profile_path: Optional[Path],
    checks: Sequence[str],
) -> GateResult:
    try:
        profile = load_workbook_profile(profile_path or DEFAULT_WORKBOOK_PROFILE)
        report = inspect_workbook(
            workbook_path,
            list(checks or DEFAULT_WORKBOOK_CHECKS),
            profile=profile,
        )
    except (OSError, ControlFileError, ValueError) as exc:
        return GateResult(
            name="workbook_qa",
            ran=True,
            technical_pass=False,
            error=str(exc),
        )
    findings = [
        {
            "check_id": finding.check_id,
            "code": finding.code,
            "sheet": finding.sheet,
            "cell": finding.cell,
            "message": finding.message,
        }
        for finding in report.findings
    ]
    return GateResult(
        name="workbook_qa",
        ran=True,
        technical_pass=report.score.technical_pass,
        detail={
            "workbook_sha256": report.sha256,
            "findings": findings[:20],
            "finding_count": len(findings),
        },
    )


def _cadastral_gate(plats: Sequence[str]) -> GateResult:
    bindings = []
    try:
        for raw in plats:
            parts = [part.strip() for part in raw.split(",")]
            if len(parts) == 3:
                bindings.append(fetch_plat(parts[0], parts[1], parts[2]))
            elif len(parts) == 4:
                bindings.append(
                    bind_local_plat(parts[0], parts[1], parts[2], Path(parts[3]))
                )
            else:
                raise PublicCadastralError(
                    "Each --public-plat must be county,township,range[,local_pdf]"
                )
        receipt = build_cadastral_receipt(bindings)
    except (OSError, PublicCadastralError) as exc:
        return GateResult(
            name="public_cadastral",
            ran=True,
            technical_pass=False,
            error=str(exc),
        )
    return GateResult(
        name="public_cadastral",
        ran=True,
        technical_pass=receipt.technical_pass,
        detail={
            "plats": [
                {
                    "county": plat.county,
                    "township": plat.township,
                    "range": plat.range_,
                    "sha256": plat.sha256,
                    "size_bytes": plat.size_bytes,
                }
                for plat in receipt.plats
            ]
        },
    )


def _gate_matches_workbook(
    gates: Sequence[GateResult],
    name: str,
    workbook: Optional[Path],
    *,
    require_isolated: bool = False,
) -> bool:
    for gate in gates:
        if gate.name != name or not gate.ran:
            continue
        if not gate.technical_pass:
            return False
        if require_isolated and gate.detail.get("isolated_copy") is not True:
            return False
        if workbook is None:
            return True
        try:
            digest = sha256_file(workbook)
        except OSError:
            return False
        bound = gate.detail.get("workbook_sha256") or gate.detail.get(
            "readback_sha256"
        )
        if not isinstance(bound, str) or not bound:
            return False
        return bound.casefold() == digest.casefold()
    return False


def _next_actions(
    gates: Sequence[GateResult],
    sections: Sequence[int],
    workbook: Optional[Path] = None,
) -> List[str]:
    ran = {gate.name for gate in gates if gate.ran}
    actions = []
    if "source_acquisition" not in ran:
        actions.append(
            "Mount PC/Drive/chat roots and rerun with --root "
            f"for sections {list(sections)}"
        )
    if "connect_status" not in ran:
        actions.append(
            "Pass --connect-status with --root pc=<abs> --root drive=<abs> "
            "on the host that can see section files"
        )
    if "page_render_export" not in ran and "reextraction" not in ran:
        actions.append(
            "Compile page-render crops with --page-render-packet, pass "
            "a tract-ledger JSON via --tract-export, or pass --workbook "
            "so the isolated index can be projected"
        )
    if "pdf_census" not in ran:
        actions.append(
            "Pass --pdf-census-packet and --pdf-bind-dir to bind federal "
            "casefile page counts and flag image-only empty-text PDFs"
        )
    if "occurrence_ledger" not in ran:
        actions.append(
            "Build an isolated occurrence packet from the checkable export "
            "and pass --occurrence-packet"
        )
    if "index_reconciliation" not in ran:
        actions.append(
            "Build a master/PDF/handwritten index packet with expected "
            "counts and pass --index-packet"
        )
    if "repair_loop" not in ran and "isolated_delta" not in ran:
        actions.append(
            "Pass --repair-dir with --workbook and --index-packet to run "
            "up to 10 isolated detect-and-repair passes, or pass "
            "--delta-packet and --delta-output for a single apply"
        )
    if "workbook_qa" not in ran:
        actions.append(
            "Pass --workbook pointing at the isolated candidate index "
            f"(default profile {DEFAULT_WORKBOOK_PROFILE.name} checks "
            "document type, parties, doc no, recorded date, and legal)"
        )
    if "public_cadastral" not in ran:
        actions.append(
            "Bind public township plats with --public-plat campbell,45n,76w "
            "and --public-plat johnson,47n,77w"
        )
    if "print_layout_repair" not in ran:
        actions.append(
            "Pass --print-layout-output to write Letter/landscape/print-title "
            "settings onto an isolated copy"
        )
    for section in sections:
        hops = named_isolated_hops(
            isolated_workbook_filename(workbook, section), section
        )
        if (
            not _gate_matches_workbook(gates, "native_print", workbook)
            and hops["native_print"] not in actions
        ):
            actions.append(hops["native_print"])
        if (
            not _gate_matches_workbook(
                gates, "drive_readback", workbook, require_isolated=True
            )
            and hops["drive_readback"] not in actions
        ):
            actions.append(hops["drive_readback"])
        if (
            not _gate_matches_workbook(gates, "human_release", workbook)
            and hops["human_release"] not in actions
        ):
            actions.append(hops["human_release"])
    for gate in gates:
        if gate.ran and gate.name == "pdf_census":
            empty = gate.detail.get("empty_text_files")
            if empty:
                actions.append(
                    f"Hold {empty} image-only PDF(s) with empty extracted text; "
                    "do not invent legal text from page count"
                )
        if gate.ran and gate.technical_pass is False:
            actions.append(f"Resolve blocking {gate.name}: {gate.error or gate.detail}")
    actions.append(
        "Drive Isolated/ remains required before any owner-release claim"
    )
    actions.append("Do not start a second controller; one writer per target")
    return actions


def run_finish(
    *,
    sections: Sequence[int],
    roots: Sequence[str] = (),
    tract_export: Optional[Path] = None,
    oracle: Optional[Path] = None,
    occurrence_packet: Optional[Path] = None,
    index_packet: Optional[Path] = None,
    public_plats: Sequence[str] = (),
    workbook: Optional[Path] = None,
    workbook_profile: Optional[Path] = None,
    delta_packet: Optional[Path] = None,
    delta_output: Optional[Path] = None,
    repair_dir: Optional[Path] = None,
    max_loops: int = 10,
    master_workbook: Optional[Path] = None,
    pdf_workbook: Optional[Path] = None,
    handwritten_workbook: Optional[Path] = None,
    print_layout_output: Optional[Path] = None,
    native_print_receipt: Optional[Path] = None,
    page_render_packet: Optional[Path] = None,
    page_render_bind_dir: Optional[Path] = None,
    pdf_census_packet: Optional[Path] = None,
    pdf_bind_dir: Optional[Path] = None,
    connect_status: bool = False,
    drive_readback: Optional[Path] = None,
    human_release_token: Optional[Path] = None,
    authority_manifest: Optional[Path] = None,
    project_manifest: Optional[Path] = None,
    snapshot_directory: Optional[Path] = None,
    acquisition_receipt: Optional[Path] = None,
) -> FinishReceipt:
    if any(section not in PRIORITY_SECTIONS for section in sections):
        raise PackageFinishError(f"Sections must come from {PRIORITY_SECTIONS}")
    gates: List[GateResult] = []
    if connect_status:
        try:
            connection = probe_connections(roots)
            gates.append(
                GateResult(
                    name="connect_status",
                    ran=True,
                    technical_pass=connection.technical_pass,
                    detail={
                        "connected_root_count": connection.connected_root_count,
                        "tools": connection.tools,
                        "desktop_sessions": connection.desktop_sessions,
                        "next_actions": connection.next_actions,
                    },
                )
            )
        except (OSError, ConnectStatusError, SourceAcquisitionError) as exc:
            gates.append(
                GateResult(
                    name="connect_status",
                    ran=True,
                    technical_pass=False,
                    error=str(exc),
                )
            )
    if roots:
        gates.append(
            _acquisition_gate(
                roots,
                sections,
                authority_manifest=authority_manifest,
                project_manifest=project_manifest,
                snapshot_directory=snapshot_directory,
                acquisition_receipt=acquisition_receipt,
            )
        )
    if page_render_packet is not None:
        if tract_export is not None:
            raise PackageFinishError(
                "Use --page-render-packet or --tract-export, not both"
            )
        try:
            compiled = compile_page_renders(
                _load_json(page_render_packet),
                bind_dir=page_render_bind_dir,
            )
            gates.append(
                GateResult(
                    name="page_render_export",
                    ran=True,
                    technical_pass=compiled.technical_pass,
                    detail={
                        "page_count": compiled.page_count,
                        "crop_count": compiled.crop_count,
                        "reextraction_technical_pass": compiled.reextraction_technical_pass,
                        "next_action": compiled.next_action,
                    },
                )
            )
            packet_id, rows = parse_ledger_export(compiled.tract_export)
            oracle_rows = parse_oracle(_load_json(oracle)) if oracle else None
            recon = assess_ledger(packet_id, rows, oracle=oracle_rows)
            gates.append(
                GateResult(
                    name="reextraction",
                    ran=True,
                    technical_pass=recon.technical_pass,
                    detail={
                        "row_count": recon.row_count,
                        "bare_docno_count": recon.bare_docno_count,
                        "next_action": recon.next_action,
                    },
                )
            )
        except (
            OSError,
            PageRenderExportError,
            ReextractionError,
            PackageFinishError,
        ) as exc:
            gates.append(
                GateResult(
                    name="page_render_export",
                    ran=True,
                    technical_pass=False,
                    error=str(exc),
                )
            )
    elif tract_export is not None:
        gates.append(_reextraction_gate(tract_export, oracle))
    if pdf_census_packet is not None:
        if pdf_bind_dir is None:
            raise PackageFinishError("PDF census requires --pdf-bind-dir")
        try:
            census = census_packet(
                _load_json(pdf_census_packet),
                bind_dir=pdf_bind_dir,
            )
            gates.append(
                GateResult(
                    name="pdf_census",
                    ran=True,
                    technical_pass=census.technical_pass,
                    detail={
                        "file_count": len(census.files),
                        "empty_text_files": census.empty_text_files,
                    },
                )
            )
        except (OSError, PdfCensusError, PackageFinishError) as exc:
            gates.append(
                GateResult(
                    name="pdf_census",
                    ran=True,
                    technical_pass=False,
                    error=str(exc),
                )
            )
    if occurrence_packet is not None:
        gates.append(_occurrence_gate(occurrence_packet))
    elif page_render_packet is not None and any(
        gate.name == "page_render_export" and gate.technical_pass
        for gate in gates
    ):
        try:
            built = build_occurrence_packet(
                _load_json(page_render_packet),
                bind_dir=page_render_bind_dir,
            )
            occ_receipt = compare_packet(parse_occurrence_packet(built))
            gates.append(
                GateResult(
                    name="occurrence_ledger",
                    ran=True,
                    technical_pass=occ_receipt.technical_pass,
                    detail={
                        "occurrence_count": occ_receipt.occurrence_count,
                        "unique_keys_from_occurrences": occ_receipt.unique_keys_from_occurrences,
                        "candidate_row_count": occ_receipt.candidate_row_count,
                        "issue_count": len(occ_receipt.issues),
                        "built_from": "page_render_packet",
                    },
                )
            )
        except (
            OSError,
            OccurrenceBuildError,
            OccurrenceLedgerError,
            PackageFinishError,
        ) as exc:
            gates.append(
                GateResult(
                    name="occurrence_ledger",
                    ran=True,
                    technical_pass=False,
                    error=str(exc),
                )
            )
    source_workbooks = any(
        (master_workbook, pdf_workbook, handwritten_workbook)
    )
    if index_packet is not None and source_workbooks and repair_dir is None:
        raise PackageFinishError(
            "Use --index-packet or the three source workbooks, not both"
        )
    if index_packet is not None and repair_dir is None:
        try:
            packet = _load_json(index_packet)
            candidate_from = "index_packet"
            if workbook is not None:
                packet = refresh_candidate(
                    packet,
                    export_faces(workbook, profile_path=workbook_profile),
                )
                candidate_from = "workbook"
            recon = reconcile_indexes(packet)
            gates.append(
                GateResult(
                    name="index_reconciliation",
                    ran=True,
                    technical_pass=recon.technical_pass,
                    detail={
                        "source_counts": recon.source_counts,
                        "proposed_delta_count": len(recon.proposed_deltas),
                        "conflict_count": recon.conflict_count,
                        "blank_required_count": recon.blank_required_count,
                        "low_confidence_blank_count": recon.low_confidence_blank_count,
                        "issue_count": len(recon.issues),
                        "candidate_from": candidate_from,
                    },
                )
            )
        except (
            OSError,
            IndexExportError,
            IndexReconciliationError,
            PackageFinishError,
        ) as exc:
            gates.append(
                GateResult(
                    name="index_reconciliation",
                    ran=True,
                    technical_pass=False,
                    error=str(exc),
                )
            )
    elif source_workbooks and repair_dir is None:
        try:
            built = export_index_packet(
                "finish-index",
                master=master_workbook,
                pdf_index=pdf_workbook,
                handwritten=handwritten_workbook,
                candidate=workbook,
                profile_path=workbook_profile,
            )
            recon = reconcile_indexes(built)
            gates.append(
                GateResult(
                    name="index_reconciliation",
                    ran=True,
                    technical_pass=recon.technical_pass,
                    detail={
                        "source_counts": recon.source_counts,
                        "proposed_delta_count": len(recon.proposed_deltas),
                        "conflict_count": recon.conflict_count,
                        "blank_required_count": recon.blank_required_count,
                        "low_confidence_blank_count": recon.low_confidence_blank_count,
                        "issue_count": len(recon.issues),
                        "built_from": "source_workbooks",
                    },
                )
            )
        except (
            OSError,
            IndexExportError,
            IndexReconciliationError,
            PackageFinishError,
        ) as exc:
            gates.append(
                GateResult(
                    name="index_reconciliation",
                    ran=True,
                    technical_pass=False,
                    error=str(exc),
                )
            )
    qa_workbook = workbook
    if repair_dir is not None:
        if workbook is None:
            raise PackageFinishError("Repair loop requires --workbook")
        if delta_packet is not None:
            raise PackageFinishError(
                "Use --repair-dir or --delta-packet, not both"
            )
        try:
            packet = _load_json(index_packet) if index_packet is not None else None
            repair = run_repair_loop(
                workbook=workbook,
                output_dir=repair_dir,
                packet_id=str(
                    (packet or {}).get("packet_id") or "repair-loop"
                ),
                index_packet=packet,
                master_workbook=master_workbook,
                pdf_workbook=pdf_workbook,
                handwritten_workbook=handwritten_workbook,
                profile_path=workbook_profile,
                max_loops=max_loops,
            )
            gates.append(
                GateResult(
                    name="repair_loop",
                    ran=True,
                    technical_pass=repair.technical_pass,
                    detail={
                        "passes": len(repair.passes),
                        "final_workbook": repair.final_workbook,
                        "remaining_blanks": repair.remaining_blanks,
                        "remaining_conflicts": repair.remaining_conflicts,
                        "packages_complete": repair.packages_complete,
                    },
                )
            )
            qa_workbook = Path(repair.final_workbook)
        except (
            OSError,
            RepairLoopError,
            PackageFinishError,
        ) as exc:
            gates.append(
                GateResult(
                    name="repair_loop",
                    ran=True,
                    technical_pass=False,
                    error=str(exc),
                )
            )
            qa_workbook = None
    if delta_packet is not None:
        if workbook is None or delta_output is None:
            raise PackageFinishError(
                "Source-proved deltas require --workbook and --delta-output"
            )
        try:
            delta_receipt = apply_deltas(
                workbook,
                delta_output,
                _load_json(delta_packet),
                profile_path=workbook_profile,
            )
            gates.append(
                GateResult(
                    name="isolated_delta",
                    ran=True,
                    technical_pass=delta_receipt.technical_pass,
                    detail={
                        "applied": delta_receipt.applied,
                        "rejected": delta_receipt.rejected,
                        "isolated_workbook": delta_receipt.isolated_workbook,
                    },
                )
            )
            qa_workbook = delta_output
        except (OSError, IsolatedDeltaError) as exc:
            gates.append(
                GateResult(
                    name="isolated_delta",
                    ran=True,
                    technical_pass=False,
                    error=str(exc),
                )
            )
            qa_workbook = None
    if print_layout_output is not None:
        if qa_workbook is None:
            raise PackageFinishError(
                "Print-layout repair requires a workbook or isolated copy"
            )
        try:
            layout = repair_print_layout(
                qa_workbook,
                print_layout_output,
                profile_path=workbook_profile,
            )
            gates.append(
                GateResult(
                    name="print_layout_repair",
                    ran=True,
                    technical_pass=layout.technical_pass,
                    detail={
                        "applied": layout.applied,
                        "isolated_workbook": layout.isolated_workbook,
                    },
                )
            )
            qa_workbook = print_layout_output
        except (OSError, PrintLayoutRepairError) as exc:
            gates.append(
                GateResult(
                    name="print_layout_repair",
                    ran=True,
                    technical_pass=False,
                    error=str(exc),
                )
            )
            qa_workbook = None
    if qa_workbook is not None:
        gates.append(
            _workbook_gate(qa_workbook, workbook_profile, DEFAULT_WORKBOOK_CHECKS)
        )
        ran_names = {gate.name for gate in gates if gate.ran}
        packet_id = f"SECTION{sections[0]}-WORKBOOK"
        if "reextraction" not in ran_names:
            try:
                export = workbook_to_tract_export(
                    qa_workbook,
                    packet_id=packet_id,
                    profile_path=workbook_profile,
                )
                export_id, rows = parse_ledger_export(export)
                recon = assess_ledger(export_id, rows)
                gates.append(
                    GateResult(
                        name="reextraction",
                        ran=True,
                        technical_pass=recon.technical_pass,
                        detail={
                            "row_count": recon.row_count,
                            "bare_docno_count": recon.bare_docno_count,
                            "next_action": recon.next_action,
                            "built_from": "workbook",
                        },
                    )
                )
            except (OSError, WorkbookLedgerError, ReextractionError) as exc:
                gates.append(
                    GateResult(
                        name="reextraction",
                        ran=True,
                        technical_pass=False,
                        error=str(exc),
                    )
                )
        ran_names = {gate.name for gate in gates if gate.ran}
        if "occurrence_ledger" not in ran_names:
            try:
                built = workbook_to_occurrence_packet(
                    qa_workbook,
                    packet_id=packet_id,
                    profile_path=workbook_profile,
                )
                occ_receipt = compare_packet(parse_occurrence_packet(built))
                gates.append(
                    GateResult(
                        name="occurrence_ledger",
                        ran=True,
                        technical_pass=occ_receipt.technical_pass,
                        detail={
                            "occurrence_count": occ_receipt.occurrence_count,
                            "unique_keys_from_occurrences": (
                                occ_receipt.unique_keys_from_occurrences
                            ),
                            "built_from": "workbook",
                        },
                    )
                )
            except (
                OSError,
                WorkbookLedgerError,
                OccurrenceLedgerError,
            ) as exc:
                gates.append(
                    GateResult(
                        name="occurrence_ledger",
                        ran=True,
                        technical_pass=False,
                        error=str(exc),
                    )
                )
    if native_print_receipt is not None:
        if qa_workbook is None:
            gates.append(
                GateResult(
                    name="native_print",
                    ran=True,
                    technical_pass=False,
                    error="Native print receipt requires a workbook to bind",
                )
            )
        else:
            try:
                native = assess_native_print(
                    _load_json(native_print_receipt),
                    workbook=qa_workbook,
                )
                gates.append(
                    GateResult(
                        name="native_print",
                        ran=True,
                        technical_pass=native.technical_pass,
                        detail={
                            "page_count": native.page_count,
                            "expected_page_count": native.expected_page_count,
                            "issue_count": len(native.issues),
                            "workbook_sha256": native.workbook_sha256,
                        },
                    )
                )
            except (OSError, NativePrintError, PackageFinishError) as exc:
                gates.append(
                    GateResult(
                        name="native_print",
                        ran=True,
                        technical_pass=False,
                        error=str(exc),
                    )
                )
    if drive_readback is not None:
        if qa_workbook is None:
            gates.append(
                GateResult(
                    name="drive_readback",
                    ran=True,
                    technical_pass=False,
                    error="Drive readback requires a workbook to bind",
                )
            )
        else:
            try:
                readback = assess_drive_readback(qa_workbook, drive_readback)
                gates.append(
                    GateResult(
                        name="drive_readback",
                        ran=True,
                        technical_pass=readback.technical_pass,
                        detail={
                            "workbook_sha256": readback.workbook_sha256,
                            "readback_sha256": readback.readback_sha256,
                            "issue_count": len(readback.issues),
                            "isolated_copy": any(
                                is_drive_isolated_copy(drive_readback, section)
                                for section in sections
                            ),
                        },
                    )
                )
            except (OSError, DriveReadbackError) as exc:
                gates.append(
                    GateResult(
                        name="drive_readback",
                        ran=True,
                        technical_pass=False,
                        error=str(exc),
                    )
                )
    if public_plats:
        gates.append(_cadastral_gate(public_plats))
    if human_release_token is not None:
        if qa_workbook is None:
            gates.append(
                GateResult(
                    name="human_release",
                    ran=True,
                    technical_pass=False,
                    error="Human release token requires a workbook to bind",
                )
            )
        else:
            try:
                release = assess_human_release(
                    _load_json(human_release_token),
                    workbook=qa_workbook,
                    requested_sections=sections,
                )
                gates.append(
                    GateResult(
                        name="human_release",
                        ran=True,
                        technical_pass=release.technical_pass,
                        detail={
                            "operator": release.operator,
                            "issue_count": len(release.issues),
                            "sections": release.sections,
                            "workbook_sha256": release.workbook_sha256,
                        },
                    )
                )
            except (OSError, HumanReleaseError, PackageFinishError) as exc:
                gates.append(
                    GateResult(
                        name="human_release",
                        ran=True,
                        technical_pass=False,
                        error=str(exc),
                    )
                )
    ran = [gate for gate in gates if gate.ran]
    technical_pass = bool(ran) and all(gate.technical_pass for gate in ran)
    packages_complete, completion_gaps = evaluate_package_completion(
        gates,
        requested_sections=sections,
    )
    next_actions = _next_actions(gates, sections, workbook=qa_workbook)
    if packages_complete:
        next_actions.append(
            "Owner review only; this is not an external client delivery"
        )
    else:
        next_actions.extend(completion_gaps[:12])
    return FinishReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        requested_sections=list(sections),
        gates=gates,
        next_actions=next_actions,
        packages_complete=packages_complete,
        technical_pass=technical_pass,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Chain Horizon finish gates for sections 15/13/11 without "
            "promoting a package."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--section",
        dest="sections",
        type=int,
        action="append",
        choices=PRIORITY_SECTIONS,
    )
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument("--tract-export", type=Path)
    parser.add_argument("--oracle", type=Path)
    parser.add_argument("--occurrence-packet", type=Path)
    parser.add_argument("--index-packet", type=Path)
    parser.add_argument("--public-plat", action="append", default=[])
    parser.add_argument("--workbook", type=Path)
    parser.add_argument("--workbook-profile", type=Path)
    parser.add_argument("--delta-packet", type=Path)
    parser.add_argument("--delta-output", type=Path)
    parser.add_argument("--repair-dir", type=Path)
    parser.add_argument("--max-loops", type=int, default=10)
    parser.add_argument("--master-workbook", type=Path)
    parser.add_argument("--pdf-workbook", type=Path)
    parser.add_argument("--handwritten-workbook", type=Path)
    parser.add_argument("--print-layout-output", type=Path)
    parser.add_argument("--native-print-receipt", type=Path)
    parser.add_argument("--page-render-packet", type=Path)
    parser.add_argument("--page-render-bind-dir", type=Path)
    parser.add_argument("--pdf-census-packet", type=Path)
    parser.add_argument("--pdf-bind-dir", type=Path)
    parser.add_argument("--connect-status", action="store_true")
    parser.add_argument("--drive-readback", type=Path)
    parser.add_argument("--human-release-token", type=Path)
    parser.add_argument("--authority-manifest", type=Path)
    parser.add_argument("--project-manifest", type=Path)
    parser.add_argument("--snapshot-directory", type=Path)
    parser.add_argument("--acquisition-receipt", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        receipt = run_finish(
            sections=args.sections or list(PRIORITY_SECTIONS),
            roots=args.root,
            tract_export=args.tract_export,
            oracle=args.oracle,
            occurrence_packet=args.occurrence_packet,
            index_packet=args.index_packet,
            public_plats=args.public_plat,
            workbook=args.workbook,
            workbook_profile=args.workbook_profile,
            delta_packet=args.delta_packet,
            delta_output=args.delta_output,
            repair_dir=args.repair_dir,
            max_loops=args.max_loops,
            master_workbook=args.master_workbook,
            pdf_workbook=args.pdf_workbook,
            handwritten_workbook=args.handwritten_workbook,
            print_layout_output=args.print_layout_output,
            native_print_receipt=args.native_print_receipt,
            page_render_packet=args.page_render_packet,
            page_render_bind_dir=args.page_render_bind_dir,
            pdf_census_packet=args.pdf_census_packet,
            pdf_bind_dir=args.pdf_bind_dir,
            connect_status=args.connect_status,
            drive_readback=args.drive_readback,
            human_release_token=args.human_release_token,
            authority_manifest=args.authority_manifest,
            project_manifest=args.project_manifest,
            snapshot_directory=args.snapshot_directory,
            acquisition_receipt=args.acquisition_receipt,
        )
        args.output.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except (OSError, PackageFinishError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "technical_pass": receipt.technical_pass,
                "packages_complete": receipt.packages_complete,
                "gates_run": [gate.name for gate in receipt.gates if gate.ran],
                "next_actions": receipt.next_actions,
            },
            indent=2,
        )
    )
    if not receipt.gates:
        return 2
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
