"""CLI for the land_title_os control layer.

    python -m core.land_title_os needs-me [--projects projects/]
    python -m core.land_title_os verify-receipts <receipts.jsonl>
    python -m core.land_title_os scan <directory> [--db assets.db] [--project ID]
    python -m core.land_title_os status <project-dir>
    python -m core.land_title_os dashboard [--projects projects/] [--out dashboard.html]
    python -m core.land_title_os backup-manifest <root> <manifest.json>
    python -m core.land_title_os verify-restore <restored-root> <manifest.json>
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

    p_status = sub.add_parser("status", help="factual project status report")
    p_status.add_argument("project_dir")

    p_dash = sub.add_parser("dashboard", help="generate the HTML control dashboard")
    p_dash.add_argument("--projects", default="projects")
    p_dash.add_argument("--out", default="dashboard.html")

    p_bman = sub.add_parser("backup-manifest", help="create a backup hash manifest")
    p_bman.add_argument("root")
    p_bman.add_argument("manifest")

    p_vres = sub.add_parser("verify-restore", help="verify a restored copy against a manifest")
    p_vres.add_argument("restored_root")
    p_vres.add_argument("manifest")

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

    if args.command == "status":
        from .health import status_report
        print(status_report(args.project_dir))
        return 0

    if args.command == "dashboard":
        from datetime import datetime, timezone

        from .dashboard import write_dashboard
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        out = write_dashboard(args.projects, args.out, generated_at=now)
        print(f"wrote {out}")
        return 0

    if args.command == "backup-manifest":
        from .backup import create_manifest
        manifest = create_manifest(args.root, args.manifest)
        print(f"hashed {manifest['file_count']} files into {args.manifest}")
        return 0

    if args.command == "verify-restore":
        from .backup import verify_restore
        problems = verify_restore(args.restored_root, args.manifest)
        if problems:
            print(f"RESTORE NOT VERIFIED — {len(problems)} problem(s):")
            for p in problems:
                print(f"  {p.describe()}")
            return 1
        print("restore verified: contents match the manifest exactly")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
