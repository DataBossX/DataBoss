"""Scriptable command-line interface for DataBossX.

Unlike the numbered interactive menu in :mod:`databossx.ui.command_center`, this
exposes every safety tool as a named subcommand so it can be driven from scripts,
Makefiles, and CI. Each command prints the artifact path(s) it produced; pass
``--json`` for machine-readable output.

Examples::

    databossx health
    databossx scan --fail-on-tracked        # non-zero exit if secrets are in git
    databossx inspect path/to/workbook.xlsx
    databossx preflight --max-rows 3
    databossx first-task --json

Run ``databossx --help`` or ``databossx <command> --help`` for details.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import backup, diagnostics, health, paths, project_map, secret_scan
from .excel import (
    mock_workbook,
    review_workbook,
    workbook_fingerprint,
    workbook_inspector,
)
from .title import titlepreviewfixer
from .ui import command_center

# Each handler returns (results, exit_code). ``results`` is a label->value dict
# that is printed as aligned text or, with --json, as a JSON object.


def _cmd_health(args: argparse.Namespace) -> tuple[dict, int]:
    return {"health_report": str(health.run())}, 0


def _cmd_backup(args: argparse.Namespace) -> tuple[dict, int]:
    r = backup.create_backup()
    return {
        "backup_zip": str(r.zip_path),
        "manifest": str(r.manifest_path),
        "sha256": r.sha256,
    }, 0


def _cmd_scan(args: argparse.Namespace) -> tuple[dict, int]:
    report = secret_scan.run()
    result = secret_scan.scan()
    tracked = len(result.tracked_findings)
    out = {
        "secret_scan_report": str(report),
        "files_scanned": result.files_scanned,
        "findings": len(result.findings),
        "tracked_findings": tracked,
    }
    code = 1 if (args.fail_on_tracked and tracked) else 0
    return out, code


def _cmd_map(args: argparse.Namespace) -> tuple[dict, int]:
    return {"project_map": str(project_map.run())}, 0


def _cmd_mock_workbook(args: argparse.Namespace) -> tuple[dict, int]:
    out = args.out and Path(args.out)
    return {"mock_workbook": str(mock_workbook.create_mock_workbook(out_path=out))}, 0


def _cmd_inspect(args: argparse.Namespace) -> tuple[dict, int]:
    report, links_csv, result = workbook_inspector.run(Path(args.workbook))
    return {
        "inspection_report": str(report),
        "links_csv": str(links_csv),
        "hyperlinks": result.total_hyperlinks,
    }, 0


def _cmd_review(args: argparse.Namespace) -> tuple[dict, int]:
    return {"review_copy": str(review_workbook.create_review_copy(Path(args.workbook)))}, 0


def _cmd_fingerprint(args: argparse.Namespace) -> tuple[dict, int]:
    fp = workbook_fingerprint.fingerprint(Path(args.workbook))
    return {"path": str(fp.path), "sha256": fp.sha256, "size": fp.size}, 0


def _cmd_preflight(args: argparse.Namespace) -> tuple[dict, int]:
    src = args.source and Path(args.source)
    res = titlepreviewfixer.run_preflight(
        source=src, max_rows=args.max_rows, budget=args.budget
    )
    return {
        "report": str(res.report_path),
        "suggestions_csv": str(res.suggestions_csv),
        "review_copy": str(res.review_copy),
        "source_unchanged": res.source_unchanged,
        "rows": len(res.rows),
    }, (0 if res.source_unchanged else 1)


def _cmd_diagnostics(args: argparse.Namespace) -> tuple[dict, int]:
    return {"diagnostics_bundle": str(diagnostics.build().zip_path)}, 0


def _cmd_first_task(args: argparse.Namespace) -> tuple[dict, int]:
    return dict(command_center.run_first_task()), 0


def _cmd_menu(args: argparse.Namespace) -> tuple[dict, int]:
    command_center.interactive()
    return {}, 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="databossx",
        description="Local-first safety tooling for the DataBossX title/runsheet workflow.",
    )
    parser.add_argument("--version", action="version", version=f"databossx {__version__}")
    parser.add_argument("--json", action="store_true", help="emit results as JSON")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    sub.add_parser("health", help="runtime/dependency/dir health check").set_defaults(func=_cmd_health)
    sub.add_parser("backup", help="zip backup with SHA-256 manifest (excludes secrets)").set_defaults(func=_cmd_backup)

    p_scan = sub.add_parser("scan", help="scan for secrets (location + type only)")
    p_scan.add_argument("--fail-on-tracked", action="store_true",
                        help="exit non-zero if any secret is tracked by git (CI gate)")
    p_scan.set_defaults(func=_cmd_scan)

    sub.add_parser("map", help="write a markdown project map").set_defaults(func=_cmd_map)

    p_mock = sub.add_parser("mock-workbook", help="create a fake runsheet (no real data)")
    p_mock.add_argument("-o", "--out", help="output .xlsx path")
    p_mock.set_defaults(func=_cmd_mock_workbook)

    p_insp = sub.add_parser("inspect", help="read-only inspect a workbook + export links")
    p_insp.add_argument("workbook", help="path to .xlsx")
    p_insp.set_defaults(func=_cmd_inspect)

    p_rev = sub.add_parser("review", help="create a review copy (AI columns on the COPY only)")
    p_rev.add_argument("workbook", help="path to source .xlsx")
    p_rev.set_defaults(func=_cmd_review)

    p_fp = sub.add_parser("fingerprint", help="SHA-256 fingerprint of a workbook")
    p_fp.add_argument("workbook", help="path to .xlsx")
    p_fp.set_defaults(func=_cmd_fingerprint)

    p_pre = sub.add_parser("preflight", help="gated TitlePreviewFixer 3-row preflight (mock OCR)")
    p_pre.add_argument("--source", help="source workbook (default: fresh mock)")
    p_pre.add_argument("--max-rows", type=int, default=3, help="rows to preflight (hard-capped)")
    p_pre.add_argument("--budget", type=float, default=1.0, help="cost-guard budget in USD")
    p_pre.set_defaults(func=_cmd_preflight)

    sub.add_parser("diagnostics", help="build a support bundle (excludes secrets)").set_defaults(func=_cmd_diagnostics)
    sub.add_parser("first-task", help="run the full safety-first first-task pass").set_defaults(func=_cmd_first_task)
    sub.add_parser("menu", help="launch the interactive command center").set_defaults(func=_cmd_menu)
    return parser


def _emit(results: dict, as_json: bool) -> None:
    if not results:
        return
    if as_json:
        print(json.dumps(results, indent=2, default=str))
        return
    width = max(len(k) for k in results)
    for key, value in results.items():
        print(f"{key.rjust(width)} : {value}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        results, code = args.func(args)
    except FileNotFoundError as exc:
        print(f"error: file not found: {exc}", file=sys.stderr)
        return 2
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as exc:  # noqa: BLE001 - surface a clean message to the operator
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _emit(results, args.json)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
