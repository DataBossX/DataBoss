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

from .isolated_delta import sha256_file

PACKET_SCHEMA_ID = "dbx.native_print_receipt"
PACKET_SCHEMA_VERSION = "1.0"
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
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workbook", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
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
