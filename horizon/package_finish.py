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
from dataclasses import asdict, dataclass, field
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
from .index_reconciliation import (
    IndexReconciliationError,
    reconcile_indexes,
)
from .isolated_delta import IsolatedDeltaError, apply_deltas
from .project_manifest import ControlFileError
from .source_acquisition import (
    PRIORITY_SECTIONS,
    SourceAcquisitionError,
    build_receipt as build_acquisition_receipt,
    parse_root,
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
        "source-backed rows, native Excel, and human release all exist",
        "technical_pass is only the gates that actually ran",
    ])

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


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
) -> GateResult:
    try:
        receipt = build_acquisition_receipt(
            [parse_root(root) for root in roots],
            requested_sections=list(sections),
        )
    except (OSError, SourceAcquisitionError) as exc:
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


def _next_actions(gates: Sequence[GateResult], sections: Sequence[int]) -> List[str]:
    ran = {gate.name for gate in gates if gate.ran}
    actions = []
    if "source_acquisition" not in ran:
        actions.append(
            "Mount PC/Drive/chat roots and rerun with --root "
            f"for sections {list(sections)}"
        )
    if "reextraction" not in ran:
        actions.append(
            "Export a tract-ledger JSON with book/page, recorded date, and "
            "parties from page renders, then pass --tract-export"
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
    if "isolated_delta" not in ran:
        actions.append(
            "Pass --delta-packet and --delta-output to apply source-proved "
            "field fills to an isolated workbook copy"
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
    for gate in gates:
        if gate.ran and gate.technical_pass is False:
            actions.append(f"Resolve blocking {gate.name}: {gate.error or gate.detail}")
    actions.append(
        "Native Excel Print Preview and Drive readback remain required "
        "before any owner-release claim"
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
) -> FinishReceipt:
    if any(section not in PRIORITY_SECTIONS for section in sections):
        raise PackageFinishError(f"Sections must come from {PRIORITY_SECTIONS}")
    gates: List[GateResult] = []
    if roots:
        gates.append(_acquisition_gate(roots, sections))
    if tract_export is not None:
        gates.append(_reextraction_gate(tract_export, oracle))
    if occurrence_packet is not None:
        gates.append(_occurrence_gate(occurrence_packet))
    if index_packet is not None:
        try:
            recon = reconcile_indexes(_load_json(index_packet))
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
                    },
                )
            )
        except (OSError, IndexReconciliationError, PackageFinishError) as exc:
            gates.append(
                GateResult(
                    name="index_reconciliation",
                    ran=True,
                    technical_pass=False,
                    error=str(exc),
                )
            )
    qa_workbook = workbook
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
    if qa_workbook is not None:
        gates.append(
            _workbook_gate(qa_workbook, workbook_profile, DEFAULT_WORKBOOK_CHECKS)
        )
    if public_plats:
        gates.append(_cadastral_gate(public_plats))
    ran = [gate for gate in gates if gate.ran]
    technical_pass = bool(ran) and all(gate.technical_pass for gate in ran)
    return FinishReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        requested_sections=list(sections),
        gates=gates,
        next_actions=_next_actions(gates, sections),
        packages_complete=False,
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
