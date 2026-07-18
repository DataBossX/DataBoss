"""DataBossX command-line interface -- the one door a non-programmer uses.

    databossx doctor                     self-check the installation
    databossx list                       show registered projects + their roots
    databossx demo                       build + run the synthetic golden project
    databossx run --project horizon      run the full slice for a project
    databossx calc --wi 1 --royalty 1/8  ad-hoc working-interest / NRI math

Errors are reported in plain language with a suggested fix, never a raw
traceback, so the tool is hard to misuse.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__


def _cmd_doctor(_args) -> int:
    from .selfcheck import format_report, run_doctor
    report = run_doctor()
    print(format_report(report))
    return 0 if report.ok else 1


def _cmd_list(_args) -> int:
    from .projects import all_projects, resolve_root
    print("Registered DataBossX projects:\n")
    for p in all_projects():
        root = resolve_root(p.key)
        exists = "found" if root and Path(root).exists() else "not on this machine"
        print(f"  {p.key:<14} {p.name}")
        if p.section:
            print(f"  {'':<14}   section: {p.section}")
        print(f"  {'':<14}   root:    {root}  ({exists})")
        if p.description:
            print(f"  {'':<14}   {p.description}")
        print()
    print("Override any root with --root, or set DATABOSSX_<KEY>_ROOT.")
    return 0


def _print_run_result(result) -> None:
    print("\n" + "=" * 66)
    print("DataBossX -- run summary")
    print("=" * 66)
    print(f"Project:      {result.project}")
    print(f"Status:       {result.rag}")
    print(f"Source root:  {result.source_root}")
    print(f"Output:       {result.output_dir}")
    if result.counts:
        print("\nCounts:")
        for k, v in result.counts.items():
            print(f"  {k:<22} {v}")
    if result.deliverables:
        print("\nDeliverables:")
        for k, v in result.deliverables.items():
            print(f"  {k:<12} {v}")
    if result.defects:
        print(f"\n{len(result.defects)} defect(s) to review before release "
              "(see Defects sheet / dashboard).")
    if result.warnings:
        print("\nWarnings:")
        for w in result.warnings:
            print(f"  - {w}")
    if result.errors:
        print("\nErrors:")
        for e in result.errors:
            print(f"  - {e}")
    print("\n" + result.message)
    print("Reminder: unreviewed output is DRAFT -- a human release gate is required.")


def _cmd_run(args) -> int:
    from .command_center import run_project
    result = run_project(args.project, root=args.root, output_dir=args.output,
                         make_pdf=not args.no_pdf, base=args.base,
                         record_audit=args.audit, template=args.template)
    _print_run_result(result)
    return 0 if result.ok else 1


def _cmd_demo(args) -> int:
    from .command_center import run_project
    from .demo import build_golden_demo
    from .projects import golden_demo_root

    dest = golden_demo_root()
    workbook = build_golden_demo(dest)
    print(f"Synthetic golden project ready: {workbook.parent.parent}")
    out = args.output or str(dest / "databossx_output")
    result = run_project("golden_demo", output_dir=out, make_pdf=not args.no_pdf,
                         record_audit=args.audit)
    _print_run_result(result)
    return 0 if result.ok else 1


def _cmd_calc(args) -> int:
    from fractions import Fraction

    from .ownership import (
        mineral_net_acres,
        royalty_nri,
        working_interest_nri,
    )
    from horizon.interest import format_acres, format_fraction

    did = False
    if args.mineral and args.gross:
        nma = mineral_net_acres(args.mineral, args.gross)
        did = True
        if nma is None:
            print("Net mineral acres: could not parse --mineral/--gross.")
        else:
            print(f"Net mineral acres = {args.mineral} x {args.gross} = "
                  f"{format_acres(nma, 4)}  (exact {format_fraction(nma)})")
    if args.mineral and args.royalty and not args.wi:
        rn = royalty_nri(args.mineral, args.royalty)
        did = True
        if rn is not None:
            print(f"Royalty NRI = {args.mineral} x {args.royalty} = "
                  f"{format_acres(rn, 8)}  (exact {format_fraction(rn)})")
    if args.wi and args.royalty:
        nri = working_interest_nri(args.wi, args.royalty, args.orri or 0)
        did = True
        if nri is None:
            print("Working-interest NRI: could not parse inputs.")
        else:
            flag = "  *** NEGATIVE: burdens exceed 8/8 ***" if nri < 0 else ""
            orri_txt = f" - ORRI {args.orri}" if args.orri else ""
            print(f"Working-interest NRI = {args.wi} x (1 - {args.royalty}{orri_txt}) "
                  f"= {format_acres(nri, 8)}  (exact {format_fraction(nri)}){flag}")
    if not did:
        print("Nothing to compute. Examples:")
        print("  databossx calc --mineral 1/2 --gross 160")
        print("  databossx calc --wi 1 --royalty 1/8")
        print("  databossx calc --wi 1/2 --royalty 3/16 --orri 1/32")
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="databossx",
        description="DataBossX -- local-first land & title intelligence.")
    ap.add_argument("--version", action="version",
                    version=f"DataBossX {__version__}")
    sub = ap.add_subparsers(dest="command")

    sub.add_parser("doctor", help="self-check the installation").set_defaults(
        func=_cmd_doctor)
    sub.add_parser("list", help="list registered projects").set_defaults(
        func=_cmd_list)

    run = sub.add_parser("run", help="run the full slice for a project")
    run.add_argument("--project", required=True,
                     help="project key or name (see 'databossx list')")
    run.add_argument("--root", default=None, help="override the source folder")
    run.add_argument("--output", default=None, help="override the output folder")
    run.add_argument("--base", default=None, help="reserved: base working dir")
    run.add_argument("--no-pdf", action="store_true", help="skip the PDF report")
    run.add_argument("--audit", action="store_true",
                     help="also record the run in a durable SQLite audit store")
    run.add_argument("--template", default=None,
                     help="approved client workbook; also emit a template-faithful "
                          "report that preserves its structure and embedded plats")
    run.set_defaults(func=_cmd_run)

    demo = sub.add_parser("demo", help="build + run the synthetic golden project")
    demo.add_argument("--output", default=None, help="override the output folder")
    demo.add_argument("--no-pdf", action="store_true", help="skip the PDF report")
    demo.add_argument("--audit", action="store_true",
                      help="also record the run in a durable SQLite audit store")
    demo.set_defaults(func=_cmd_demo)

    calc = sub.add_parser("calc", help="ad-hoc mineral / WI / NRI math")
    calc.add_argument("--mineral", default=None, help="mineral interest, e.g. 1/2")
    calc.add_argument("--gross", default=None, help="gross acres, e.g. 160")
    calc.add_argument("--wi", default=None, help="working interest, e.g. 1")
    calc.add_argument("--royalty", default=None, help="royalty rate, e.g. 1/8")
    calc.add_argument("--orri", default=None, help="overriding royalty (optional)")
    calc.set_defaults(func=_cmd_calc)

    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as exc:  # last-resort plain-language guard
        print(f"\nUnexpected error: {exc}")
        print("Run 'databossx doctor' to check your installation, or re-run with "
              "a corrected --root/--project.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
