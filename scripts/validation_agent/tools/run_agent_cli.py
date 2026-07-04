"""
Command-line entry point for a single validation run.

Usage:
    python tools/run_agent_cli.py <workbook.xlsx> [--extra-report-dir DIR ...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import load_settings
from db.db_client import DatabaseManager
from core.orchestrator import Orchestrator


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DataBossX Validation Agent — one run")
    ap.add_argument("workbook", help="Path to the source workbook (.xlsx/.xlsm)")
    ap.add_argument("--extra-report-dir", action="append", default=[],
                    help="Additional folder(s) to search for candidate reports")
    args = ap.parse_args(argv)

    wb = Path(args.workbook)
    if not wb.exists():
        print(f"ERROR: workbook not found: {wb}", file=sys.stderr)
        return 2

    settings = load_settings()
    settings.ensure_dirs()
    db = DatabaseManager(settings.db_path)
    res = Orchestrator(db, settings).run(str(wb), extra_report_dirs=args.extra_report_dir)

    print(f"Run:        {res.run_id}")
    print(f"Final:      {res.final_state}")
    print(f"Iterations: {res.iterations}")
    print(f"Gates:      {res.gate_summary}")
    print(f"Folder:     {res.run_folder}")
    print("Exports:")
    for e in res.exports:
        print(f"  - {e}")
    # Exit non-zero only on hard error state, not on a clean ESCALATE.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
