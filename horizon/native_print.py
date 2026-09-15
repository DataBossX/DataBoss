"""Bind a writer-held native Excel Print Preview receipt.

This module does not launch Excel, invent a page count, or mutate a
workbook. ``technical_pass`` means only that the receipt names Microsoft
Excel on Windows, US Letter, landscape, print titles, and a page count
that matches the writer-held expected count for that workbook hash.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .examiner import require_named_examiner, write_new_json
from .isolated_delta import sha256_file

PACKET_SCHEMA_ID = "dbx.native_print_receipt"
PACKET_SCHEMA_VERSION = "1.0"
DRAFT_SCHEMA_ID = "dbx.native_print_draft"
DRAFT_SCHEMA_VERSION = "1.0"
DRAFT_STATUS = "UNAPPROVED_DRAFT"
RECEIPT_SCHEMA_ID = "dbx.native_print_gate_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
REQUIRED_KEYS = {
    "schema_id",
    "schema_version",
    "packet_id",
    "workbook_sha256",
    "application",
    "host",
    "paper_size",
    "orientation",
    "page_count",
    "expected_page_count",
    "print_titles",
    "print_area_set",
    "operator",
}
NATIVE_APPLICATION = "Microsoft Excel"
NATIVE_HOST = "Windows"
LETTER_VALUES = {1, "1", "Letter", "LETTER", "letter"}


class NativePrintError(ValueError):
    """Raised when a native-print receipt is unsafe or not native."""


@dataclass
class NativePrintGateReceipt:
    generated_utc: str
    packet_id: str
    workbook: str
    workbook_sha256: str
    page_count: int
    expected_page_count: int
    issues: List[str]
    technical_pass: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            "technical_pass is not package release",
            "Drive readback remains a separate owner step",
        ]
    )

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        raise NativePrintError(f"{label} must be a single-line string")
    return value.strip()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def assess_native_print(
    payload: Dict[str, object],
    *,
    workbook: Optional[Path] = None,
) -> NativePrintGateReceipt:
    if set(payload) != REQUIRED_KEYS:
        raise NativePrintError("Native print receipt has invalid top-level fields")
    if (
        payload["schema_id"] != PACKET_SCHEMA_ID
        or payload["schema_version"] != PACKET_SCHEMA_VERSION
    ):
        raise NativePrintError("Native print receipt schema is invalid")
    packet_id = _require_text(payload["packet_id"], "packet_id")
    digest = payload["workbook_sha256"]
    if isinstance(digest, str):
        digest = digest.casefold()
    if not _is_sha256(digest):
        raise NativePrintError("workbook_sha256 is invalid")
    workbook_path = ""
    if workbook is not None:
        workbook_path = str(workbook.expanduser().resolve())
        actual = sha256_file(workbook)
        if actual != digest:
            raise NativePrintError(
                "Workbook hash does not match the native print receipt"
            )
    issues: List[str] = []
    application = _require_text(payload["application"], "application")
    if application != NATIVE_APPLICATION:
        issues.append(
            f"application {application!r} is not {NATIVE_APPLICATION}"
        )
    host = _require_text(payload["host"], "host")
    if host != NATIVE_HOST:
        issues.append(f"host {host!r} is not {NATIVE_HOST}")
    paper = payload["paper_size"]
    if paper not in LETTER_VALUES:
        issues.append(f"paper_size {paper!r} is not US Letter")
    orientation = _require_text(payload["orientation"], "orientation")
    if orientation != "landscape":
        issues.append(f"orientation {orientation!r} is not landscape")
    page_count = payload["page_count"]
    expected = payload["expected_page_count"]
    if type(page_count) is not int or page_count < 1:
        raise NativePrintError("page_count must be an integer >= 1")
    if type(expected) is not int or expected < 1:
        raise NativePrintError("expected_page_count must be an integer >= 1")
    if page_count != expected:
        issues.append(
            f"page_count {page_count} does not match expected_page_count {expected}"
        )
    if payload["print_titles"] is not True:
        issues.append("print_titles must be true")
    if payload["print_area_set"] is not True:
        issues.append("print_area_set must be true")
    _require_text(payload["operator"], "operator")
    return NativePrintGateReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        packet_id=packet_id,
        workbook=workbook_path,
        workbook_sha256=digest,
        page_count=page_count,
        expected_page_count=expected,
        issues=issues,
        technical_pass=not issues,
    )


def write_native_print_packet(
    *,
    workbook: Path,
    output: Path,
    operator: str,
    page_count: int,
    expected_page_count: int,
    packet_id: str,
) -> Dict[str, object]:
    """Write a writer-held Excel Print Preview packet. Does not invent page counts."""
    try:
        named = require_named_examiner(operator)
    except ValueError as exc:
        raise NativePrintError(str(exc)) from exc
    if type(page_count) is not int or page_count < 1:
        raise NativePrintError("page_count must be an integer >= 1")
    if type(expected_page_count) is not int or expected_page_count < 1:
        raise NativePrintError("expected_page_count must be an integer >= 1")
    if page_count != expected_page_count:
        raise NativePrintError("page_count must match expected_page_count")
    resolved = workbook.expanduser()
    if not resolved.is_file():
        raise NativePrintError(f"workbook does not exist: {resolved}")
    packet = {
        "schema_id": PACKET_SCHEMA_ID,
        "schema_version": PACKET_SCHEMA_VERSION,
        "packet_id": packet_id.strip(),
        "workbook_sha256": sha256_file(resolved),
        "application": NATIVE_APPLICATION,
        "host": NATIVE_HOST,
        "paper_size": 1,
        "orientation": "landscape",
        "page_count": page_count,
        "expected_page_count": expected_page_count,
        "print_titles": True,
        "print_area_set": True,
        "operator": named,
    }
    if not packet["packet_id"] or "\n" in packet["packet_id"]:
        raise NativePrintError("packet_id must be a single-line string")
    try:
        write_new_json(packet, output, "native print packet")
    except ValueError as exc:
        raise NativePrintError(str(exc)) from exc
    assessed = assess_native_print(packet, workbook=resolved)
    if not assessed.technical_pass:
        raise NativePrintError("; ".join(assessed.issues) or "native print packet failed")
    return packet


def write_native_print_draft(
    *,
    workbook: Path,
    output: Path,
    packet_id: str,
) -> Dict[str, object]:
    """Hash-bind a draft. Does not invent a page count or name an examiner."""
    resolved = workbook.expanduser().resolve()
    if not resolved.is_file():
        raise NativePrintError(f"workbook does not exist: {resolved}")
    token = packet_id.strip()
    if not token or "\n" in token:
        raise NativePrintError("packet_id must be a single-line string")
    draft = {
        "schema_id": DRAFT_SCHEMA_ID,
        "schema_version": DRAFT_SCHEMA_VERSION,
        "status": DRAFT_STATUS,
        "packet_id": token,
        "workbook_sha256": sha256_file(resolved),
        "application": NATIVE_APPLICATION,
        "host": NATIVE_HOST,
        "paper_size": 1,
        "orientation": "landscape",
        "print_titles": True,
        "print_area_set": True,
        "page_count": None,
        "operator": "",
        "notes": [
            "UNAPPROVED_DRAFT cannot bind native_print",
            "Attest with a named examiner and the Windows Excel page count",
        ],
    }
    output = output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(draft, indent=2, sort_keys=True), encoding="utf-8")
    return draft


def attest_native_print_draft(
    draft: Dict[str, object],
    *,
    workbook: Path,
    output: Path,
    operator: str,
    page_count: int,
) -> Dict[str, object]:
    """Promote a draft after Print Preview. Horizon does not invent page_count."""
    if (
        draft.get("schema_id") != DRAFT_SCHEMA_ID
        or draft.get("schema_version") != DRAFT_SCHEMA_VERSION
        or draft.get("status") != DRAFT_STATUS
    ):
        raise NativePrintError("native print draft schema is invalid")
    resolved = workbook.expanduser().resolve()
    if not resolved.is_file():
        raise NativePrintError(f"workbook does not exist: {resolved}")
    actual = sha256_file(resolved)
    expected = str(draft.get("workbook_sha256") or "").casefold()
    if actual != expected:
        raise NativePrintError(
            "Workbook hash does not match the native print draft; reprint "
            "the current isolated workbook"
        )
    return write_native_print_packet(
        workbook=resolved,
        output=output,
        operator=operator,
        page_count=page_count,
        expected_page_count=page_count,
        packet_id=str(draft.get("packet_id") or ""),
    )


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativePrintError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise NativePrintError(f"{path} must contain a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bind a writer-held native Excel Print Preview receipt."
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--attest", action="store_true")
    parser.add_argument("--from-draft", type=Path)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workbook", type=Path)
    parser.add_argument("--operator")
    parser.add_argument("--page-count", type=int)
    parser.add_argument("--expected-page-count", type=int)
    parser.add_argument("--packet-id")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.draft:
            if args.workbook is None or args.packet_id is None:
                raise NativePrintError("--draft requires --workbook and --packet-id")
            draft = write_native_print_draft(
                workbook=args.workbook,
                output=args.output,
                packet_id=args.packet_id,
            )
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "status": draft["status"],
                        "workbook_sha256": draft["workbook_sha256"],
                        "packages_complete": False,
                    },
                    indent=2,
                )
            )
            return 0
        if args.attest:
            if args.from_draft is None or args.workbook is None or args.operator is None:
                raise NativePrintError(
                    "--attest requires --from-draft, --workbook, --operator, "
                    "and --page-count"
                )
            if args.page_count is None:
                raise NativePrintError(
                    "Pass the Print Preview page count; Horizon does not invent it"
                )
            packet = attest_native_print_draft(
                _load_json(args.from_draft),
                workbook=args.workbook,
                output=args.output,
                operator=args.operator,
                page_count=args.page_count,
            )
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "workbook_sha256": packet["workbook_sha256"],
                        "page_count": packet["page_count"],
                        "packages_complete": False,
                    },
                    indent=2,
                )
            )
            return 0
        if args.write:
            if args.workbook is None or args.operator is None or args.packet_id is None:
                raise NativePrintError(
                    "--write requires --workbook, --operator, --packet-id, "
                    "--page-count, and --expected-page-count"
                )
            if args.page_count is None or args.expected_page_count is None:
                raise NativePrintError(
                    "Pass the Print Preview page count; Horizon does not invent it"
                )
            packet = write_native_print_packet(
                workbook=args.workbook,
                output=args.output,
                operator=args.operator,
                page_count=args.page_count,
                expected_page_count=args.expected_page_count,
                packet_id=args.packet_id,
            )
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "workbook_sha256": packet["workbook_sha256"],
                        "page_count": packet["page_count"],
                        "packages_complete": False,
                    },
                    indent=2,
                )
            )
            return 0
        if args.packet is None:
            raise NativePrintError("Pass --packet to assess, or --write to create")
        receipt = assess_native_print(
            _load_json(args.packet),
            workbook=args.workbook,
        )
        args.output.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except (OSError, NativePrintError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "technical_pass": receipt.technical_pass,
                "page_count": receipt.page_count,
                "issues": receipt.issues,
            },
            indent=2,
        )
    )
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
