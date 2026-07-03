"""Command-line entry point for a single validation run (no dashboard).

Usage:
    python tools/run_agent.py <workbook.xlsx> [--approve-paid]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from config.settings import get_settings
from core.orchestrator import Orchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="DataBossX Validation Agent")
    parser.add_argument("workbook", help="Path to source workbook (.xlsx/.xlsm)")
    parser.add_argument("--approve-paid", action="store_true",
                        help="Examiner pre-approves paid source retrieval "
                             "(still hard-capped at $100).")
    args = parser.parse_args()

    wb = Path(args.workbook)
    if not wb.exists():
        print(f"ERROR: workbook not found: {wb}", file=sys.stderr)
        return 2

    settings = get_settings(refresh=True)
    settings.ensure_dirs()
    print(f"Mode: {'DRY-RUN' if settings.dry_run else 'LIVE'} · "
          f"cap ${settings.api_cap_usd} · max_iter {settings.max_iterations}")

    orch = Orchestrator(settings)
    try:
        result = orch.run(wb, examiner_approved_spend=args.approve_paid)
    finally:
        orch.close()

    print(f"\nRun:        {result.run_id}")
    print(f"Status:     {result.status}")
    print(f"Final state:{result.final_state}")
    print(f"Iterations: {result.iterations}")
    print(f"Escalations:{len(result.escalations)}")
    print(f"Run folder: {result.run_dir}")
    print("Exports:")
    for e in result.exports:
        print(f"  - {e}")
    # Exit code communicates terminal outcome to the launcher.
    return 0 if result.status == "CERTIFIED" else 3


if __name__ == "__main__":
    raise SystemExit(main())
