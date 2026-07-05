#!/usr/bin/env python3
"""DataBossX Title Report Engine v2 -- command-line orchestrator.

Run against the folder where the real title files live::

    python app.py --root "D:\\Desktop\\Horizon" --section "31-12N-24W"

The engine discovers and ranks source workbooks, picks the controlling runsheet
and the formatting template, parses evidence, matches OGLs, chains ownership per
tract, verifies, and exports the final XLSX + audit log + source ranking.

It never fabricates title data. Where ownership cannot be proven it preserves the
best-supported figure, marks it "Needs Verification", highlights the cell yellow,
and explains the gap in the Audit Log.

Deliverables (paths follow the mission spec when --root is D:\\Desktop\\Horizon;
otherwise they land under the engine's own logs/output and the --root folder):
  * <root>/SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx
  * logs/SECTION31_AUDIT_LOG.xlsx
  * logs/SOURCE_FILE_RANKING.xlsx
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import ingest, parser as ev_parser, ogl_matcher, chain, verifier, writer  # noqa: E402
from engine.audit import AuditLog  # noqa: E402
from engine.models import EvidenceRow, Tract  # noqa: E402

FINAL_NAME = "SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx"
AUDIT_NAME = "SECTION31_AUDIT_LOG.xlsx"
RANKING_NAME = "SOURCE_FILE_RANKING.xlsx"


def _now_iso(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    try:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    except Exception:  # noqa: BLE001
        return "1970-01-01 00:00:00Z"


def _group_tracts(evidence: List[EvidenceRow]) -> List[Tract]:
    """Group evidence into tracts; infer gross acreage from the runsheet rows."""
    by_tract = defaultdict(list)
    for ev in evidence:
        by_tract[ev.tract or "Tract 1"].append(ev)

    tracts: List[Tract] = []
    for name in sorted(by_tract, key=_tract_sort_key):
        rows = by_tract[name]
        gross = None
        legal = ""
        for ev in rows:
            if ev.gross_acres is not None and gross is None:
                gross = ev.gross_acres
            if ev.legal_description and not legal:
                legal = ev.legal_description
        tracts.append(Tract(name=name, gross_acres=gross, legal_description=legal,
                            evidence=rows))
    return tracts


def _tract_sort_key(name: str):
    import re
    m = re.search(r"(\d+)", name or "")
    return (int(m.group(1)) if m else 9999, name)


def run(root: Path, section: str, out_final: Path, now_iso: str,
        copy_inputs: bool = True) -> dict:
    audit = AuditLog(now_iso)
    logs_dir = HERE / "logs"
    input_dir = HERE / "data" / "input"
    template_dir = HERE / "data" / "template"
    output_dir = HERE / "data" / "output"
    for d in (logs_dir, input_dir, template_dir, output_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Discover + rank -----------------------------------------------------
    # Exclude the engine's own working folders so we never re-ingest copied
    # inputs or a prior output when this package sits inside the scanned root.
    exclude = [input_dir, output_dir, template_dir, HERE / "archive", logs_dir,
               HERE / "demo"]
    # Never exclude a folder that the caller explicitly pointed --root at (or into).
    root_res = root.resolve()
    exclude = [d for d in exclude
               if not (root_res == d.resolve() or ingest._is_under(root_res, d.resolve()))]
    candidates = ingest.discover(root, exclude_dirs=exclude)
    selection = ingest.select_sources(candidates)
    writer.write_ranking_workbook(candidates, selection, logs_dir / RANKING_NAME)

    if copy_inputs:
        for c in candidates:
            try:
                shutil.copy2(c.path, input_dir / c.path.name)
            except (OSError, shutil.SameFileError):
                pass

    template_path = None
    if selection.template is not None:
        template_path = template_dir / "template.xlsx"
        try:
            shutil.copy2(selection.template.path, template_path)
        except (OSError, shutil.SameFileError):
            template_path = selection.template.path

    # 2. Parse evidence ------------------------------------------------------
    evidence: List[EvidenceRow] = []
    ogl_rows: List[EvidenceRow] = []
    if selection.runsheet is not None:
        evidence.extend(ev_parser.parse_candidate(selection.runsheet))
        audit.record("INGEST runsheet", source_sheet=selection.runsheet.name,
                     after=f"{len(evidence)} evidence rows",
                     evidence=f"controlling runsheet: {selection.runsheet.path}")
    # Prior report tract sheets are parsed but NOT trusted unless runsheet-backed.
    if selection.prior_report is not None and selection.prior_report is not selection.runsheet:
        prior = ev_parser.parse_candidate(selection.prior_report)
        audit.record("INGEST prior report (untrusted)",
                     source_sheet=selection.prior_report.name,
                     after=f"{len(prior)} rows read for corroboration only",
                     evidence="prior tract sheets are not trusted unless runsheet-backed (rule #5)")

    ogl_cand = selection.ogl
    if ogl_cand is not None:
        for sheet in ogl_cand.sheets:
            if sheet.is_ogl:
                grid = ev_parser.read_grid(ogl_cand.path, sheet.title)
                ogl_rows.extend(ev_parser.parse_sheet(grid, sheet))

    # 3. OGL matching --------------------------------------------------------
    ogl_index = ogl_matcher.build_ogl_index(ogl_rows)
    unmatched = ogl_matcher.match_leases(evidence, ogl_index, audit)

    # 4. Chain per tract -----------------------------------------------------
    tracts = _group_tracts(evidence)
    for t in tracts:
        chain.chain_tract(t, audit)
        verifier.verify_tract(t, audit)

    # 5. Export --------------------------------------------------------------
    writer.write_report(tracts, audit, out_final, template=template_path, section=section)
    writer.write_audit_workbook(audit, logs_dir / AUDIT_NAME)
    # keep a copy of the final report in the engine output folder too
    try:
        shutil.copy2(out_final, output_dir / FINAL_NAME)
    except (OSError, shutil.SameFileError):
        pass

    # 6. Validate ------------------------------------------------------------
    failures = verifier.validate_export(out_final, tracts)

    owner_count = sum(len(t.owners) for t in tracts)
    flag_count = sum(len(t.flags) for t in tracts)
    return {
        "candidates": candidates,
        "selection": selection,
        "tracts": tracts,
        "owner_count": owner_count,
        "flag_count": flag_count,
        "unmatched_ogl": unmatched,
        "failures": failures,
        "out_final": out_final,
        "audit_path": logs_dir / AUDIT_NAME,
        "ranking_path": logs_dir / RANKING_NAME,
        "template_used": template_path,
    }


def _print_summary(result: dict, root: Path) -> None:
    sel = result["selection"]
    line = "=" * 68
    print("\n" + line)
    print(" DataBossX Title Report Engine v2 — RUN SUMMARY")
    print(line)
    print(f" Root scanned        : {root}")
    print(f" Candidates found    : {len(result['candidates'])}")
    print(f" Best template       : {sel.template.name if sel.template else '(none — minimal Overview created)'}")
    print(f" Best runsheet       : {sel.runsheet.name if sel.runsheet else '(NONE FOUND — no controlling source)'}")
    print(f" Best prior report   : {sel.prior_report.name if sel.prior_report else '(none)'}")
    print(f" OGL sheet source    : {sel.ogl.name if sel.ogl else '(none)'}")
    print(f" Tract count         : {len(result['tracts'])}")
    print(f" Owner count         : {result['owner_count']}")
    print(f" Review flags        : {result['flag_count']}  (unmatched OGL: {result['unmatched_ogl']})")
    for t in result["tracts"]:
        bal = "balanced" if not any(f.category in ("unbalanced_tract", "ambiguous_acreage") for f in t.flags) else "NEEDS VERIFICATION"
        print(f"     - {t.name}: {len(t.owners)} owner(s), {t.owned_acres} ac, "
              f"evidence score {t.evidence_score}/100 [{bal}]")
    print(f" Output report       : {result['out_final']}")
    print(f" Audit log           : {result['audit_path']}")
    print(f" Source ranking      : {result['ranking_path']}")
    print(" Unresolved issues   :")
    if result["failures"]:
        for f in result["failures"]:
            print(f"     [VALIDATION] {f}")
    unresolved = [f for t in result["tracts"] for f in t.flags]
    if not unresolved and not result["failures"]:
        print("     (none — all tracts balanced and validated)")
    else:
        for f in unresolved[:25]:
            print(f"     [{f.severity}] {f.tract or '-'}: {f.category} — {f.message}")
        if len(unresolved) > 25:
            print(f"     ... and {len(unresolved) - 25} more (see Review Flags sheet)")
    if not result["candidates"]:
        print("\n NOTE: no source workbooks were found under the scanned root.")
        print("       Point --root at the folder that holds the runsheet/template/OGL")
        print("       files (e.g. D:\\Desktop\\Horizon) and rerun.")
    print(line + "\n")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="DataBossX Title Report Engine v2")
    ap.add_argument("--root", default=str(HERE / "data" / "input"),
                    help="Folder to scan for source files (e.g. D:\\Desktop\\Horizon)")
    ap.add_argument("--section", default="31-12N-24W",
                    help="Section-Township-Range label for the report")
    ap.add_argument("--output", default=None,
                    help="Explicit path for the final XLSX (defaults to <root>/" + FINAL_NAME + ")")
    ap.add_argument("--now", default=None, help="Override run timestamp (ISO); for reproducible tests")
    ap.add_argument("--no-copy-inputs", action="store_true",
                    help="Do not copy discovered source files into data/input")
    args = ap.parse_args(argv)

    root = Path(args.root).expanduser()
    out_final = Path(args.output).expanduser() if args.output else (root / FINAL_NAME)
    now_iso = _now_iso(args.now)

    result = run(root, args.section, out_final, now_iso,
                 copy_inputs=not args.no_copy_inputs)
    _print_summary(result, root)
    return 0 if not result["failures"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
