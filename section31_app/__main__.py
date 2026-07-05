"""CLI entry point: ``python -m section31_app --root "D:\\Desktop\\Horizon\\Roger Mills"``.

Runs the full pipeline headlessly (no Streamlit) -- handy for scheduled runs or
CI smoke tests. The Streamlit dashboard is launched separately via app.py.
"""

from __future__ import annotations

import argparse
import sys

from .config import Section31Config
from .env_utils import load_env
from .pipeline import run_pipeline


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Section 31 report pipeline")
    parser.add_argument("--root", help="Roger Mills folder root")
    parser.add_argument("--extra-root", action="append", default=[],
                        help="additional folder(s) to scan")
    parser.add_argument("--drive", action="store_true",
                        help="enable Google Drive fallback")
    parser.add_argument("--no-archive", action="store_true",
                        help="do not move non-final files into subfolders")
    args = parser.parse_args(argv)

    load_env()
    cfg = Section31Config.from_env(args.root)
    result = run_pipeline(cfg, extra_roots=args.extra_root, use_drive=args.drive,
                          do_archive=not args.no_archive)

    print(f"Verdict:        {result['verdict']}")
    print(f"Final workbook: {result['final_workbook']}")
    print(f"Base workbook:  {result['base']}")
    print(f"Owners:         {result['ownership_totals']['owners']}")
    print(f"Net min acres:  {result['ownership_totals']['total_net_mineral_acres']}")
    print(f"Wells:          {result['wells']}")
    print(f"Image spend:    ${result['spend']['spent_usd']:.2f} of "
          f"${result['spend']['cap_usd']:.2f}")
    print(f"Main folder clean (only final XLSX): {result['clean']}")
    return 0 if "NOT READY" not in result["verdict"] else 2


if __name__ == "__main__":
    sys.exit(main())
