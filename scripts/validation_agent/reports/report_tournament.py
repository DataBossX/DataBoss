"""
Report tournament + batch builder.

For each source folder:
  1. Find the best candidate workbook report (prefers cursory/title/final .xlsx).
  2. Run a TOURNAMENT of improvement strategies (different OGL match thresholds,
     with tract-coverage filtering). Each produces a candidate improved workbook.
  3. Score each candidate (OGL numbers filled without conflicts + totals fixed −
     conflicts) and pick the winner.
  4. Write the winner to the output folder in template naming, plus a
     reconciliation report. Sources are never overwritten; nothing is invented.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from reports.title_ogl_reconciler import reconcile, ReconcileReport
from validators.wb_access import read_tract_blocks

WORKBOOK_EXTS = {".xlsx", ".xlsm"}
PREFER_TOKENS = ("cursory", "title", "final", "best", "turn")
# Tournament strategies: (label, match_threshold)
STRATEGIES = [("strict", 0.95), ("balanced", 0.90), ("recall", 0.86)]


@dataclass
class Candidate:
    strategy: str
    threshold: float
    path: str
    report: ReconcileReport
    score: float = 0.0
    foots: int = 0


@dataclass
class FolderResult:
    folder: str
    source_report: Optional[str]
    winner: Optional[Candidate]
    final_path: Optional[str]
    candidates: List[Candidate] = field(default_factory=list)
    note: str = ""


def find_best_report(folder: Path) -> Optional[Path]:
    cands = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in WORKBOOK_EXTS
             and not p.name.startswith("~$")]
    if not cands:
        return None

    def score(p: Path) -> tuple:
        n = p.name.lower()
        tok = sum(1 for t in PREFER_TOKENS if t in n)
        return (tok, p.stat().st_size, p.stat().st_mtime)
    cands.sort(key=score, reverse=True)
    return cands[0]


def _score_candidate(cand: Candidate) -> float:
    r = cand.report.summary()
    # reward fills + verifications + fixed totals; penalise conflicts heavily
    return (r["filled"] * 2.0 + r["verified"] * 1.0 + r["totals_fixed"] * 3.0
            - r["conflicts"] * 2.0 + cand.foots * 1.0)


def _count_footing(path: str) -> int:
    ok = 0
    for b in read_tract_blocks(path):
        if b["gross"] is None:
            continue
        diff = abs((b["owner_nma_sum"] or Decimal("0")) - b["gross"])
        if diff <= Decimal("0.05") or b["has_balance"]:
            ok += 1
    return ok


def run_tournament(source_report: str, work_dir: Path) -> List[Candidate]:
    work_dir.mkdir(parents=True, exist_ok=True)
    cands: List[Candidate] = []
    for label, thr in STRATEGIES:
        out = work_dir / f"candidate_{label}.xlsx"
        if out.exists():
            out.unlink()
        try:
            rep = reconcile(source_report, str(out), match_threshold=thr)
        except Exception:
            continue
        c = Candidate(label, thr, str(out), rep)
        c.foots = _count_footing(str(out))
        c.score = _score_candidate(c)
        cands.append(c)
    return cands


def pick_winner(cands: List[Candidate]) -> Optional[Candidate]:
    if not cands:
        return None
    # highest score; tie -> higher threshold (safer / fewer false fills)
    return sorted(cands, key=lambda c: (c.score, c.threshold), reverse=True)[0]


def build_for_folder(folder: str, out_dir: str, work_root: str) -> FolderResult:
    fp = Path(folder)
    res = FolderResult(folder=str(fp), source_report=None, winner=None, final_path=None)
    if not fp.exists():
        res.note = "folder not found"
        return res
    best = find_best_report(fp)
    if not best:
        res.note = "no workbook report found in folder"
        return res
    res.source_report = str(best)
    work = Path(work_root) / fp.name
    cands = run_tournament(str(best), work)
    res.candidates = cands
    winner = pick_winner(cands)
    if not winner:
        res.note = "tournament produced no candidate"
        return res
    res.winner = winner
    outp = Path(out_dir)
    outp.mkdir(parents=True, exist_ok=True)
    final = outp / f"{fp.name}_FINAL_Cursory_Title_Report.xlsx"
    i = 1
    while final.exists():
        final = outp / f"{fp.name}_FINAL_Cursory_Title_Report_{i:02d}.xlsx"
        i += 1
    shutil.copy2(winner.path, final)
    res.final_path = str(final)
    # write a reconciliation report next to it
    _write_recon_md(res, outp / f"{fp.name}_reconciliation.md")
    return res


def _write_recon_md(res: FolderResult, path: Path) -> None:
    w = res.winner
    lines = [f"# Reconciliation — {Path(res.folder).name}", "",
             f"- Source report: `{res.source_report}`",
             f"- Winning strategy: **{w.strategy}** (OGL match threshold {w.threshold})",
             f"- Final report: `{res.final_path}`", "",
             "## Candidates (tournament)", "",
             "| Strategy | Threshold | Filled | Verified | Conflicts | Totals fixed | Tracts foot | Score |",
             "|---|---|---|---|---|---|---|---|"]
    for c in res.candidates:
        s = c.report.summary()
        lines.append(f"| {c.strategy} | {c.threshold} | {s['filled']} | {s['verified']} | "
                     f"{s['conflicts']} | {s['totals_fixed']} | {c.foots} | {c.score} |")
    lines += ["", "## Winner details", ""]
    s = w.report.summary()
    lines.append(f"- OGL numbers filled from register: **{s['filled']}**")
    lines.append(f"- Existing OGL numbers verified: **{s['verified']}**")
    lines.append(f"- Conflicts flagged for examiner (NOT changed): **{s['conflicts']}**")
    lines.append(f"- Hard-coded totals converted to SUM: **{s['totals_fixed']}**")
    lines.append(f"- Owners with no OGL match (reported, not invented): **{s['unmatched']}**")
    if w.report.conflicts:
        lines += ["", "### Conflicts to review", "",
                  "| Tract | Owner | Existing OGL | Register match | Score |",
                  "|---|---|---|---|---|"]
        for c in w.report.conflicts:
            lines.append(f"| {c['tract']} | {c['owner']} | {c['existing_ogl']} | "
                         f"{c['ogl_match']} ({c['grantor']}) | {c['score']} |")
    path.write_text("\n".join(lines), encoding="utf-8")


def batch_build(input_dirs: List[str], out_dir: str, work_root: str) -> List[FolderResult]:
    return [build_for_folder(d, out_dir, work_root) for d in input_dirs]
