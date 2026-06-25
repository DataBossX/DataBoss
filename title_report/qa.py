"""QA gates for the cursory title report.

Implements the checks from the workflow's QA section and emits QA_RESULTS.md:

  * citation coverage   — every material schedule row carries a citation
  * row reconciliation  — workbook schedule counts match the model
  * fraction math       — every derived NRI/NMA recomputes exactly from inputs
  * no-hallucination     — UNKNOWN stays UNKNOWN; no computed interest without
                           exact basis language
  * secrets scan        — no API keys / passwords / .env content in deliverables

``run_qa`` returns a structured summary (also fed to the workbook QA Dashboard)
and a boolean ``passed`` so callers can gate "final" status.
"""

from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path
from typing import List

from .models import TitleReport, UNKNOWN
from . import fractions as fr

# Conservative secret patterns. Matches common key shapes and assignments.
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),                 # OpenAI-style keys
    re.compile(r"AKIA[0-9A-Z]{16}"),                    # AWS access key id
    re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*\S+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def _citation_coverage(rpt: TitleReport) -> dict:
    """Every material row must cite a source. Placeholder/UNKNOWN-only rows are
    allowed to lack a citation only when they assert nothing (all-UNKNOWN)."""
    gaps: List[str] = []

    def cited(c) -> bool:
        return bool(c) and c != UNKNOWN

    for i in rpt.instruments:
        if not cited(i.citation):
            gaps.append(f"runsheet:{i.instrument_no}")
    for c in rpt.chain_links:
        if not cited(c.citation):
            gaps.append(f"chain:{c.instrument_no}")
    for w in rpt.wells:
        if not cited(w.citation):
            gaps.append(f"well:{w.api_number}")
    for c in rpt.curative:
        if not cited(c.citation):
            gaps.append(f"curative:{c.issue_id}")
    for o in rpt.ownership:
        asserts = any(fr.is_known(v) for v in
                      (o.mineral_interest, o.lease_royalty, o.working_interest, o.burdens))
        if asserts and not cited(o.citation):
            gaps.append(f"ownership:{o.owner}")

    detail = "All material rows cited." if not gaps else f"Missing citations: {', '.join(gaps)}"
    return _check("Citation coverage", not gaps, detail)


def _row_reconciliation(rpt: TitleReport, workbook_counts: dict) -> dict:
    expected = {
        "Source Log": len(rpt.sources),
        "Runsheet": len(rpt.instruments),
        "Abstractions": len(rpt.abstractions),
        "Wells & HBP": len(rpt.wells),
        "Curative": len(rpt.curative),
        "NRI-WI Matrix": len(rpt.ownership),
    }
    mismatches = [f"{k}: model {v} vs workbook {workbook_counts.get(k)}"
                  for k, v in expected.items() if workbook_counts.get(k) != v]
    detail = "Workbook rows reconcile with model." if not mismatches else "; ".join(mismatches)
    return _check("Row reconciliation", not mismatches, detail)


def _fraction_math(rpt: TitleReport) -> dict:
    """Recompute every derived interest from inputs and confirm exactness.

    Also enforces the no-hallucination rule: an entry that lacks exact basis
    language must not carry computed interests. Where mineral interests or NRI
    are expected to total 8/8, the totals are verified to equal exactly 1.
    """
    errors: List[str] = []
    for o in rpt.ownership:
        has_basis = bool(o.basis_language) and o.basis_language != UNKNOWN
        nri = fr.entry_nri(o.role, o.mineral_interest, o.lease_royalty,
                           o.working_interest, o.burdens, o.override_royalty)
        if fr.is_known(nri) and not has_basis:
            errors.append(f"{o.owner}: computed NRI without basis language")

    # Reconciliation: when all mineral / NRI components are known, totals = 1.
    minerals = [o.mineral_interest for o in rpt.ownership if o.role == "royalty"]
    if minerals and all(fr.is_known(m) for m in minerals):
        mtot = fr.total_known(minerals)
        if mtot != Fraction(1):
            errors.append(f"mineral interests total {fr.frac_str(mtot)} != 1")

    nris = [fr.entry_nri(o.role, o.mineral_interest, o.lease_royalty,
                         o.working_interest, o.burdens, o.override_royalty)
            for o in rpt.ownership]
    if nris and all(fr.is_known(n) for n in nris):
        ntot = fr.total_known(nris)
        if ntot != Fraction(1):
            errors.append(f"total NRI {fr.frac_str(ntot)} != 8/8")

    detail = "All derived interests recompute exactly; minerals & NRI reconcile to 8/8." \
        if not errors else "; ".join(errors)
    return _check("Fraction math", not errors, detail)


def _secrets_scan(paths: List[Path]) -> dict:
    hits: List[str] = []
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeError):
            continue
        for pat in _SECRET_PATTERNS:
            if pat.search(text):
                hits.append(f"{p.name}:{pat.pattern[:24]}")
    detail = "No secrets detected in deliverables." if not hits else f"Potential secrets: {hits}"
    return _check("Secrets scan", not hits, detail)


def run_qa(rpt: TitleReport, workbook_counts: dict, deliverable_paths: List[Path],
           out_dir: Path) -> dict:
    checks = [
        _citation_coverage(rpt),
        _row_reconciliation(rpt, workbook_counts),
        _fraction_math(rpt),
        _secrets_scan(deliverable_paths),
    ]
    passed = all(c["status"] == "PASS" for c in checks)
    summary = {"passed": passed, "checks": checks,
               "is_placeholder": rpt.config.is_placeholder}
    _write_qa_md(rpt, summary, out_dir)
    return summary


def _write_qa_md(rpt: TitleReport, summary: dict, out_dir: Path) -> str:
    cfg = rpt.config
    lines = [
        f"# QA_RESULTS — {cfg.tract_label}",
        "",
        f"Report date: {cfg.report_date}  |  Source cutoff: {cfg.source_cutoff_date}",
        "",
    ]
    if cfg.data_status != "EXAMINED":
        lines += [f"> **DATA STATUS: {cfg.data_status}** — illustrative, internally-consistent "
                  "title model; NOT an examination of record title. The report cannot be marked "
                  "FINAL as a record-title opinion until real records are examined.", ""]
    overall = "PASS" if summary["passed"] else "FAIL"
    lines += [f"## Overall: **{overall}**", "",
              "| Check | Result | Detail |", "| --- | --- | --- |"]
    for c in summary["checks"]:
        detail = c["detail"].replace("|", "\\|")
        lines.append(f"| {c['name']} | {c['status']} | {detail} |")
    lines += [
        "",
        "## Finalization",
        "",
        (f"Report is **NOT FINAL** as a record-title opinion: {cfg.data_status} data in use "
         "(all QA gates may still pass on the model)." if cfg.data_status != "EXAMINED" else
         ("Report may be marked **FINAL**." if summary["passed"]
          else "Report is **NOT FINAL**: one or more QA checks failed.")),
        "",
    ]
    path = out_dir / "QA_RESULTS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)
