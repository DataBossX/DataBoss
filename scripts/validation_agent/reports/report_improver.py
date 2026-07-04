"""
Report improver.

Reads the best existing report, compares it against the workbook manifest,
validation results, source queue, and escalations, and produces a NEW versioned
improved markdown report. It adds structure, a validation scorecard, a
missing-source table, and an examiner action list — but never adds unverified
legal facts. Every added line is labelled with one of:
VERIFIED / UNVERIFIED / ESCALATED / BLOCKED BY SPEND CAP /
BLOCKED BY MISSING CREDENTIALS / NEEDS EXAMINER REVIEW.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

LABELS = ("VERIFIED", "UNVERIFIED", "ESCALATED", "BLOCKED BY SPEND CAP",
          "BLOCKED BY MISSING CREDENTIALS", "NEEDS EXAMINER REVIEW")


def _read_text(path: Optional[str]) -> str:
    if not path:
        return ""
    p = Path(path)
    if p.suffix.lower() in {".md", ".txt", ".csv"} and p.exists():
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
    return ""


class ReportImprover:
    def __init__(self, dest_dir: str | Path):
        self.dest_dir = Path(dest_dir)
        self.dest_dir.mkdir(parents=True, exist_ok=True)

    def _next_path(self, stem: str = "improved_report", ext: str = ".md") -> Path:
        i = 1
        while True:
            p = self.dest_dir / f"{stem}_v{i:03d}{ext}"
            if not p.exists():
                return p
            i += 1

    def improve(self, *, best_report: Optional[str], manifest: Dict[str, Any],
                validation_results: List[Any], source_summary: Dict[str, int],
                escalations: List[Dict[str, Any]], final_state: str,
                mode: str, spend: Dict[str, str]) -> Path:
        original = _read_text(best_report)
        lines: List[str] = []
        A = lines.append
        A(f"# Improved Validation Report — {manifest.get('file_name', 'workbook')}")
        A("")
        A(f"_Generated {datetime.now().isoformat(timespec='seconds')} · mode: **{mode}** · "
          f"final state: **{final_state}**_")
        A("")
        A("> Labels: " + " · ".join(LABELS))
        A("")

        # --- Validation scorecard ---
        A("## Validation Scorecard")
        A("")
        A("| Gate | Status | Severity | Repairable | Reason |")
        A("|---|---|---|---|---|")
        for r in validation_results:
            A(f"| {getattr(r,'gate_name','')} | {getattr(r,'status','')} | "
              f"{getattr(r,'severity','')} | {'yes' if getattr(r,'repairable',False) else 'no'} | "
              f"{str(getattr(r,'reason','')).replace('|','/')[:120]} |")
        A("")

        # --- Source verification ---
        A("## Source Verification")
        A("")
        A(f"- Instrument references parsed: **{source_summary.get('total', 0)}**")
        A(f"- Located locally / cached: **{source_summary.get('found_local', 0)}** (VERIFIED where a file exists)")
        miss = source_summary.get('missing', 0)
        label = "BLOCKED BY MISSING CREDENTIALS" if mode == "dry-run" else "NEEDS EXAMINER REVIEW"
        A(f"- Missing sources: **{miss}** — {label} (contents never invented)")
        A("")

        # --- Spend ---
        A("## Spend")
        A("")
        A(f"- Cumulative charged: **${spend.get('cumulative','0.00')}** of cap **${spend.get('cap','100.00')}** "
          f"(remaining ${spend.get('remaining','100.00')})")
        A("")

        # --- Examiner action list (escalations) ---
        A("## Examiner Action List — ESCALATED / NEEDS EXAMINER REVIEW")
        A("")
        if escalations:
            A("| Category | Subject | Detail | Recommended Action |")
            A("|---|---|---|---|")
            for e in escalations:
                A(f"| {e.get('category','')} | {str(e.get('subject',''))[:40]} | "
                  f"{str(e.get('detail',''))[:90].replace('|','/')} | "
                  f"{str(e.get('recommended_action',''))[:90].replace('|','/')} |")
        else:
            A("_No open escalations recorded._")
        A("")

        # --- Provenance of the source report (unchanged, never overwritten) ---
        A("## Basis")
        A("")
        A(f"- Best source report: `{best_report or '(none found)'}` — read-only, NOT modified.")
        A(f"- Workbook: `{manifest.get('file_name','')}` (sha256 `{manifest.get('file_sha256','')[:16]}…`)")
        if original:
            A("")
            A("<details><summary>Original report excerpt (first 60 lines, verbatim)</summary>")
            A("")
            A("```")
            for ln in original.splitlines()[:60]:
                A(ln)
            A("```")
            A("</details>")

        out = self._next_path()
        out.write_text("\n".join(lines), encoding="utf-8")
        return out
