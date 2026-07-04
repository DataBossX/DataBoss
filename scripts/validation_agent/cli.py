"""Command-line entrypoint: run the perfection loop and emit reports.

Usage:
    python -m validation_agent.cli run <workbook.xlsx> [--max-iters N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .models import LoopState
from .orchestrator import PerfectionLoop
from .reporting.audit_report import AuditReportBuilder
from .reporting.certification import Certifier


def _run(args: argparse.Namespace) -> int:
    loop = PerfectionLoop(args.workbook)
    outcome = loop.run(max_iterations=args.max_iters)
    workdir = Path(loop.conn.execute(
        "SELECT path FROM versions WHERE run_id=? ORDER BY version LIMIT 1",
        (loop.run_id,)).fetchone()["path"]).parent

    report = AuditReportBuilder(loop.conn, loop.run_id).build(workdir / "audit_report.md")

    print(f"run_id      : {loop.run_id}")
    print(f"final state : {outcome.state.value}")
    print(f"iterations  : {outcome.iterations}")
    print(f"final ver   : v{outcome.final_version} -> {outcome.final_path.name}")
    if outcome.scorecard:
        for gate, score in outcome.scorecard.scores.items():
            print(f"  {gate.value:16} {'PASS' if score.passed else score.worst.value} "
                  f"({score.failures} failures)")
    print(f"audit report: {report}")
    for tkt in outcome.escalations:
        print(f"  ESCALATION [{tkt.gate.value}/{tkt.category.value}]: {tkt.reason}")

    if outcome.state == LoopState.CERTIFIED:
        art = Certifier(loop.conn, loop.run_id).certify(
            outcome.final_path, outcome.final_version, outcome.state, workdir)
        print(f"CERTIFIED   : {art.workbook_path.name} (sha {art.sha256[:12]}…)")
        print(f"title picture: {art.summary_path}")
    return 0 if outcome.state in (LoopState.CERTIFIED, LoopState.ESCALATED) else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="validation_agent")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run the perfection loop on a workbook")
    run.add_argument("workbook", type=str)
    run.add_argument("--max-iters", type=int, default=25)
    run.set_defaults(func=_run)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
