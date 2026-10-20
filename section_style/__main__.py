"""Command line for the Section 11 styler.

Examples:

    python -m section_style apply INPUT.xlsx OUTPUT.xlsx
    python -m section_style audit INPUT.xlsx
    python -m section_style apply-dir INPUT_DIR OUTPUT_DIR
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from openpyxl import load_workbook

from .apply import UnrecognizedWorkbook, apply_directory, apply_file
from .audit import audit_workbook


def _audit(path: Path) -> int:
    findings = audit_workbook(load_workbook(path))
    json.dump([item.to_dict() for item in findings], sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 1 if findings else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply or audit the Section 11 grid.")
    sub = parser.add_subparsers(dest="command", required=True)
    apply_cmd = sub.add_parser("apply", help="style one workbook")
    apply_cmd.add_argument("source", type=Path)
    apply_cmd.add_argument("dest", type=Path)
    audit_cmd = sub.add_parser("audit", help="list style gaps")
    audit_cmd.add_argument("source", type=Path)
    directory = sub.add_parser("apply-dir", help="style every recognized workbook in a folder")
    directory.add_argument("source", type=Path)
    directory.add_argument("dest", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "apply":
            results = apply_file(args.source, args.dest)
            for item in results:
                print(f"{item.sheet}: {item.kind} rows {item.header_row}-{item.last_row}")
            return 0
        if args.command == "audit":
            return _audit(args.source)
        written = apply_directory(args.source, args.dest)
        for path, results in written:
            kinds = ",".join(item.kind for item in results)
            print(f"{path}: {kinds}")
        return 0
    except UnrecognizedWorkbook as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
