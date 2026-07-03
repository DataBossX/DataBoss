"""Command-line entrypoint for the DataBossX Validation & Repair Agent.

Usage:
    python -m validation_agent.main path/to/workbook.xlsx

Initializes the append-only memory layer, runs the perfection loop over the
supplied workbook, writes the versioned deliverables, and prints a summary.
The source workbook is never modified.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .core.orchestrator import PerfectionLoopOrchestrator
from .db.db_client import db
from .reports.output_generator import OutputGenerator


def run_agent(source: str, *, timestamp: str | None = None) -> int:
    db.init()
    ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    orchestrator = PerfectionLoopOrchestrator()
    outcome = orchestrator.run(source, timestamp=ts)
    paths = OutputGenerator().generate(outcome)

    print(f"\n=== {outcome.run_id} ===")
    print(f"Final state : {outcome.final_state}")
    print(f"Certified   : {outcome.certified}")
    print(f"Iterations  : {len(outcome.iterations)}")
    print(f"Final version: v{outcome.final_version}")
    print(f"API spend   : ${outcome.total_spend:.2f} / $100.00 cap")
    print(f"Message     : {outcome.message}")
    if outcome.escalations:
        print(f"Escalations : {len(outcome.escalations)}")
        for e in outcome.escalations:
            print(f"  - [{e.severity.value}] {e.failed_gate}: {e.repair_blocked_reason}")
    print("Outputs:")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    return 0 if outcome.certified else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DataBossX Validation & Repair Agent")
    parser.add_argument("workbook", help="Path to the source .xlsx workbook")
    parser.add_argument("--timestamp", default=None,
                        help="Override the run timestamp (YYYYMMDD_HHMMSS).")
    args = parser.parse_args(argv)
    if not Path(args.workbook).is_file():
        parser.error(f"workbook not found: {args.workbook}")
    return run_agent(args.workbook, timestamp=args.timestamp)


if __name__ == "__main__":
    sys.exit(main())
