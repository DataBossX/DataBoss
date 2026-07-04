"""CLI: finalize Roger Mills title reports across three folders.

Reads the .env at the Horizon root (API key / browser creds — never printed),
runs the tournament+loops finalizer with the validation-agent safety layer
(append-only audit + $100 spend guard, no silent paid calls, no fabrication),
and writes the best template-formatted finals into the output folder.

Example (Windows):
    python tools\\rogermills_finalize.py ^
        --horizon "D:\\Desktop\\Horizon" ^
        --output  "D:\\Desktop\\Horizon\\rogermillsfinalreports" ^
        --template "D:\\Desktop\\Horizon\\Roger Mills\\Template(30).xlsx"

Run with --dry-run first to see the tournament plan without writing anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from dotenv import load_dotenv

from db.db_client import DatabaseManager
from db.audit_logger import AuditLogger
from sources.spend_guard import SpendGuard
from config.settings import ABSOLUTE_API_CAP_USD
from reports.rogermills_finalizer import RogerMillsFinalizer, FinalizeConfig

DEFAULT_FOLDERS = ["Roger Mills", "Roger Mills 2", "Roger Mills 3"]


def _load_env(horizon_root: Path) -> dict:
    """Load .env from the Horizon root. Returns a redacted presence report."""
    env_path = horizon_root / ".env"
    loaded = load_dotenv(env_path) if env_path.exists() else False
    import os
    return {
        "env_found": bool(loaded),
        "okcounty_user": bool(os.getenv("OKCOUNTY_USERNAME")),
        "okcounty_pass": bool(os.getenv("OKCOUNTY_PASSWORD")),
        "api_base_url": bool(os.getenv("OKCOUNTY_API_BASE_URL")),
        "api_key": bool(os.getenv("OKCOUNTY_API_KEY") or os.getenv("API_KEY")),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Roger Mills report finalizer")
    ap.add_argument("--horizon", default=r"D:\Desktop\Horizon",
                    help="Horizon root containing the Roger Mills folders + .env")
    ap.add_argument("--output", default=None,
                    help="Output folder for finals "
                         "(default: <horizon>/rogermillsfinalreports)")
    ap.add_argument("--folders", nargs="*", default=DEFAULT_FOLDERS,
                    help="Folder names under Horizon to process")
    ap.add_argument("--template", default=None,
                    help="Template workbook used as the formatting authority")
    ap.add_argument("--tract-sheet", default=None)
    ap.add_argument("--title-sheet", default=None)
    ap.add_argument("--ogl-sheet", default=None)
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--loops", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true",
                    help="Plan only; write nothing.")
    args = ap.parse_args()

    horizon = Path(args.horizon)
    if not horizon.exists():
        print(f"BLOCKER: Horizon root not found: {horizon}", file=sys.stderr)
        print("This tool must run where the files live (your Windows machine).",
              file=sys.stderr)
        return 2

    env_report = _load_env(horizon)
    output = Path(args.output) if args.output else horizon / "rogermillsfinalreports"
    folders = [horizon / name for name in args.folders]
    template = Path(args.template) if args.template else None

    output.mkdir(parents=True, exist_ok=True)
    db = DatabaseManager(output / "_audit" / "rogermills_audit.db")
    audit = AuditLogger(output / "_audit" / "rogermills.log", db=db)
    guard = SpendGuard(db=db, run_id="rogermills", cap_usd=ABSOLUTE_API_CAP_USD)

    cfg = FinalizeConfig(
        horizon_root=horizon, output_dir=output, folders=folders,
        template_path=template, dry_run=args.dry_run,
        top_k=args.top_k, loops=args.loops, tract_sheet=args.tract_sheet,
        title_sheet=args.title_sheet, ogl_sheet=args.ogl_sheet,
    )

    print(f"Horizon: {horizon}")
    print(f"Output : {output}")
    print(f"Mode   : {'DRY-RUN' if args.dry_run else 'WRITE'}  "
          f"(spend cap ${guard.cap}, live source OFF unless configured)")
    print(f".env   : found={env_report['env_found']}  "
          f"okcounty_creds={env_report['okcounty_user'] and env_report['okcounty_pass']}  "
          f"api_key_present={env_report['api_key']}  (values never printed)")
    print("")

    finalizer = RogerMillsFinalizer(cfg, db=db, audit=audit, spend_guard=guard)
    summary = finalizer.run()
    db.close()

    print(json.dumps(summary, indent=2))
    print("")
    if summary["finals"]:
        print(f"Wrote {len(summary['finals'])} final report(s) to {output}")
    else:
        print("No finals written." + (" (dry-run)" if args.dry_run else ""))
    if summary["review_total"]:
        print(f"{summary['review_total']} item(s) need examiner review — see "
              f"REVIEW_*.md in the output folder. These are NOT auto-resolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
