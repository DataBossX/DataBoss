"""End-to-end runner for a source folder such as D:/Desktop/Horizon.

    python -m validation_agent.run_horizon D:/Desktop/Horizon

Pipeline:
    1. Organize the folder  -- unzip everything, quarantine trash/duplicates,
       inventory, and discover every workbook (tools.organize_workspace).
    2. For each workbook     -- run the perfection loop (validate -> safe-repair
       -> recalc -> re-validate, up to the iteration cap) toward certification.
    3. Build the reports     -- a full title report (chained-out interest, OGL
       tie-out, legals, notes) plus the validation scorecard / certification /
       escalation packets.
    4. Collect everything    -- into <root>/rogermillsfinalreports/<workbook>/
       with a top-level index.

No title fact is fabricated: a workbook that cannot certify without inventing a
fact ends in an escalation packet, and the title report flags the gap.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .core.orchestrator import PerfectionLoopOrchestrator
from .core.run_manager import sha256_of
from .db.db_client import db
from .ingestion.manifest_builder import WorkbookManifestBuilder
from .models import Finding
from .reports.output_generator import OutputGenerator
from .reports.title_report import TitleReportGenerator
from .tools.organize_workspace import WorkspaceOrganizer


def _all_findings(outcome) -> list[Finding]:
    return [f for it in outcome.iterations for r in it.gate_results
            for f in r.findings]


def _unique_dir(out_dir: Path, stem: str, used: set[str]) -> Path:
    """A collision-free output folder name for a workbook stem within a batch."""
    name = stem or "workbook"
    candidate = name
    n = 1
    while candidate in used:
        candidate = f"{name}_{n}"
        n += 1
    used.add(candidate)
    return out_dir / candidate


def run_horizon(root: str | Path, out_dir: Optional[str | Path] = None,
                *, timestamp: Optional[str] = None) -> dict:
    root = Path(root).resolve()
    out_dir = Path(out_dir) if out_dir else root / "rogermillsfinalreports"
    out_dir.mkdir(parents=True, exist_ok=True)
    base_ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")

    org = WorkspaceOrganizer().run(root)
    db.init()

    orchestrator = PerfectionLoopOrchestrator()
    builder = WorkbookManifestBuilder()
    processed: list[dict] = []
    used_names: set[str] = set()

    for idx, wb in enumerate(org.workbooks):
        wb_path = Path(wb)
        ts = f"{base_ts}_{idx:03d}"
        # Whole body is guarded: one bad workbook must never abort the batch or
        # skip the index. Distinct output folder so same-stem workbooks (e.g.
        # 2019/RunSheet.xlsx and 2021/RunSheet.xlsx) never clobber each other.
        wb_out = _unique_dir(out_dir, wb_path.stem, used_names)
        try:
            outcome = orchestrator.run(wb_path, timestamp=ts)
            OutputGenerator().generate(outcome)
            findings = _all_findings(outcome)

            final_path = outcome.ctx.version_path(outcome.final_version)
            if not final_path.is_file():
                final_path = outcome.ctx.v0_path
            manifest = builder.build(outcome.run_id, outcome.final_version,
                                     final_path, sha256_of(final_path))

            wb_out.mkdir(parents=True, exist_ok=True)
            TitleReportGenerator().generate(manifest, wb_out, findings=findings,
                                            prospect=wb_path.stem)
            run_reports = outcome.ctx.run_folder / "reports"
            if run_reports.is_dir():
                shutil.copytree(run_reports, wb_out / "validation",
                                dirs_exist_ok=True)
            esc_dir = outcome.ctx.run_folder / "escalations"
            if esc_dir.is_dir() and any(esc_dir.iterdir()):
                shutil.copytree(esc_dir, wb_out / "escalations", dirs_exist_ok=True)
            cert = outcome.ctx.run_folder / "certification.md"
            if cert.is_file():
                shutil.copy2(cert, wb_out / "certification.md")

            processed.append({
                "workbook": str(wb_path),
                "run_id": outcome.run_id,
                "state": outcome.final_state,
                "certified": outcome.certified,
                "iterations": len(outcome.iterations),
                "escalations": len(outcome.escalations),
                "output": str(wb_out),
            })
        except Exception as exc:  # noqa: BLE001 -- isolate per-workbook failures
            processed.append({"workbook": str(wb_path), "error": str(exc)})

    _write_index(out_dir, root, org, processed)
    return {"organize": org.summary(), "processed": processed,
            "output_dir": str(out_dir)}


def _write_index(out_dir: Path, root: Path, org, processed: list[dict]) -> None:
    lines = [f"# Roger Mills Final Reports -- {root.name}", "",
             f"Source folder: `{root}`", "",
             "## Workspace", "",
             f"- Workbooks processed: {len(processed)}",
             f"- Zips extracted: {len(org.extracted_zips)}",
             f"- Duplicates quarantined: {len(org.duplicates)}",
             f"- Trash quarantined: {len(org.trash)}", "",
             "## Reports", ""]
    if not processed:
        lines.append("_No workbooks were found in the source folder._")
    for p in processed:
        if "error" in p:
            lines.append(f"- **{Path(p['workbook']).name}** -- ERROR: {p['error']}")
            continue
        status = "CERTIFIED" if p["certified"] else f"ESCALATED ({p['escalations']})"
        lines.append(f"- **{Path(p['workbook']).name}** -- {status} "
                     f"({p['iterations']} iter) -> `{Path(p['output']).name}/`")
    (out_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def selftest() -> int:
    """Build a synthetic workspace, run the whole pipeline, and verify outputs.

    Lets a user confirm the tool works on their machine (Python, dependencies,
    LibreOffice) before pointing it at real data -- no external files needed.
    """
    import tempfile
    from .tests.make_fixture import build_certifiable_workbook
    workspace = Path(tempfile.mkdtemp(prefix="dbx_selftest_")) / "workspace"
    workspace.mkdir(parents=True)
    build_certifiable_workbook(workspace / "demo_prospect.xlsx")

    summary = run_horizon(workspace, timestamp="00000000_000000")
    out = Path(summary["output_dir"])
    checks = [
        ("index written", (out / "index.md").is_file()),
        ("title report written",
         (out / "demo_prospect" / "title_report.md").is_file()),
        ("interest reconciles / certified",
         any(p.get("certified") for p in summary["processed"])),
    ]
    ok = all(v for _, v in checks)
    print("SELF-TEST", "PASSED" if ok else "FAILED")
    for name, v in checks:
        print(f"  [{'x' if v else ' '}] {name}")
    print(f"Demo reports written to: {out}")
    if not ok:
        print("Investigate the failing check above; the engine did not complete.")
    return 0 if ok else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Organize a folder and build Roger Mills title reports.")
    parser.add_argument("root", nargs="?", default=None,
                        help="Source folder, e.g. D:/Desktop/Horizon")
    parser.add_argument("--out", default=None,
                        help="Output folder (default <root>/rogermillsfinalreports)")
    parser.add_argument("--timestamp", default=None)
    parser.add_argument("--selftest", action="store_true",
                        help="Run a synthetic end-to-end check and exit.")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.root:
        parser.error("a source folder is required (or use --selftest)")
    if not Path(args.root).is_dir():
        parser.error(f"folder not found: {args.root}")
    summary = run_horizon(args.root, args.out, timestamp=args.timestamp)
    print(f"\nOrganized: {summary['organize']}")
    print(f"Output: {summary['output_dir']}")
    for p in summary["processed"]:
        if "error" in p:
            print(f"  {Path(p['workbook']).name}: ERROR {p['error']}")
        else:
            state = "CERTIFIED" if p["certified"] else "ESCALATED"
            print(f"  {Path(p['workbook']).name}: {state} -> {p['output']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
