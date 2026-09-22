"""Bounded detect-and-repair loop for isolated abstract copies.

Each pass exports the current candidate, reconciles it to master/PDF/
handwritten faces, and applies only medium/high proposals to a new copy.
The original workbook is never overwritten. The loop stops at the first
conflict, empty proposal set, or max pass count. This is not package
release.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .index_export import (
    IndexExportError,
    bind_delta_packet,
    build_index_packet,
    export_faces,
    refresh_candidate,
)
from .index_reconciliation import (
    IndexReconciliationError,
    IndexReconciliationReceipt,
    reconcile_indexes,
)
from .isolated_delta import IsolatedDeltaError, apply_deltas, sha256_file
from .project_manifest import ControlFileError
from .workbook_qa import inspect_workbook, load_workbook_profile

DEFAULT_WORKBOOK_PROFILE = (
    Path(__file__).resolve().parent / "profiles" / "penterra_index_v1.json"
)
DEFAULT_WORKBOOK_CHECKS = (
    "abstract_required_fields",
    "abstract_print_layout",
)

RECEIPT_SCHEMA_ID = "dbx.repair_loop_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
DEFAULT_MAX_LOOPS = 10
MAX_LOOPS_CAP = 20


class RepairLoopError(ValueError):
    """Raised when the repair loop cannot run safely."""


@dataclass
class LoopPass:
    pass_number: int
    source_workbook: str
    isolated_workbook: str
    proposed: int
    applied: int
    recon_pass: bool
    qa_pass: Optional[bool]
    stop_reason: str = ""
    issues: List[str] = field(default_factory=list)


@dataclass
class RepairLoopReceipt:
    generated_utc: str
    packet_id: str
    original_workbook: str
    final_workbook: str
    final_workbook_sha256: str
    passes: List[LoopPass]
    remaining_proposals: int
    remaining_conflicts: int
    remaining_blanks: int
    technical_pass: bool
    packages_complete: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            "The original workbook was not modified",
            "packages_complete stays false",
            "technical_pass is not package release",
        ]
    )

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RepairLoopError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RepairLoopError(f"{path} must contain a JSON object")
    return payload


def _qa_pass(workbook: Path, profile_path: Optional[Path]) -> tuple[bool, List[str]]:
    report = inspect_workbook(
        workbook,
        list(DEFAULT_WORKBOOK_CHECKS),
        profile=load_workbook_profile(profile_path or DEFAULT_WORKBOOK_PROFILE),
    )
    issues = [
        f"{finding.code}:{finding.cell or finding.sheet}:{finding.message}"
        for finding in report.findings[:20]
    ]
    return report.score.technical_pass, issues


def run_repair_loop(
    *,
    workbook: Path,
    output_dir: Path,
    packet_id: str,
    index_packet: Optional[Dict[str, object]] = None,
    master_workbook: Optional[Path] = None,
    pdf_workbook: Optional[Path] = None,
    handwritten_workbook: Optional[Path] = None,
    profile_path: Optional[Path] = None,
    max_loops: int = DEFAULT_MAX_LOOPS,
    orphan_allowlist: Optional[Sequence[Dict[str, object]]] = None,
) -> RepairLoopReceipt:
    workbook = workbook.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if max_loops < 1 or max_loops > MAX_LOOPS_CAP:
        raise RepairLoopError(f"max_loops must be between 1 and {MAX_LOOPS_CAP}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RepairLoopError("Repair output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    if index_packet is None:
        if not (master_workbook and pdf_workbook and handwritten_workbook):
            raise RepairLoopError(
                "Repair loop needs --index-packet or the three source workbooks"
            )
        base_packet = build_index_packet(
            packet_id,
            master=export_faces(master_workbook, profile_path=profile_path),
            pdf_index=export_faces(pdf_workbook, profile_path=profile_path),
            handwritten_index=export_faces(
                handwritten_workbook, profile_path=profile_path
            ),
            candidate_rows=[],
            orphan_allowlist=orphan_allowlist,
        )
    else:
        base_packet = dict(index_packet)
        if orphan_allowlist is not None:
            base_packet["orphan_allowlist"] = list(orphan_allowlist)
    current = workbook
    passes: List[LoopPass] = []
    last_recon: Optional[IndexReconciliationReceipt] = None
    for pass_number in range(1, max_loops + 1):
        candidate = export_faces(current, profile_path=profile_path)
        packet = refresh_candidate(base_packet, candidate)
        recon = reconcile_indexes(packet)
        last_recon = recon
        isolated = output_dir / f"isolated_pass_{pass_number:02d}.xlsx"
        if not recon.technical_pass:
            passes.append(
                LoopPass(
                    pass_number=pass_number,
                    source_workbook=str(current),
                    isolated_workbook="",
                    proposed=len(recon.proposed_deltas),
                    applied=0,
                    recon_pass=False,
                    qa_pass=None,
                    stop_reason="reconciliation_blocked",
                    issues=recon.issues[:20],
                )
            )
            break
        if not recon.proposed_deltas:
            qa_ok, qa_issues = _qa_pass(current, profile_path)
            passes.append(
                LoopPass(
                    pass_number=pass_number,
                    source_workbook=str(current),
                    isolated_workbook="",
                    proposed=0,
                    applied=0,
                    recon_pass=True,
                    qa_pass=qa_ok,
                    stop_reason="no_eligible_proposals",
                    issues=qa_issues,
                )
            )
            break
        delta_packet = bind_delta_packet(
            recon.proposed_deltas,
            source_workbook_sha256=sha256_file(current),
            packet_id=f"{packet_id}-pass-{pass_number:02d}",
        )
        delta_receipt = apply_deltas(
            current,
            isolated,
            delta_packet,
            profile_path=profile_path,
        )
        qa_ok, qa_issues = _qa_pass(isolated, profile_path)
        passes.append(
            LoopPass(
                pass_number=pass_number,
                source_workbook=str(current),
                isolated_workbook=str(isolated),
                proposed=len(recon.proposed_deltas),
                applied=delta_receipt.applied,
                recon_pass=True,
                qa_pass=qa_ok,
                issues=qa_issues,
            )
        )
        current = isolated
        if delta_receipt.applied == 0:
            passes[-1].stop_reason = "no_cells_changed"
            break
    else:
        passes[-1].stop_reason = "max_loops"

    remaining_proposals = len(last_recon.proposed_deltas) if last_recon else 0
    remaining_conflicts = last_recon.conflict_count if last_recon else 0
    remaining_blanks = last_recon.blank_required_count if last_recon else 0
    technical_pass = bool(passes) and all(
        item.recon_pass and item.applied >= 0 for item in passes
    )
    if any(item.stop_reason == "reconciliation_blocked" for item in passes):
        technical_pass = False
    try:
        final_digest = sha256_file(current)
    except OSError:
        final_digest = ""
    return RepairLoopReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        packet_id=packet_id,
        original_workbook=str(workbook),
        final_workbook=str(current),
        final_workbook_sha256=final_digest,
        passes=passes,
        remaining_proposals=remaining_proposals,
        remaining_conflicts=remaining_conflicts,
        remaining_blanks=remaining_blanks,
        technical_pass=technical_pass,
        packages_complete=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run up to 10 isolated detect-and-repair passes. "
            "Does not promote a package."
        )
    )
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--packet-id", required=True)
    parser.add_argument("--index-packet", type=Path)
    parser.add_argument("--master-workbook", type=Path)
    parser.add_argument("--pdf-workbook", type=Path)
    parser.add_argument("--handwritten-workbook", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--max-loops", type=int, default=DEFAULT_MAX_LOOPS)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        receipt = run_repair_loop(
            workbook=args.workbook,
            output_dir=args.output_dir,
            packet_id=args.packet_id,
            index_packet=_load_json(args.index_packet) if args.index_packet else None,
            master_workbook=args.master_workbook,
            pdf_workbook=args.pdf_workbook,
            handwritten_workbook=args.handwritten_workbook,
            profile_path=args.profile,
            max_loops=args.max_loops,
        )
        args.receipt.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except (
        OSError,
        ControlFileError,
        RepairLoopError,
        IndexExportError,
        IndexReconciliationError,
        IsolatedDeltaError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "receipt": str(args.receipt),
                "final_workbook": receipt.final_workbook,
                "passes": len(receipt.passes),
                "technical_pass": receipt.technical_pass,
                "packages_complete": receipt.packages_complete,
            },
            indent=2,
        )
    )
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
