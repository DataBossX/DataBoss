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
from .core.wiring import OKCountySourceProbe, SurgeonRepairer, WorkbookGateSuite
from .excel.recalc import LibreOfficeEngine

ARTIFACT_KEY = "TitleReport"


def _manager() -> SQLiteManager:
    config.ensure_dirs()
    return SQLiteManager(config.DB_PATH)


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


def cmd_run(args: argparse.Namespace) -> int:
    mgr = _manager()
    vc = VersionController(mgr)
    if vc.get_latest_version(ARTIFACT_KEY) is None:
        print("error: no workbook registered; run `register <workbook.xlsx>` first",
              file=sys.stderr)
        return 2
    recalc = LibreOfficeEngine()
    suite = WorkbookGateSuite(
        source_probe=_source_probe(mgr),
        recalc_engine=recalc if recalc.conversion_works() else None,
    )
    loop = PerfectionLoop(mgr, ARTIFACT_KEY, suite, SurgeonRepairer(), versions=vc)
    outcome = loop.run()
    print(f"state={outcome.state.value} iterations={outcome.iterations} "
          f"version={outcome.final_version.version_label if outcome.final_version else '—'}")
    for esc in outcome.escalations:
        print(f"  ESCALATION [{esc.category}] {esc.gate} — {esc.reference}")
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

    run = sub.add_parser("run", help="drive the perfection loop")
    run.set_defaults(func=cmd_run)

    stat = sub.add_parser("status", help="print the scorecard")
    stat.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
