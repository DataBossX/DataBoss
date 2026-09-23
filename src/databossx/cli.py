"""Local-first DataBossX control CLI. Never writes to Drive or originals."""

from __future__ import annotations

import argparse
import json
import sys

from .config import DataBossConfig
from .connectors.drive import DriveConnection, GoogleDriveConnector
from .connectors.local import LocalFolderConnector
from .connectors.sync import apply_vault_ingest, plan_sync
from .intake import create_project
from .policy import POLICY_VERSION, PolicyEngine


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="databossx", description="DataBossX trusted kernel CLI")
    parser.add_argument("--repo-root", default=".", help="Repository or runtime root")
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health", help="Kernel and policy health")
    health.set_defaults(func=cmd_health)

    create = sub.add_parser("project-create", help="Create a draft project")
    create.add_argument("--name", required=True)
    create.add_argument("--jurisdiction", default="OK")
    create.add_argument("--project-id")
    create.set_defaults(func=cmd_project_create)

    scan = sub.add_parser("drive-scan", help="Read-only Drive or mirror scan")
    scan.add_argument("--root", required=True, help="Local Drive-export mirror or folder")
    scan.add_argument("--backend", default="local_mirror", choices=("local_mirror", "google_api"))
    scan.add_argument("--dry-run", action="store_true", default=True)
    scan.add_argument("--hash", action="store_true", help="Hash files (still read-only)")
    scan.set_defaults(func=cmd_drive_scan)

    sync = sub.add_parser("drive-sync-plan", help="Plan vault ingest between two roots")
    sync.add_argument("--left", required=True)
    sync.add_argument("--right", required=True)
    sync.add_argument("--project-id", required=True)
    sync.add_argument("--apply", action="store_true", help="Copy missing bytes into the vault only")
    sync.set_defaults(func=cmd_drive_sync_plan)

    return parser


def cmd_health(args: argparse.Namespace) -> int:
    write = PolicyEngine().decide("drive.write", write=True)
    _print_json(
        {
            "status": "ok",
            "policy_version": POLICY_VERSION,
            "external_write": write.allowed,
            "external_write_reason": write.reason,
        }
    )
    return 0


def cmd_project_create(args: argparse.Namespace) -> int:
    config = DataBossConfig.from_repo_root(args.repo_root)
    project = create_project(
        config,
        name=args.name,
        jurisdiction_code=args.jurisdiction,
        project_id=args.project_id,
    )
    _print_json({"project_id": project.project_id, "root": str(project.root_path)})
    return 0


def cmd_drive_scan(args: argparse.Namespace) -> int:
    connector = GoogleDriveConnector(
        DriveConnection(root_locator=args.root, backend=args.backend)
    )
    scan = connector.scan(dry_run=not args.hash)
    print(connector.export_manifest(scan))
    return 0


def cmd_drive_sync_plan(args: argparse.Namespace) -> int:
    left = LocalFolderConnector(args.left).scan(dry_run=False).items
    right = LocalFolderConnector(args.right).scan(dry_run=False).items
    plan = plan_sync(left, right)
    print(plan.to_json())
    if args.apply:
        config = DataBossConfig.from_repo_root(args.repo_root)
        ingested = apply_vault_ingest(config, args.project_id, plan)
        _print_json({"ingested": ingested, "provider_writes": 0})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
