"""Command-line interface for the DataBossX control plane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .control_plane import ControlPlane


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="databossx", description="Controlled DataBossX project intake"
    )
    parser.add_argument("--database", default="databossx-control.sqlite3")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="initialize or verify the control database")

    project = commands.add_parser(
        "create-project", help="create a project from a JSON manifest"
    )
    project.add_argument("manifest")

    intake = commands.add_parser("intake", help="inventory a file or directory read-only")
    intake.add_argument("project_id")
    intake.add_argument("path")
    intake.add_argument("--source-authority", type=int, required=True, choices=range(1, 9))
    intake.add_argument("--role", default="source")
    intake.add_argument("--security-classification", default="CONFIDENTIAL")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    control = ControlPlane(args.database)
    backup = control.initialize()

    if args.command == "init":
        print(
            json.dumps(
                {
                    "database": str(control.database),
                    "backup": str(backup) if backup else None,
                }
            )
        )
        return 0

    if args.command == "create-project":
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        project_id = control.create_project(manifest)
        print(json.dumps({"project_id": project_id}))
        return 0

    root = Path(args.path).expanduser().resolve(strict=True)
    paths = (
        [root]
        if root.is_file()
        else sorted(path for path in root.rglob("*") if path.is_file())
    )
    asset_ids = []
    for path in paths:
        asset_ids.append(
            control.ingest_asset(
                args.project_id,
                path,
                source_authority=args.source_authority,
                role=args.role,
                security_classification=args.security_classification,
            )
        )

    revision = control.create_manifest_revision(
        args.project_id,
        {"project_id": args.project_id, "source_locations": [str(root)]},
        asset_ids,
    )
    print(
        json.dumps(
            {
                "project_id": args.project_id,
                "files_scanned": len(paths),
                "unique_assets": len(set(asset_ids)),
                "manifest_revision_id": revision,
            }
        )
    )
    return 0
