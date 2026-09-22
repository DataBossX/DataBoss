"""Command-line entry for local, fail-closed checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .access import probe_access
from .ledger import build_ledger, hash_tree
from .package import verify_package
from .purity import check_purity
from .tournament import run_tournament, write_receipt


def _print(data: object) -> int:
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0


def _load_json(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="source_bound_finish",
        description="Fail-closed source-bound finish tools. Never invents facts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    access = sub.add_parser("access", help="probe a local source root")
    access.add_argument("--root", default="")

    census = sub.add_parser("census", help="hash and count local source files")
    census.add_argument("--root", required=True)

    ledger = sub.add_parser("ledger", help="build an unresolved page ledger")
    ledger.add_argument("paths", nargs="+")

    purity = sub.add_parser("purity", help="check client rows from JSON")
    purity.add_argument("rows_json")

    package = sub.add_parser("package", help="verify a ZIP package")
    package.add_argument("zip_path")
    package.add_argument("--member", action="append", dest="members")

    tournament = sub.add_parser("tournament", help="run one fail-closed cycle")
    tournament.add_argument("packet_json")
    tournament.add_argument("--receipt", default="")

    args = parser.parse_args(argv)
    if args.command == "access":
        receipt = probe_access(args.root or None)
        _print(receipt.to_dict())
        return 0 if receipt.status != "BLOCKED" else 2
    if args.command == "census":
        return _print(hash_tree(args.root))
    if args.command == "ledger":
        return _print(build_ledger(args.paths).to_dict())
    if args.command == "purity":
        rows = _load_json(args.rows_json)
        return _print([item.to_dict() for item in check_purity(rows)])
    if args.command == "package":
        return _print(verify_package(args.zip_path, expected_members=args.members))
    if args.command == "tournament":
        packet = _load_json(args.packet_json)
        result = run_tournament(packet)
        if args.receipt:
            write_receipt(result, args.receipt)
        _print(result.to_dict())
        return 0 if result.complete else 2
    parser.error("unknown command")


if __name__ == "__main__":
    sys.exit(main())
