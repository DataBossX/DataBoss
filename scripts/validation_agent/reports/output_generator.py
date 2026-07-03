"""OutputGenerator -- final versioned deliverables.

Writes everything a human examiner needs into the run's immutable output folder:

    reports/scorecard.md        -- gate-by-gate pass/fail matrix (final iteration)
    reports/audit_report.md     -- exhaustive per-iteration narrative + spend
    reports/summary.json        -- machine-readable run summary
    certification.md            -- present ONLY when 100% of gates passed
    escalations/ESC-*.md        -- one packet per escalation (Section 7's 9 fields)

All writes are confined to the run folder (Golden Law #5); nothing outside
``outputs/`` is ever touched or overwritten.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from ..models import Escalation, GateStatus

if TYPE_CHECKING:
    from ..core.orchestrator import RunOutcome

_STATUS_ICON = {
    GateStatus.PASS: "PASS",
    GateStatus.FAIL: "FAIL",
    GateStatus.ERROR: "ERROR",
    GateStatus.SKIPPED: "SKIP",
}


class OutputGenerator:
    def generate(self, outcome: "RunOutcome") -> dict[str, str]:
        run_folder = outcome.ctx.run_folder
        reports_dir = run_folder / "reports"
        esc_dir = run_folder / "escalations"
        reports_dir.mkdir(parents=True, exist_ok=True)
        esc_dir.mkdir(parents=True, exist_ok=True)

        paths: dict[str, str] = {}
        paths["scorecard"] = self._write(reports_dir / "scorecard.md",
                                         self._scorecard_md(outcome))
        paths["audit_report"] = self._write(reports_dir / "audit_report.md",
                                            self._audit_md(outcome))
        paths["summary"] = self._write(reports_dir / "summary.json",
                                       json.dumps(self._summary(outcome), indent=2,
                                                  default=str))
        if outcome.certified:
            paths["certification"] = self._write(run_folder / "certification.md",
                                                 self._certification_md(outcome))
        else:
            written = []
            for idx, esc in enumerate(outcome.escalations, start=1):
                fp = esc_dir / f"ESC-{idx:03d}-{esc.category.value}.md"
                written.append(self._write(fp, self._escalation_md(esc, idx)))
            paths["escalations"] = json.dumps(written)
        return paths

    # -- scorecard ----------------------------------------------------------
    def _scorecard_md(self, outcome: "RunOutcome") -> str:
        last = outcome.latest()
        lines = [f"# Validation Scorecard -- {outcome.run_id}", ""]
        lines.append(f"- Final state: **{outcome.final_state}**")
        lines.append(f"- Certified: **{outcome.certified}**")
        lines.append(f"- Iterations run: **{len(outcome.iterations)}**")
        lines.append(f"- Final workbook version: **v{outcome.final_version}**")
        lines.append(f"- Cumulative API spend (ledger total, all runs): "
                     f"**${outcome.total_spend:.2f}** (hard cap $100.00)")
        lines.append("")
        lines.append("| Gate | Name | Status | Detail |")
        lines.append("|------|------|--------|--------|")
        if last:
            for r in sorted(last.gate_results, key=lambda g: g.gate_id):
                detail = r.detail.replace("|", "\\|")[:120]
                lines.append(f"| {r.gate_id} | {r.gate_name} | "
                             f"{_STATUS_ICON.get(r.status, r.status.value)} | {detail} |")
        gate13 = "PASS" if outcome.certified else "FAIL"
        lines.append(f"| 13 | Final Certification | {gate13} | "
                     f"{'100% of gates passed.' if outcome.certified else 'Not certified.'} |")
        lines.append("")
        return "\n".join(lines)

    # -- audit report -------------------------------------------------------
    def _audit_md(self, outcome: "RunOutcome") -> str:
        lines = [f"# Audit Report -- {outcome.run_id}", "",
                 f"Source: `{outcome.ctx.source_path}`",
                 f"Source SHA-256: `{outcome.ctx.source_sha256}`",
                 f"Run folder: `{outcome.ctx.run_folder}`", "",
                 f"Outcome: **{outcome.final_state}** -- {outcome.message}", ""]
        for rec in outcome.iterations:
            lines.append(f"## Iteration {rec.iteration} (v{rec.version}) "
                         f"-> {rec.decision}")
            for r in sorted(rec.gate_results, key=lambda g: g.gate_id):
                lines.append(f"- Gate {r.gate_id} {r.gate_name}: "
                             f"**{_STATUS_ICON.get(r.status, r.status.value)}** "
                             f"-- {r.detail}")
                for f in r.findings:
                    loc = f" @ {f.location}" if f.location else ""
                    lines.append(f"    - [{f.severity.value}] {f.message}{loc}")
            if rec.plan.safe_repairs:
                lines.append(f"  - Safe repairs applied: {len(rec.plan.safe_repairs)}")
                for a in rec.plan.safe_repairs:
                    lines.append(f"    - {a.location}: {a.action_type} -> "
                                 f"{a.new_formula}")
            if rec.plan.escalations:
                lines.append(f"  - Escalations raised: {len(rec.plan.escalations)}")
            lines.append("")
        return "\n".join(lines)

    # -- certification ------------------------------------------------------
    def _certification_md(self, outcome: "RunOutcome") -> str:
        return "\n".join([
            f"# CERTIFICATION -- {outcome.run_id}", "",
            "All quality gates (1-13) passed. This workbook version is certified "
            "by the automated validation agent, subject to human examiner approval "
            "of the risk (Golden Law #1).", "",
            f"- Certified workbook version: **v{outcome.final_version}**",
            f"- Path: `{outcome.ctx.version_path(outcome.final_version)}`",
            f"- Cumulative API spend (ledger total): **${outcome.total_spend:.2f}**",
            f"- Iterations to certification: **{len(outcome.iterations)}**", "",
            "No legal or title facts were fabricated in producing this result.",
        ])

    # -- escalation packet (Section 7) --------------------------------------
    def _escalation_md(self, esc: Escalation, idx: int) -> str:
        return "\n".join([
            f"# Escalation ESC-{idx:03d} -- {esc.category.value}", "",
            f"- **Severity**: {esc.severity.value}",
            f"- **Estimated urgency**: {esc.estimated_urgency}", "",
            "## Escalation Payload (mandatory fields)", "",
            f"1. **Failed Validation Gate**: {esc.failed_gate} (gate {esc.gate_id})",
            f"2. **Affected Workbook Location**: {esc.location or 'N/A'}",
            f"3. **Affected Subject**: {esc.subject}",
            f"4. **Source Documents Checked**: "
            f"{', '.join(esc.sources_checked) or 'None'}",
            f"5. **Source Documents Missing**: "
            f"{', '.join(esc.sources_missing) or 'None recorded'}",
            f"6. **Attempted Automated Checks**: "
            f"{'; '.join(esc.automated_checks_attempted) or 'None'}",
            f"7. **Reason Automated Repair Was Blocked**: {esc.repair_blocked_reason}",
            f"8. **Recommended Examiner Action**: {esc.recommended_examiner_action}",
            f"9. **Estimated Urgency**: {esc.estimated_urgency}", "",
            "> Automated repair was intentionally halted. The system does not "
            "fabricate legal or title facts (Golden Law #3/#4).",
        ])

    # -- machine summary ----------------------------------------------------
    def _summary(self, outcome: "RunOutcome") -> dict:
        last = outcome.latest()
        return {
            "run_id": outcome.run_id,
            "final_state": outcome.final_state,
            "certified": outcome.certified,
            "iterations": len(outcome.iterations),
            "final_version": outcome.final_version,
            "total_spend": outcome.total_spend,
            "message": outcome.message,
            "final_gate_results": [r.to_dict() for r in last.gate_results] if last else [],
            "escalations": [e.to_dict() for e in outcome.escalations],
        }

    @staticmethod
    def _write(path: Path, content: str) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)
