"""CLI for the land_title_os control layer.

    python -m core.land_title_os needs-me [--projects projects/]
    python -m core.land_title_os verify-receipts <receipts.jsonl>
    python -m core.land_title_os scan <directory> [--db assets.db] [--project ID]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="land_title_os")
    sub = parser.add_subparsers(dest="command", required=True)

    p_needs = sub.add_parser("needs-me", help="decisions only a human can make")
    p_needs.add_argument("--projects", default="projects")

    p_ver = sub.add_parser("verify-receipts", help="verify a receipt ledger's hash chain")
    p_ver.add_argument("ledger")

    p_scan = sub.add_parser("scan", help="inventory a directory into the asset database")
    p_scan.add_argument("directory")
    p_scan.add_argument("--db", default="assets.db")
    p_scan.add_argument("--project", default=None)

    args = parser.parse_args(argv)

    if args.command == "needs-me":
        from .needs_me import collect, render
        print(render(collect(args.projects)))
        return 0

    if args.command == "verify-receipts":
        from .receipts import ReceiptLedger
        problems = ReceiptLedger(args.ledger).verify_chain()
        if problems:
            print("RECEIPT CHAIN BROKEN:")
            for p in problems:
                print(f"  {p}")
            return 1
        print("receipt chain intact")
        return 0

    if args.command == "scan":
        from .assets import AssetInventory
        inv = AssetInventory(args.db)
        registered = inv.scan_directory(Path(args.directory), project_id=args.project)
        dupes = inv.duplicate_groups()
        print(f"registered {len(registered)} files into {args.db} "
              f"({len(dupes)} duplicate group(s))")
        inv.close()
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
