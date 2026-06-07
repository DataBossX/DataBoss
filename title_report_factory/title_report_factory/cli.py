"""cli -- command line entry point.

Usage:
    python -m title_report_factory run --config configs/section_27_diversified.json
"""
from __future__ import annotations

import argparse
import json
import sys

from .pipeline import run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="title_report_factory",
                                     description="Automated cursory title report factory")
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="Run the full pipeline")
    p_run.add_argument("--config", required=True, help="Path to the run config JSON")
    p_run.add_argument("--quiet", action="store_true", help="Suppress stage logging")

    args = parser.parse_args(argv)
    if args.command == "run":
        log = (lambda *a, **k: None) if args.quiet else (lambda *a, **k: print(*a, **k, file=sys.stderr))
        summary = run(args.config, log=log)
        print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
