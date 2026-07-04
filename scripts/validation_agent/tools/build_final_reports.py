"""
Batch "tournament" builder for cursory-title reports.

Scans one or more source folders, finds the best report in each, runs the OGL/
title reconciliation tournament, and writes the winning final reports (template
naming) plus per-folder reconciliation notes into an output folder.

Usage (Windows example):
  python tools/build_final_reports.py ^
      --input "D:\\Desktop\\Horizon\\Roger Mills" ^
      --input "D:\\Desktop\\Horizon\\Roger Mills 2" ^
      --input "D:\\Desktop\\Horizon\\Roger Mills 3" ^
      --out   "D:\\Desktop\\Horizon\\rogermillsfinalreports" ^
      --env   "D:\\Desktop\\Horizon\\.env"

The --env file (if present) is loaded so OKCounty credentials / API settings are
available; secrets are never printed. Live source retrieval still requires
DATABOSSX_LIVE_SOURCE=true and DATABOSSX_DRY_RUN=false in that .env.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DataBossX — batch tournament report builder")
    ap.add_argument("--input", action="append", required=True, help="Source folder (repeatable)")
    ap.add_argument("--out", required=True, help="Output folder for final reports")
    ap.add_argument("--env", default="", help="Path to a .env file to load (optional)")
    ap.add_argument("--work", default="", help="Scratch folder for candidates (optional)")
    args = ap.parse_args(argv)

    if args.env:
        envp = Path(args.env)
        if envp.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(envp)
                print(f"Loaded environment from {envp} (secrets not printed).")
            except Exception:
                print(f"WARNING: could not load {envp}; continuing without it.")
        else:
            print(f"WARNING: --env path not found: {envp}")

    from reports.report_tournament import batch_build

    work = args.work or str(Path(args.out) / "_work")
    results = batch_build(args.input, args.out, work)

    print("\n=== BATCH RESULT ===")
    ok = 0
    for r in results:
        name = Path(r.folder).name
        if r.final_path:
            ok += 1
            s = r.winner.report.summary()
            print(f"[OK]  {name}: -> {Path(r.final_path).name}  "
                  f"(strategy={r.winner.strategy}, filled={s['filled']}, verified={s['verified']}, "
                  f"conflicts={s['conflicts']}, totals_fixed={s['totals_fixed']})")
        else:
            print(f"[--]  {name}: {r.note}")
    print(f"\n{ok}/{len(results)} folder(s) produced a final report in: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
