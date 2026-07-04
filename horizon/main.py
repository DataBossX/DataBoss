#!/usr/bin/env python3
"""Horizon Command Center -- entry point (mission section 5).

Scans the root, executes the foundation cleanup, then initiates the
report-improvement loop, logging every action to ``horizon_audit.log``.

Run it *on the machine where the files live*:

    py -m pip install -r horizon/requirements.txt
    py horizon/main.py --root "D:\\Desktop\\Horizon"

Or set ``HORIZON_ROOT`` and run ``py horizon/main.py``. Use ``--no-backup`` to
skip the snapshot copy, and ``--dry-run`` to scan/validate without writing new
versions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

# Support both ``python horizon/main.py`` and ``python -m horizon.main``.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from horizon.audit import AuditLog
    from horizon.config import HorizonConfig
    from horizon.foundation import run_cleanup
    from horizon.orchestrator import Orchestrator
    from horizon.pipeline import build_from_workbook, find_reference_workbook
    from horizon.report_io import read_report, write_report
    from horizon.validation import load_requirements
    from horizon.versioning import latest_version, next_version_path
else:
    from .audit import AuditLog
    from .config import HorizonConfig
    from .foundation import run_cleanup
    from .orchestrator import Orchestrator
    from .pipeline import build_from_workbook, find_reference_workbook
    from .report_io import read_report, write_report
    from .validation import load_requirements
    from .versioning import latest_version, next_version_path


def build_config(args: argparse.Namespace) -> HorizonConfig:
    cfg = HorizonConfig.from_env(args.root)
    if args.section:
        cfg.section = args.section
    if args.max_loops:
        cfg.max_loops = args.max_loops
    return cfg


def run(args: argparse.Namespace) -> int:
    cfg = build_config(args)
    if not cfg.root.exists():
        print(f"FATAL: root folder does not exist: {cfg.root}")
        print("Run Horizon on the machine where the title files actually live.")
        return 2

    cfg.ensure_workspace()
    audit = AuditLog(path=cfg.audit_log)
    audit.info("horizon_start", f"root={cfg.root} section={cfg.section}")

    # 1. Foundation cleanup: snapshot -> unzip -> scan -> SHA256 dedup.
    cleanup = run_cleanup(cfg, audit, backup=not args.no_backup)

    # 2. Requirements from the Golden Source of Truth.
    reqs = load_requirements(cfg.root / cfg.golden_source_name)
    audit.info("requirements", f"source={reqs.source} "
                               f"columns={len(reqs.required_columns)} "
                               f"required_instruments={len(reqs.required_instruments)}")

    # 3. Ingest the newest report iteration to perfect (if any exists yet).
    base_stem = args.base or f"{cfg.section}_Roger_Mills_Cursory_Title_Report"

    # 3a. Build an initial chained report from a reference workbook (the
    #     Intelligence Layer): read OGL + runsheet, reconcile, tag reviews.
    #     Explicit --build-from wins; otherwise auto-detect the best OGL+runsheet
    #     workbook among the scanned files so a single command "just works".
    wb_path = None
    if args.build_from:
        wb_path = Path(args.build_from)
        if not wb_path.exists():
            audit.error("build_from_missing", f"workbook not found: {wb_path}")
            wb_path = None
    elif latest_version(cfg.final_reports, base_stem) is None:
        candidates = [r.path for r in cleanup.kept] or [r.path for r in cleanup.scanned]
        wb_path = find_reference_workbook(candidates)
        if wb_path is not None:
            audit.info("reference_autodetect", f"selected {wb_path.name}")
        else:
            audit.warn("reference_autodetect",
                       "no OGL+runsheet workbook found among sources")

    if wb_path is not None:
        build = build_from_workbook(wb_path, section=cfg.section)
        audit.info("chain_build",
                   f"ogl_rows={len(build.report.rows)} "
                   f"chain_breaks={len(build.chain_breaks)} "
                   f"tracts_needing_review={len(build.tracts_reviewed)}")
        if not args.dry_run and build.report.rows:
            out = next_version_path(cfg.final_reports, base_stem)
            write_report(build.report, out)
            audit.info("chain_build_written", out.name)

    current = latest_version(cfg.final_reports, base_stem)
    if current is None:
        audit.escalate(
            "no_report",
            f"No versioned report found in {cfg.final_reports}. Place an initial "
            f"'{base_stem}_v001.xlsx' (or point --base at your report) to start "
            f"the improvement loop. Cleanup completed; not fabricating a report.",
        )
        _print_summary(cfg, cleanup, None)
        return 0

    if args.dry_run:
        audit.info("dry_run", "skipping improvement loop (scan/validate only)")
        _print_summary(cfg, cleanup, None)
        return 0

    # 4. Autonomous improvement loop.
    report = read_report(current, section=cfg.section)
    orch = Orchestrator(cfg, audit)
    result = orch.run(report, base_stem, reqs)
    audit.info("horizon_done",
               f"loops={result.loops_run} converged={result.converged} "
               f"exhausted={result.exhausted} "
               f"final={result.final_version.name if result.final_version else '(none)'}")
    _print_summary(cfg, cleanup, result)
    return 0 if result.converged else 1


def _print_summary(cfg, cleanup, result) -> None:
    print("\n" + "=" * 70)
    print("HORIZON COMMAND CENTER -- SUMMARY")
    print("=" * 70)
    print(f"Root:              {cfg.root}")
    print(f"Final reports dir: {cfg.final_reports}")
    print(f"Audit log:         {cfg.audit_log}")
    print(f"Files scanned:     {len(cleanup.scanned)}")
    print(f"Duplicates trashed:{len(cleanup.quarantined)} "
          f"(groups={cleanup.duplicate_groups})")
    if result is not None:
        print(f"Loops run:         {result.loops_run}")
        print(f"Converged:         {result.converged}")
        if result.final_version:
            print(f"Final version:     {result.final_version.name}")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Horizon Command Center")
    ap.add_argument("--root", default=None,
                    help="Horizon root (default: $HORIZON_ROOT or D:\\Desktop\\Horizon)")
    ap.add_argument("--section", default="31-12N-24W", help="Target section label")
    ap.add_argument("--base", default=None,
                    help="Base stem of the report to improve (without _vNNN)")
    ap.add_argument("--build-from", default=None,
                    help="Reference workbook to chain (OGL + runsheet sheets) "
                         "into an initial versioned report before the loop")
    ap.add_argument("--max-loops", type=int, default=0,
                    help="Override the improvement-loop cap (default 5)")
    ap.add_argument("--no-backup", action="store_true",
                    help="Skip the snapshot backup copy")
    ap.add_argument("--dry-run", action="store_true",
                    help="Scan + validate only; do not write new versions")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
