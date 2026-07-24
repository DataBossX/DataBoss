"""Command-line entry point for the DataBossX local-first runtime.

Examples
--------
Run a title-intake project end to end against a read-only source folder::

    python -m databossx run-intake \
        --repo-root . \
        --name "Section 32" \
        --jurisdiction OK \
        --source /path/to/source_docs \
        --template /path/to/control_template.xlsx

Nothing in the source folder is modified: bytes are hashed and copied into the
content-addressed vault under ``<repo-root>/runtime``.
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import DataBossConfig
from .workers import run_project_intake


def _run_intake(args: argparse.Namespace) -> int:
    config = DataBossConfig.from_repo_root(args.repo_root)
    project, summary = run_project_intake(
        config,
        name=args.name,
        jurisdiction_code=args.jurisdiction,
        source_roots=list(args.source or []),
        template_path=args.template,
        project_id=args.project_id,
    )
    report = {
        "project_id": project.project_id,
        "name": project.name,
        "jurisdiction": project.jurisdiction_code,
        "run_status": summary.run_status,
        "tasks_processed": summary.processed,
        "tasks_succeeded": summary.succeeded,
        "tasks_failed": summary.failed,
        "tasks_remaining": summary.remaining,
        "runtime_root": str(config.runtime_root),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    # Non-zero exit if the run did not complete cleanly, for scripting/CI.
    return 0 if summary.run_status == "COMPLETED" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="databossx", description="DataBossX local-first runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run-intake", help="Create a project and run its title-intake workflow")
    run.add_argument("--repo-root", default=".", help="Repository root; runtime/ is created under it")
    run.add_argument("--name", required=True, help="Human-readable project name")
    run.add_argument("--jurisdiction", required=True, help="Jurisdiction code, e.g. OK")
    run.add_argument(
        "--source",
        action="append",
        metavar="PATH",
        help="Read-only source root to inventory (repeatable)",
    )
    run.add_argument("--template", default=None, help="Approved workbook template to register")
    run.add_argument("--project-id", default=None, help="Explicit project id (default: generated)")
    run.set_defaults(func=_run_intake)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover - process entry point
    sys.exit(main())
