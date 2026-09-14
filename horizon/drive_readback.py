"""Bind a Drive (or other) readback copy to the isolated workbook hash.

The gate does not upload, download, or mutate files. It only compares
SHA-256 of two existing paths. Matching hashes are not package release.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .isolated_delta import sha256_file

RECEIPT_SCHEMA_ID = "dbx.drive_readback_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
_ISOLATED_WORKBOOK_SECTION = re.compile(
    r"^section(\d+)-(letter|delta(?:-\d+)?)\.xlsx$",
    re.IGNORECASE,
)
_FOLDER_SECTION = re.compile(
    r"(?i)(?:^|[^a-z0-9])sec(?:tion)?[\s_-]*0?(11|13|15)(?![a-z0-9])"
)
_FOLDER_TOWNSHIP = re.compile(
    r"(?i)^0?(11|13|15)-\d{1,2}[ns]-\d{1,3}[ew]$"
)


def path_folder_sections(path: Path) -> List[int]:
    """Priority sections named by parent folders, not the filename."""
    found: List[int] = []
    for part in path.parts[:-1]:
        if part.casefold() == "isolated":
            continue
        match = _FOLDER_SECTION.search(part) or _FOLDER_TOWNSHIP.fullmatch(part)
        if match is None:
            continue
        number = int(match.group(1))
        if number not in found:
            found.append(number)
    return found


def is_drive_isolated_copy(path: Path, section: int) -> bool:
    """True when Isolated/ names this section and no folder names another."""
    if not any(part.casefold() == "isolated" for part in path.parts):
        return False
    match = _ISOLATED_WORKBOOK_SECTION.match(path.name)
    if match is None or int(match.group(1)) != section:
        return False
    return not any(number != section for number in path_folder_sections(path))


def isolated_workbook_filename(path: Optional[Path], section: int) -> str:
    """Name the current isolated Letter or delta, or sectionN-letter.xlsx."""
    if path is not None:
        match = _ISOLATED_WORKBOOK_SECTION.match(path.name)
        if match is not None and int(match.group(1)) == section:
            return path.name
    return f"section{section}-letter.xlsx"


class DriveReadbackError(ValueError):
    """Raised when Drive readback cannot be bound safely."""


@dataclass
class DriveReadbackReceipt:
    generated_utc: str
    workbook: str
    workbook_sha256: str
    readback: str
    readback_sha256: str
    issues: List[str]
    technical_pass: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            "technical_pass means the two files are byte-identical",
            "This is not package release",
        ]
    )

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def assess_drive_readback(
    workbook: Path,
    readback: Path,
) -> DriveReadbackReceipt:
    workbook = workbook.expanduser().resolve()
    readback = readback.expanduser().resolve()
    if not workbook.is_file():
        raise DriveReadbackError(f"Workbook does not exist: {workbook}")
    if not readback.is_file():
        raise DriveReadbackError(f"Readback copy does not exist: {readback}")
    if workbook == readback:
        raise DriveReadbackError(
            "Readback path must be a distinct Drive/PC copy, not the same file"
        )
    workbook_sha = sha256_file(workbook)
    readback_sha = sha256_file(readback)
    issues: List[str] = []
    if workbook_sha != readback_sha:
        issues.append("Drive/PC readback hash does not match the isolated workbook")
    return DriveReadbackReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        workbook=str(workbook),
        workbook_sha256=workbook_sha,
        readback=str(readback),
        readback_sha256=readback_sha,
        issues=issues,
        technical_pass=not issues,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare an isolated workbook to a Drive/PC readback copy."
    )
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--readback", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        receipt = assess_drive_readback(args.workbook, args.readback)
        args.output.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except (OSError, DriveReadbackError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "technical_pass": receipt.technical_pass,
                "issues": receipt.issues,
            },
            indent=2,
        )
    )
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
