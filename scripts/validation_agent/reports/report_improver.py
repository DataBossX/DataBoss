"""Improve a prior title report without adding unverified legal facts.

Reads the best prior report, compares it against the manifest, validation
results, source index, and escalations, and produces a NEW versioned report
with improved formatting, a validation scorecard, source citation tables, a
missing-document list, and an examiner action matrix. Every fact carries an
explicit label; no unverified legal fact is ever introduced.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.enums import GateStatus
from core.hashing import sha256_file
from db.audit_logger import AuditLogger
from reports.output_generator import FACT_LABELS
from validators.base_validator import Escalation, ValidationResult


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


class ReportImprover:
    def __init__(self, audit: AuditLogger, run_id: str, reports_dir: Path) -> None:
        self.audit = audit
        self.run_id = run_id
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def _read_source(self, path: Optional[Path]) -> str:
        if not path or not Path(path).exists():
            return "_No prior report located; this is a newly generated report._"
        if Path(path).suffix.lower() in {".md", ".txt", ".csv"}:
            try:
                return Path(path).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                return "_Prior report could not be read._"
        return f"_Prior report `{Path(path).name}` located (binary format; not inlined)._"

    def _fact_label(self, result: ValidationResult) -> str:
        if result.status == GateStatus.PASS:
            return "VERIFIED"
        if result.status == GateStatus.ESCALATE:
            fc = result.failure_category.value if result.failure_category else ""
            if "Spend" in fc:
                return "BLOCKED BY SPEND CAP"
            if "Authentication" in fc:
                return "BLOCKED BY MISSING CREDENTIALS"
            return "ESCALATED"
        return "NEEDS EXAMINER REVIEW"

    def improve(
        self,
        prior_report: Optional[Path],
        results: List[ValidationResult],
        escalations: List[Escalation],
        source_index: Dict[str, Any],
        manifest: Dict[str, Any],
    ) -> Dict[str, str]:
        original = self._read_source(prior_report)
        wb = manifest.get("workbook", {})
        found = source_index.get("found", [])
        missing = source_index.get("missing", [])

        lines: List[str] = [
            "# DataBossX Improved Title Report",
            "",
            f"- Run ID: `{self.run_id}`",
            f"- Generated: {datetime.now(timezone.utc).isoformat()}",
            f"- Source report: `{Path(prior_report).name if prior_report else 'none'}`",
            f"- Workbook: `{wb.get('filename', 'n/a')}` (sha256 `{wb.get('sha256', '')[:16]}…`)",
            "",
            "> Every factual line is labelled. No unverified legal fact has been added.",
            "",
            "## Fact Label Legend",
            "",
        ]
        lines += [f"- **{label}**" for label in FACT_LABELS]

        lines += ["", "## Validation Scorecard", "",
                  "| Gate | Label | Status | Subject | Reason |",
                  "| --- | --- | --- | --- | --- |"]
        for r in results:
            lines.append(
                f"| {r.gate_name} | {self._fact_label(r)} | {r.status.value} | "
                f"{r.affected_subject or ''} | {(r.reason or '').replace('|', '/')} |"
            )

        lines += ["", "## Source Citation Table", "",
                  "| Reference | Type | Status | SHA-256 |",
                  "| --- | --- | --- | --- |"]
        for f in found:
            lines.append(
                f"| `{f.get('reference_key')}` | {f.get('reference_type')} | VERIFIED | "
                f"`{str(f.get('sha256',''))[:16]}…` |"
            )
        for m in missing:
            lines.append(
                f"| `{m.get('reference_key')}` | {m.get('reference_type')} | "
                f"NEEDS EXAMINER REVIEW | — |"
            )

        lines += ["", "## Missing Document List", ""]
        if missing:
            for m in missing:
                lines.append(f"- `{m.get('reference_key')}` — NEEDS EXAMINER REVIEW")
        else:
            lines.append("- None outstanding.")

        lines += ["", "## Examiner Action Matrix", "",
                  "| Urgency | Gate | Subject | Recommended Action |",
                  "| --- | --- | --- | --- |"]
        for e in escalations:
            lines.append(
                f"| {e.urgency.value} | {e.failed_gate} | {e.subject or ''} | "
                f"{(e.recommended_examiner_action or '').replace('|', '/')} |"
            )

        lines += ["", "---", "", "## Prior Report (preserved, unmodified)", "", original]

        body = "\n".join(lines) + "\n"
        out = self.reports_dir / f"improved_report_{_stamp()}.md"
        if out.exists():
            out = self.reports_dir / f"improved_report_{_stamp()}_v2.md"
        out.write_text(body, encoding="utf-8")
        sha = sha256_file(out)
        self.audit.log_report_export("improved_report", str(out), sha, run_id=self.run_id)
        return {"path": str(out), "sha256": sha}
