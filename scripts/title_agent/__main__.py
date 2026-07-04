"""Command-line entrypoint for the Title Agent.

    python -m scripts.title_agent register <workbook.xlsx>   # seed version 1
    python -m scripts.title_agent run                        # drive the loop
    python -m scripts.title_agent status                     # print scorecard

The loop wires the real WorkbookGateSuite and SurgeonRepairer. A source probe
is attached only when an OKCounty API key is present; Gate 6 (execution) runs
only when LibreOffice is functional — otherwise it is skipped, never faked.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from .api.okcounty import BudgetManager, CurlClient, DocumentVerifier
from .core.config import config
from .core.loop import PerfectionLoop
from .core.memory import AuditLogger, SQLiteManager, VersionController
from .core.reporting import CertificationReporter
from .core.wiring import ColumnMap, OKCountySourceProbe, SurgeonRepairer, WorkbookGateSuite
from .excel.recalc import LibreOfficeEngine

ARTIFACT_KEY = "TitleReport"


def _manager() -> SQLiteManager:
    config.ensure_dirs()
    return SQLiteManager(config.DB_PATH)


def _column_map(args: argparse.Namespace) -> ColumnMap | None:
    """Load a ColumnMap from --column-map, else an auto-detected columnmap.json
    in the base dir, else None (built-in defaults)."""
    explicit = getattr(args, "column_map", None)
    if explicit:
        return ColumnMap.from_json(Path(explicit))
    default = config.BASE_DIR / "columnmap.json"
    if default.exists():
        print(f"(using column map {default})")
        return ColumnMap.from_json(default)
    return None


def _source_probe(mgr: SQLiteManager):
    """Attach a live probe only if an API key is configured."""
    if not os.getenv(config.OKCOUNTY_API_KEY_ENV, "").strip():
        return None
    audit = AuditLogger(mgr)
    return OKCountySourceProbe(
        CurlClient(mgr, audit), DocumentVerifier(), BudgetManager(mgr, audit)
    )


def cmd_register(args: argparse.Namespace) -> int:
    src = Path(args.workbook)
    if not src.exists():
        print(f"error: workbook not found: {src}", file=sys.stderr)
        return 2
    mgr = _manager()
    vc = VersionController(mgr)
    version = vc.mint_new_version(ARTIFACT_KEY, reason=f"register {src.name}")
    shutil.copy2(src, version.file_path)
    print(f"registered {src.name} as {version.version_label} -> {version.file_path}")
    return 0


def _print_coverage(report) -> None:  # type: ignore[no-untyped-def]
    print("Mapping coverage:")
    for item in report.items:
        mark = {"mapped": "ok", "columns_unresolved": "UNRESOLVED",
                "sheet_absent": "ABSENT"}.get(item.status, item.status)
        extra = ""
        if item.missing_columns:
            extra = f" missing={list(item.missing_columns)}"
        elif item.note:
            extra = f" ({item.note})"
        print(f"  [{mark:>10}] {item.gate} · {item.sheet} · rows={item.data_rows}{extra}")
    for wmsg in report.warnings:
        print(f"  warning: {wmsg}")
    for bmsg in report.blocking:
        print(f"  BLOCKING: {bmsg}")


def cmd_map(args: argparse.Namespace) -> int:
    mgr = _manager()
    vc = VersionController(mgr)
    latest = vc.get_latest_version(ARTIFACT_KEY)
    if latest is None:
        print("error: no workbook registered; run `register <workbook.xlsx>` first",
              file=sys.stderr)
        return 2
    report = WorkbookGateSuite(column_map=_column_map(args)).coverage(latest.file_path)
    _print_coverage(report)
    print(f"\ncoverage {'OK' if report.ok else 'INCOMPLETE'}")
    return 0 if report.ok else 1


def cmd_run(args: argparse.Namespace) -> int:
    mgr = _manager()
    vc = VersionController(mgr)
    latest = vc.get_latest_version(ARTIFACT_KEY)
    if latest is None:
        print("error: no workbook registered; run `register <workbook.xlsx>` first",
              file=sys.stderr)
        return 2
    recalc = LibreOfficeEngine()
    suite = WorkbookGateSuite(
        column_map=_column_map(args),
        source_probe=_source_probe(mgr),
        recalc_engine=recalc if recalc.conversion_works() else None,
    )
    # Preflight: never run the loop (and risk a false CERTIFIED) on a workbook
    # whose columns the suite cannot read. Force the operator to fix the mapping.
    coverage = suite.coverage(latest.file_path)
    if not coverage.ok and not args.force:
        _print_coverage(coverage)
        print("\nerror: mapping is incomplete — refusing to certify a workbook the "
              "agent cannot fully read. Fix the layout/ColumnMap, or re-run with "
              "--force to proceed anyway (gates with unread inputs will not run).",
              file=sys.stderr)
        return 2
    reporter = CertificationReporter(mgr)
    artifacts: dict[str, object] = {}

    def _on_certified(version) -> None:  # type: ignore[no-untyped-def]
        try:
            artifacts["result"] = reporter.generate(version)
        except Exception as exc:  # reporting must not crash a valid certification
            print(f"warning: could not write certification report: {exc}", file=sys.stderr)

    loop = PerfectionLoop(mgr, ARTIFACT_KEY, suite, SurgeonRepairer(),
                          versions=vc, on_certified=_on_certified)
    outcome = loop.run()
    print(f"state={outcome.state.value} iterations={outcome.iterations} "
          f"version={outcome.final_version.version_label if outcome.final_version else '—'}")
    for esc in outcome.escalations:
        print(f"  ESCALATION [{esc.category}] {esc.gate} — {esc.reference}")
    result = artifacts.get("result")
    if result is not None:
        print(f"  Certified workbook: {result.certified_workbook}")  # type: ignore[attr-defined]
        print(f"  Audit report:       {result.audit_report}")  # type: ignore[attr-defined]
    return 0 if outcome.certified else 1


def cmd_status(args: argparse.Namespace) -> int:
    from .frontend.dashboard_data import DashboardData

    sc = DashboardData(_manager(), ARTIFACT_KEY).scorecard()
    print(f"Prospect {sc.prospect_id} · {sc.section} · loop={sc.loop_state} · "
          f"certified={sc.certified}")
    print(f"Budget ${sc.budget.spent:.2f}/${sc.budget.cap:.2f} · "
          f"open escalations={sc.open_escalation_count}")
    for g in sc.gates:
        mark = "PASS" if g.passed else f"ATTENTION ({g.open_escalations})"
        print(f"  {g.gate}: {mark}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="title_agent", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    reg = sub.add_parser("register", help="seed version 1 from a workbook")
    reg.add_argument("workbook")
    reg.set_defaults(func=cmd_register)

    mp = sub.add_parser("map", help="preflight: show how columns map to the gates")
    mp.add_argument("--column-map", help="path to a JSON column-map override")
    mp.set_defaults(func=cmd_map)

    run = sub.add_parser("run", help="drive the perfection loop")
    run.add_argument("--force", action="store_true",
                     help="run even if mapping coverage is incomplete")
    run.add_argument("--column-map", help="path to a JSON column-map override")
    run.set_defaults(func=cmd_run)

    stat = sub.add_parser("status", help="print the scorecard")
    stat.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
