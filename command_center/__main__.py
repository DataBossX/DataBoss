"""Headless CLI for the command center — the pipeline without Streamlit.

Useful in CI, on a server, or when you just want the report:

    # run against the built-in synthetic sample
    python -m command_center --sample

    # run against a real OGL+runsheet workbook, write a highlighted report
    python -m command_center --workbook "31-12N-24W ... .xlsx" \
        --template template.xlsx --out REPORT_v001.xlsx --section 31-12N-24W
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import format_fraction
from .interest_fmt import fmt_acres
from .sample_data import ensure_sample_workspace
from .tasks import run_pipeline


def _print_event(evt) -> None:
    loop = f"L{evt.loop} " if evt.loop else "   "
    print(f"{loop}{evt.agent:<13} {evt.level:<9} {evt.message}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="command_center", description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--workbook", help="OGL+runsheet workbook (.xlsx)")
    src.add_argument("--sample", action="store_true", help="use the synthetic demo corpus")
    ap.add_argument("--template", help="report template (.xlsx) to write into")
    ap.add_argument("--out", help="output report path (.xlsx)")
    ap.add_argument("--section", default="31-12N-24W")
    ap.add_argument("--max-loops", type=int, default=5)
    ap.add_argument("--swarm", choices=["auto", "off", "force"], default="auto")
    args = ap.parse_args(argv)

    template = args.template
    if args.sample:
        root = Path(args.out).parent if args.out else Path("command_center/sample")
        workbook, sample_tpl = ensure_sample_workspace(root)
        template = template or str(sample_tpl)
        out = args.out or str(Path(root) / f"{args.section.replace('/', '-')}_REPORT_v001.xlsx")
    else:
        workbook = args.workbook
        out = args.out

    outcome = run_pipeline(
        workbook, section=args.section, out_path=out, template=template,
        max_loops=args.max_loops, use_swarm=args.swarm, sink=_print_event,
    )

    r = outcome.result
    print("\n" + "═" * 68)
    print(f"SECTION {r.section}  ·  mode={outcome.mode}  ·  "
          f"converged={r.converged} in {r.loops_run} loop(s)")
    for b in r.balances:
        print(f"  [{b.status:11}] {b.tract_legal or b.tract:24} "
              f"Σwi={format_fraction(b.outstanding_sum):>5} "
              f"net={fmt_acres(b.net_acres_sum)}/{fmt_acres(b.gross_acres)} ac"
              + (f"  ASSUMED: {'; '.join(b.assumptions)}" if b.assumptions else "")
              + (f"  REVIEW: {'; '.join(b.reasons)}" if b.reasons else ""))
    if outcome.report_path:
        print(f"\nReport: {outcome.report_path}  "
              f"({len(r.assumed_cells)} ASSUMED cells highlighted yellow)")
    print("═" * 68)
    # Non-zero exit if anything needs a human — handy for CI gating.
    return 0 if r.tracts_escalated == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
