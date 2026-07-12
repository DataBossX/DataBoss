"""Operator CLI for the trusted DataBossX kernel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .command_center import CommandCenter
from .providers import provider_health
from .section32 import execute_source_limited_run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="databossx")
    parser.add_argument("--runtime", type=Path, default=Path("runtime"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("health")
    subparsers.add_parser("process-once")
    subparsers.add_parser("run-section32")
    args = parser.parse_args(argv)

    if args.command == "health":
        value = {
            "status": "PASS",
            "runtime": str(args.runtime.resolve()),
            "providers": provider_health(network_checks=False),
            "secrets_exposed": False,
        }
        print(json.dumps(value, indent=2))
        return 0
    if args.command == "run-section32":
        run_dir = execute_source_limited_run(args.runtime / "section32_runs")
        print(run_dir)
        return 2  # truthful partial/blocking result

    center = CommandCenter(args.runtime / "command_center")
    try:
        with center.single_instance():
            result = center.process_next()
        print(json.dumps(result or {"status": "idle"}, indent=2))
        return 0
    finally:
        center.close()


if __name__ == "__main__":
    sys.exit(main())
