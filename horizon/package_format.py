"""Apply the Section 13 / Section 15 Letter package contract.

Match Section 15 by role, never by facts. The work date for this lane
is 2026-09-22. Isolated copies receive US Letter, landscape, and print
titles on rows 1-8. Exact-N membership is supplied by the operator.
No legal, party, or date cell is invented.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .examiner import write_new_json
from .image_account import WORK_DATE, WORK_DATE_TOKEN
from .isolated_delta import sha256_file
from .print_layout_repair import PrintLayoutRepairError, repair_print_layout
from .workbook_qa import inspect_workbook, load_workbook_profile

RECEIPT_SCHEMA_ID = "dbx.package_format_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
MEMBERSHIP_SCHEMA_ID = "dbx.package_membership_receipt"
MEMBERSHIP_SCHEMA_VERSION = "1.0"
DEFAULT_PROFILE = (
    Path(__file__).resolve().parent / "profiles" / "penterra_index_v1.json"
)
DEFAULT_CHECKS = ("abstract_required_fields", "abstract_print_layout")
ROLE_NOT_FACTS = "Match Section 15 by role, not facts"
FROZEN_PACKAGE_IDS = frozenset({"P15", "P10", "P2"})
FROZEN_ROLES = frozenset({"format_donor", "frozen_donor", "closed"})


class PackageFormatError(ValueError):
    """Raised when a 13/15-format package cannot be assembled safely."""


@dataclass
class PackageContract:
    package_id: str
    section: int
    county: str
    township: str
    exact_n: Optional[int]
    role: str


PACKAGE_CONTRACTS: Sequence[PackageContract] = (
    PackageContract("P15", 15, "Campbell", "45N-76W", 6, "format_donor"),
    PackageContract("P13", 13, "Campbell", "45N-76W", 5, "content_winner"),
    PackageContract("P11", 11, "Campbell", "45N-76W", 7, "qa_hold"),
    PackageContract("P14", 14, "Campbell", "45N-76W", 8, "owner_review"),
    PackageContract("P12", 12, "Campbell", "45N-76W", None, "unknown"),
    PackageContract("P10", 10, "Campbell", "45N-76W", None, "closed"),
    PackageContract("P3", 3, "Campbell", "45N-76W", None, "source_hold"),
    PackageContract("P2", 2, "Campbell", "45N-76W", None, "frozen_donor"),
    PackageContract("P1", 1, "Campbell", "45N-76W", None, "unknown"),
    PackageContract("J13", 13, "Johnson", "47N-77W", 9, "no_faces"),
    PackageContract("J24", 24, "Johnson", "47N-77W", None, "unknown"),
    PackageContract("H7", 7, "Beckham", "11N-25W", None, "horizon_partial"),
)


def contract_for(package_id: str) -> PackageContract:
    token = package_id.strip().upper()
    for item in PACKAGE_CONTRACTS:
        if item.package_id == token:
            return item
    raise PackageFormatError(f"unknown package id {package_id!r}")


def dated_zip_name(contract: PackageContract) -> str:
    if contract.exact_n is None:
        raise PackageFormatError(
            f"{contract.package_id} has no exact-N contract; do not invent membership"
        )
    return (
        f"{contract.package_id}_{contract.township}-{contract.section}"
        f"__SUPERSEDING_TURNIN_DATED_{WORK_DATE_TOKEN}_EXACT{contract.exact_n}.zip"
    )


@dataclass
class FormatReceipt:
    generated_utc: str
    work_date: str
    source_workbook: str
    isolated_workbook: str
    source_workbook_sha256: str
    isolated_workbook_sha256: str
    applied: List[str]
    qa_pass: bool
    technical_pass: bool
    packages_complete: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            ROLE_NOT_FACTS,
            "Do not copy donor tract facts, counts, serials, or source-through dates",
            "US Letter landscape with print titles on rows 1-8",
            "packages_complete stays false",
        ]
    )

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class MembershipReceipt:
    generated_utc: str
    work_date: str
    package_id: str
    zip_name: str
    exact_n: int
    members: List[Dict[str, object]]
    zip_path: str
    zip_sha256: str
    technical_pass: bool
    packages_complete: bool
    schema_id: str = MEMBERSHIP_SCHEMA_ID
    schema_version: str = MEMBERSHIP_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            ROLE_NOT_FACTS,
            "Exact-N is ZIP membership, not instrument count",
            "This is not Drive Isolated/ and not owner release",
        ]
    )

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def apply_letter_format(
    source_workbook: Path,
    output_workbook: Path,
    *,
    profile_path: Optional[Path] = None,
) -> FormatReceipt:
    profile = profile_path or DEFAULT_PROFILE
    try:
        repair = repair_print_layout(
            source_workbook,
            output_workbook,
            profile_path=profile,
        )
    except PrintLayoutRepairError as exc:
        raise PackageFormatError(str(exc)) from exc
    report = inspect_workbook(
        output_workbook,
        list(DEFAULT_CHECKS),
        profile=load_workbook_profile(profile),
    )
    return FormatReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        work_date=WORK_DATE.isoformat(),
        source_workbook=repair.source_workbook,
        isolated_workbook=repair.isolated_workbook,
        source_workbook_sha256=repair.source_workbook_sha256,
        isolated_workbook_sha256=sha256_file(output_workbook),
        applied=repair.applied,
        qa_pass=report.score.technical_pass,
        technical_pass=repair.technical_pass and report.score.technical_pass,
        packages_complete=False,
    )


def assemble_exact_package(
    *,
    package_id: str,
    members: Sequence[Path],
    output_zip: Path,
) -> MembershipReceipt:
    contract = contract_for(package_id)
    if contract.package_id in FROZEN_PACKAGE_IDS or contract.role in FROZEN_ROLES:
        raise PackageFormatError(
            f"{contract.package_id} is {contract.role}; do not rebuild it"
        )
    if contract.exact_n is None:
        raise PackageFormatError(
            f"{contract.package_id} has no exact-N contract; do not invent members"
        )
    if len(members) != contract.exact_n:
        raise PackageFormatError(
            f"{contract.package_id} requires exact-{contract.exact_n} members, "
            f"got {len(members)}"
        )
    dest = output_zip.expanduser().resolve()
    if dest.exists():
        raise PackageFormatError("package ZIP must not already exist")
    if dest.suffix.casefold() != ".zip":
        raise PackageFormatError("package output must be a .zip")
    expected_name = dated_zip_name(contract)
    if dest.name != expected_name:
        raise PackageFormatError(
            f"ZIP must be named {expected_name} for work dated {WORK_DATE.isoformat()}"
        )
    listed: List[Dict[str, object]] = []
    seen_names: set[str] = set()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member in members:
            path = member.expanduser().resolve()
            if not path.is_file():
                raise PackageFormatError(f"missing package member: {path}")
            if path.name in seen_names:
                raise PackageFormatError(f"duplicate member name: {path.name}")
            seen_names.add(path.name)
            digest = sha256_file(path)
            archive.write(path, arcname=path.name)
            listed.append(
                {
                    "name": path.name,
                    "sha256": digest,
                    "size_bytes": path.stat().st_size,
                }
            )
        if archive.testzip() is not None:
            dest.unlink(missing_ok=True)
            raise PackageFormatError("ZIP CRC failed")
    return MembershipReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        work_date=WORK_DATE.isoformat(),
        package_id=contract.package_id,
        zip_name=expected_name,
        exact_n=contract.exact_n,
        members=listed,
        zip_path=str(dest),
        zip_sha256=sha256_file(dest),
        technical_pass=True,
        packages_complete=False,
    )


def portfolio_status() -> Dict[str, object]:
    return {
        "schema_id": "dbx.abstract_portfolio_status",
        "schema_version": "1.0",
        "work_date": WORK_DATE.isoformat(),
        "role_rule": ROLE_NOT_FACTS,
        "packages": [
            {
                "package_id": item.package_id,
                "section": item.section,
                "county": item.county,
                "township": item.township,
                "exact_n": item.exact_n,
                "role": item.role,
                "status": "UNKNOWN",
                "image_count": "UNKNOWN",
                "ready_to_turn_in": False,
                "packages_complete": False,
            }
            for item in PACKAGE_CONTRACTS
        ],
        "notes": [
            "UNKNOWN stays UNKNOWN until a bind-dir image account is measured",
            "Do not convert UNKNOWN to zero",
            "Frozen and closed packages must not be rebuilt",
            "This inventory is not Drive Isolated/ and not owner release",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Format an isolated workbook like Section 13/15 and optionally "
            "assemble an exact-N ZIP dated 2026-09-22."
        )
    )
    parser.add_argument("--workbook", type=Path)
    parser.add_argument("--letter-output", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--package-id")
    parser.add_argument("--member", action="append", default=[], type=Path)
    parser.add_argument("--zip-output", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--portfolio", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        payload: Dict[str, object]
        if args.portfolio:
            payload = portfolio_status()
        elif args.package_id and args.zip_output is not None:
            membership = assemble_exact_package(
                package_id=args.package_id,
                members=args.member,
                output_zip=args.zip_output,
            )
            payload = membership.to_dict()
        elif args.workbook is not None and args.letter_output is not None:
            receipt = apply_letter_format(
                args.workbook,
                args.letter_output,
                profile_path=args.profile,
            )
            payload = receipt.to_dict()
        else:
            raise PackageFormatError(
                "Pass --portfolio, --workbook/--letter-output, "
                "or --package-id/--member/--zip-output"
            )
        write_new_json(payload, args.receipt, "package format receipt")
        print(
            json.dumps(
                {
                    "output": str(args.receipt),
                    "work_date": WORK_DATE.isoformat(),
                    "technical_pass": payload.get("technical_pass", True),
                    "packages_complete": False,
                },
                indent=2,
            )
        )
    except (OSError, PackageFormatError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0 if payload.get("technical_pass", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
