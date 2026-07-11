"""The ``databossx`` command line interface.

Subcommands: doctor, env, new, discover, run, plugins. Every subcommand is a
thin adapter over a tested module; the CLI adds argument parsing, human
output, and exception-to-exit-code translation only.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .config import FoundryConfig, load_config
from .errors import DoctorUnclean, FoundryError
from .logs import setup_logging

log = logging.getLogger("databossx.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="databossx",
        description="DataBossX Foundry — bootstrap layer for the automation platform.",
    )
    parser.add_argument("--version", action="version", version=f"databossx {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="check (and optionally install) required tooling")
    p_doctor.add_argument("--core-only", action="store_true",
                          help="only require the bootstrap essentials (python, pip, git)")
    p_doctor.add_argument("--install", action="store_true",
                          help="attempt to install missing tools with the platform package manager")
    p_doctor.add_argument("--out", type=Path, default=None,
                          help="where to write doctor_report.json (default: cwd)")

    p_env = sub.add_parser("env", help="create/repair an isolated venv with a lockfile")
    p_env.add_argument("project", help="project name under projects/ (or a path)")

    p_new = sub.add_parser("new", help="scaffold a new project")
    p_new.add_argument("project", help="project name (slug)")

    p_disc = sub.add_parser("discover", help="scan work roots and write ranked registry.json")
    p_disc.add_argument("--root", action="append", type=Path, default=None,
                        help="override discovery root(s); repeatable")
    p_disc.add_argument("--out", type=Path, default=None,
                        help="registry output path (default: <root>/registry.json)")

    p_run = sub.add_parser("run", help="run a task declared in a project's PLAN.md")
    p_run.add_argument("ref", help="task reference '<project>.<task>' (e.g. demo.hello)")

    p_plug = sub.add_parser("plugins", help="list, validate, or run installed plugins")
    plug_sub = p_plug.add_subparsers(dest="plugins_command", required=True)
    plug_sub.add_parser("list", help="list installed plugins with validity status")
    p_val = plug_sub.add_parser("validate", help="validate one plugin (or all)")
    p_val.add_argument("name", nargs="?", default=None)
    p_runp = plug_sub.add_parser("run", help="execute '<plugin>:<entrypoint>'")
    p_runp.add_argument("ref", help="e.g. safety_kernel:smoke")
    p_runp.add_argument("--json", dest="payload", default=None,
                        help="JSON object passed to the entrypoint as its payload")
    return parser


def _cmd_doctor(config: FoundryConfig, args: argparse.Namespace) -> int:
    from . import doctor as doc

    result = doc.run_doctor(core_only=args.core_only)
    if args.install and result.missing:
        attempts = doc.install_missing(result)
        for key, cmd, rc in attempts:
            status = "ok" if rc == 0 else f"FAILED (exit {rc})"
            print(f"  install {key}: {status} — {cmd}")
        result = doc.run_doctor(core_only=args.core_only)
    print(doc.format_report(result))
    out = args.out or Path.cwd() / "doctor_report.json"
    path = doc.write_report(result, out)
    print(f"  report: {path}")
    if not result.clean:
        raise DoctorUnclean(
            "environment is not clean; run the printed install commands "
            "(or `databossx doctor --install`) and re-run"
        )
    return 0


def _cmd_env(config: FoundryConfig, args: argparse.Namespace) -> int:
    from .envs import ensure_env

    report = ensure_env(config, args.project)
    for line in report.log_lines:
        print(f"  {line}")
    state = "created" if report.created else ("repaired" if report.repaired else "healthy")
    print(f"env {report.project}: {state}; python: {report.python_path}; "
          f"lockfile: {report.lockfile}")
    return 0


def _cmd_new(config: FoundryConfig, args: argparse.Namespace) -> int:
    from .scaffold import scaffold_project

    report = scaffold_project(config, args.project)
    print(f"project {report.project}: {report.project_dir}")
    for name in report.created:
        print(f"  created: {name}")
    for name in report.skipped_existing:
        print(f"  kept existing: {name}")
    print(f"next: databossx run {report.project}.hello")
    return 0


def _cmd_discover(config: FoundryConfig, args: argparse.Namespace) -> int:
    from .discover import discover, write_registry

    registry = discover(config, roots=args.root)
    out, snapshot = write_registry(config, registry, out=args.out)
    projects = registry["projects"]
    skipped = registry["skipped_complete"]
    for root in registry["roots"]:
        marker = "" if root["exists"] else "  (missing)"
        print(f"  root: {root['path']}{marker}")
    print(f"  {len(projects)} open project(s), {len(skipped)} completed skipped")
    for item in projects:
        missing = ", ".join(item["missing"]) or "none"
        print(f"    [{item['score']:>3}] {item['name']:<30} missing: {missing}")
    print(f"  registry: {out}\n  snapshot: {snapshot}")
    return 0


def _cmd_run(config: FoundryConfig, args: argparse.Namespace) -> int:
    from .runner import run_task

    result = run_task(config, args.ref)
    for step in result.steps:
        tail = step.stdout_tail.strip()
        if tail:
            print(tail)
    print(f"{result.project}.{result.task}: {result.status} in {result.duration_s}s")
    print(f"  log:    {result.log_path}")
    print(f"  output: {result.output_path}")
    return 0


def _cmd_plugins(config: FoundryConfig, args: argparse.Namespace) -> int:
    from .plugins.loader import call_entrypoint, discover_plugins, validate_plugin

    if args.plugins_command == "list":
        plugins = discover_plugins(config.plugins_dir)
        if not plugins:
            print(f"no plugins installed under {config.plugins_dir}")
            return 0
        for p in plugins:
            status = "ok" if p.valid else "INVALID"
            version = p.manifest.version if p.manifest else "?"
            print(f"  [{status}] {p.name} {version} — "
                  f"{p.manifest.description if p.manifest else '; '.join(p.errors)}")
        return 0

    if args.plugins_command == "validate":
        targets = (
            [config.plugins_dir / args.name]
            if args.name
            else [p.directory for p in discover_plugins(config.plugins_dir)]
        )
        if not targets:
            print(f"no plugins found under {config.plugins_dir}")
            return 0
        bad = 0
        for directory in targets:
            loaded = validate_plugin(directory)
            if loaded.valid:
                print(f"  ok: {loaded.name} {loaded.manifest.version}")
            else:
                bad += 1
                print(f"  INVALID: {loaded.name}")
                for err in loaded.errors:
                    print(f"    - {err}")
        if bad:
            raise FoundryError(f"{bad} plugin(s) failed validation")
        return 0

    # plugins run
    payload = None
    if args.payload:
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            raise FoundryError(f"--json is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise FoundryError("--json must be a JSON object")
    result = call_entrypoint(config.plugins_dir, args.ref, payload)
    print(json.dumps(result, indent=2, default=str))
    return 0


_COMMANDS = {
    "doctor": _cmd_doctor,
    "env": _cmd_env,
    "new": _cmd_new,
    "discover": _cmd_discover,
    "run": _cmd_run,
    "plugins": _cmd_plugins,
}


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(verbose=args.verbose)
    config = load_config()
    try:
        return _COMMANDS[args.command](config, args)
    except FoundryError as exc:
        log.error("%s", exc)
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
