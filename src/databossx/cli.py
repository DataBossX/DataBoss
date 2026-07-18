from __future__ import annotations

import argparse
import ipaddress
import json
import secrets
import threading
import webbrowser
from pathlib import Path
from typing import Sequence

from .config import KernelConfig
from .service import KernelService


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="databossx",
        description="DataBossX trusted local evidence and report kernel",
    )
    parser.add_argument(
        "--runtime", type=Path, help="Override local runtime folder (testing/recovery)"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Initialize and verify local storage")
    commands.add_parser("demo", help="Run the safe synthetic project end to end")
    add = commands.add_parser("project-add", help="Register a read-only source folder")
    add.add_argument("--name", required=True)
    add.add_argument("--source", type=Path, required=True)
    ingest = commands.add_parser("ingest", help="Hash and ingest one project")
    ingest.add_argument("project_id")
    search = commands.add_parser("search", help="Search extracted source text")
    search.add_argument("project_id")
    search.add_argument("query")
    run = commands.add_parser("run-grocery", help="Build draft report artifacts")
    run.add_argument("project_id")
    title_import = commands.add_parser(
        "title-import", help="Import operator-reviewed title records from JSON"
    )
    title_import.add_argument("project_id")
    title_import.add_argument("json_file", type=Path)
    title_build = commands.add_parser(
        "title-build", help="Build exact XLSX/PDF examiner packet"
    )
    title_build.add_argument("title_case_id")
    title_review = commands.add_parser(
        "title-review", help="Approve or reject an exact package hash"
    )
    title_review.add_argument("run_id")
    title_review.add_argument("manifest_sha256")
    title_review.add_argument("--reviewer", required=True)
    title_review.add_argument("--decision", choices=("APPROVE", "REJECT"), required=True)
    title_review.add_argument("--notes", default="")
    serve = commands.add_parser("serve", help="Start loopback Command Center")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--open", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = KernelConfig.default(args.runtime)
    service = KernelService(config)
    if args.command == "init":
        _print(service.health())
    elif args.command == "demo":
        project = service.create_synthetic_project()
        ingest = service.ingest_project(project["id"])
        run = service.run_grocery(project["id"])
        _print(
            {
                "project": project,
                "ingest": ingest,
                "run": run,
                "artifacts": service.list_artifacts(run["id"]),
                "health": service.health(),
            }
        )
    elif args.command == "project-add":
        _print(service.create_project(args.name, args.source))
    elif args.command == "ingest":
        _print(service.ingest_project(args.project_id))
    elif args.command == "search":
        _print(service.search(args.project_id, args.query))
    elif args.command == "run-grocery":
        run = service.run_grocery(args.project_id)
        _print({"run": run, "artifacts": service.list_artifacts(run["id"])})
    elif args.command == "title-import":
        payload = json.loads(args.json_file.read_text(encoding="utf-8"))
        _print(service.create_title_case(args.project_id, payload))
    elif args.command == "title-build":
        _print(service.build_title_package(args.title_case_id))
    elif args.command == "title-review":
        _print(
            service.review_title_package(
                args.run_id,
                args.manifest_sha256,
                args.reviewer,
                args.decision,
                args.notes,
            )
        )
    elif args.command == "serve":
        try:
            address = ipaddress.ip_address(args.host)
        except ValueError:
            if args.host != "localhost":
                raise SystemExit("Dashboard host must be localhost or a loopback address")
        else:
            if not address.is_loopback:
                raise SystemExit("Dashboard must remain loopback-only")
        if not 1 <= args.port <= 65535:
            raise SystemExit("Port must be between 1 and 65535")
        try:
            import uvicorn
        except ImportError as exc:
            raise SystemExit(
                "Dashboard dependencies missing. Install requirements-kernel.txt"
            ) from exc
        from .api import create_app

        token = secrets.token_urlsafe(32)
        app = create_app(service, token)
        url = f"http://{args.host}:{args.port}/#token={token}"
        print(f"DataBossX is local-only at http://{args.host}:{args.port}/")
        if args.open:
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0
