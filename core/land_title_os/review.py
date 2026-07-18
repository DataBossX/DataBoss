"""Independent final-review roles (Moves #20/#49).

Three reviewers, each blind to the others' logic, each answering one
question. Only failures and disagreements surface — a clean pass produces
an empty report, not a pile of reassurance.

1. **Evidence reviewer** — is every conclusion supported, by strong enough
   sources, and human-verified where it matters?
2. **Math reviewer** — do interests and acreage reconcile exactly?
3. **Deliverable reviewer** — does the final structure match the approved
   template, with nothing extra and nothing missing?
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from . import qa_engine
from .evidence import EvidenceLedger
from .legal_desc import reconcile_acreage
from .manifest import ProjectManifest

WEAK_AUTHORITY = 7          # ai_extraction and below
LOW_CONFIDENCE = 0.5


@dataclass
class ReviewFinding:
    role: str                # evidence | math | deliverable
    severity: str            # critical | high | medium
    message: str
    recommendation: str = ""


# -- role 1: evidence ---------------------------------------------------------

def evidence_review(ledger: EvidenceLedger) -> list[ReviewFinding]:
    out: list[ReviewFinding] = []
    for c in ledger.conclusions.values():
        best = ledger.best_authority(c.conclusion_id)
        if best >= WEAK_AUTHORITY:
            out.append(ReviewFinding(
                "evidence", "critical",
                f"conclusion rests only on weak sources (best authority rank {best}): "
                f"{c.statement[:120]}",
                "Obtain a recorded instrument image, official index entry, or order "
                "before this conclusion enters a deliverable."))
        if c.verification_status != "human_verified" and c.kind in (
                "ownership", "working_interest"):
            out.append(ReviewFinding(
                "evidence", "high",
                f"{c.kind} conclusion not human-verified: {c.statement[:120]}",
                "Route through the needs-me queue for examiner sign-off."))
    for e in ledger.entries.values():
        low = [f"{axis}={v}" for axis, v in e.confidence.items() if v < LOW_CONFIDENCE]
        if low and e.verification_status == "unverified":
            out.append(ReviewFinding(
                "evidence", "medium",
                f"evidence {e.evidence_id} ({e.book_page or e.source_document}) has low "
                f"unverified confidence: {', '.join(low)}",
                "Re-extract with a different route or verify against the image."))
    return out


# -- role 2: math -------------------------------------------------------------

def math_review(sheets: dict[str, list[dict]], config: dict | None = None,
                tract_descriptions: list[str] | None = None,
                expected_section_acres: int = 640) -> list[ReviewFinding]:
    out: list[ReviewFinding] = []
    for f in qa_engine.run_standard_checks(sheets, config):
        out.append(ReviewFinding(
            "math", f.severity if f.severity in ("critical", "high") else "medium",
            f"[{f.rule}] {f.sheet}" + (f" row {f.row}" if f.row else "") + f": {f.message}",
            f.recommendation))
    if tract_descriptions:
        total, problems = reconcile_acreage(tract_descriptions, Fraction(expected_section_acres))
        for p in problems:
            out.append(ReviewFinding(
                "math", "critical" if total is not None else "high",
                f"acreage reconciliation: {p}",
                "Reconcile tract descriptions against the plat and source instruments; "
                "never force-balance."))
    return out


# -- role 3: deliverable ------------------------------------------------------

def deliverable_review(sheet_names: list[str], manifest: ProjectManifest) -> list[ReviewFinding]:
    out: list[ReviewFinding] = []
    expected = None
    for t in manifest.templates:
        if isinstance(t, dict) and t.get("sheets"):
            expected = list(t["sheets"])
            break
    if expected is None:
        out.append(ReviewFinding(
            "deliverable", "high",
            f"manifest {manifest.project_id} declares no template sheet list",
            "Add the approved template's sheet names to the manifest so structure "
            "can be locked."))
        return out
    for f in qa_engine.check_template_sheets(sheet_names, expected):
        out.append(ReviewFinding(
            "deliverable", "critical" if f.severity == "critical" else "high",
            f"[{f.rule}] {f.message}", f.recommendation))
    return out


# -- consolidated -------------------------------------------------------------

def run_reviews(project_dir: str | Path, sheets: dict[str, list[dict]] | None = None,
                qa_config: dict | None = None,
                tract_descriptions: list[str] | None = None) -> list[ReviewFinding]:
    """Run every applicable role for a project directory. Empty list = pass."""
    project_dir = Path(project_dir)
    findings: list[ReviewFinding] = []

    ledger_path = project_dir / "evidence.jsonl"
    if ledger_path.exists():
        findings += evidence_review(EvidenceLedger(ledger_path))

    if sheets is not None:
        findings += math_review(sheets, qa_config, tract_descriptions)
        manifest_path = project_dir / "manifest.json"
        if manifest_path.exists():
            findings += deliverable_review(list(sheets), ProjectManifest.load(manifest_path))

    order = {"critical": 0, "high": 1, "medium": 2}
    findings.sort(key=lambda f: (order.get(f.severity, 3), f.role))
    return findings


def render(findings: list[ReviewFinding]) -> str:
    if not findings:
        return "ALL REVIEWS PASS — no failures or disagreements to show."
    lines = [f"REVIEW FAILURES — {len(findings)} finding(s)", ""]
    for f in findings:
        lines.append(f"[{f.severity.upper():>8}] ({f.role}) {f.message}")
        if f.recommendation:
            lines.append(f"           -> {f.recommendation}")
    return "\n".join(lines)
