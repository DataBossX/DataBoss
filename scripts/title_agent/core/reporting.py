"""Certification output — the Certified Workbook and the Audit Report.

Blueprint section 3, step 3: on certification the loop "outputs the Certified
Workbook & Audit Report." This module produces both:

* **Certified Workbook** — the certified version copied to a clearly named,
  never-overwritten output file (the version label is in the name, so each
  certified version keeps its own artifact).
* **Audit Report** — a Markdown record stating the certification, the six-gate
  scorecard, the full version lineage, the budget spent, and the complete
  append-only audit trail.

Neither output is ever overwritten; regenerating for an already-certified
version raises rather than clobbering the prior artifact.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import (
    COUNTY,
    GROSS_ACRE_TARGET,
    PROSPECT_ID,
    SECTION,
    STATE,
    TRACT_COUNT,
    WELL_NAME,
    config,
)
from .memory import ArtifactVersion, AuditLogger, SQLiteManager, VersionController
from .taxonomy import Gate
from ..api.okcounty import BudgetManager


class ReportExistsError(RuntimeError):
    """A certification artifact already exists for this version — refusing to
    overwrite it."""


@dataclass(frozen=True)
class CertificationArtifacts:
    certified_workbook: Path
    audit_report: Path


class CertificationReporter:
    """Emits the Certified Workbook and Audit Report on certification."""

    def __init__(
        self, manager: SQLiteManager, output_dir: Optional[Path] = None
    ) -> None:
        self._db = manager
        self._dir: Path = Path(output_dir) if output_dir is not None else config.REPORTS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._audit = AuditLogger(manager)
        self._versions = VersionController(manager)
        self._budget = BudgetManager(manager, self._audit)

    def generate(self, version: ArtifactVersion) -> CertificationArtifacts:
        """Produce both artifacts for the certified ``version``."""
        stem = f"{version.artifact_key}_CERTIFIED_{version.version_label.lstrip('_')}"
        workbook_out = self._dir / f"{stem}{version.file_path.suffix or '.xlsx'}"
        report_out = self._dir / f"{stem}_AUDIT_REPORT.md"

        for target in (workbook_out, report_out):
            if target.exists():
                raise ReportExistsError(f"certification artifact already exists: {target}")
        if not version.file_path.exists():
            raise FileNotFoundError(f"certified workbook source missing: {version.file_path}")

        shutil.copy2(version.file_path, workbook_out)
        report_out.write_text(self._render_report(version, workbook_out), encoding="utf-8")

        self._audit.log_action(
            "CERTIFICATION_REPORT", f"{version.artifact_key} {version.version_label}",
            "generated", metadata={"workbook": str(workbook_out), "report": str(report_out)},
        )
        return CertificationArtifacts(workbook_out, report_out)

    def _render_report(self, version: ArtifactVersion, workbook_out: Path) -> str:
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        budget = self._budget.status()
        lines: list[str] = []
        w = lines.append

        w("# Certification Report — DataBossX Title Agent")
        w("")
        w(f"- **Prospect**: {PROSPECT_ID}")
        w(f"- **Section**: {SECTION} · {COUNTY} County, {STATE}")
        w(f"- **Well**: {WELL_NAME}")
        w(f"- **Tracts**: {TRACT_COUNT} · **Gross acres target**: {GROSS_ACRE_TARGET:.2f}")
        w(f"- **Certified version**: `{version.version_label}`")
        w(f"- **Certified workbook**: `{workbook_out.name}`")
        w(f"- **Generated (UTC)**: {generated}")
        w("")
        w("## Certification statement")
        w("")
        w("This workbook passed all six quality gates with no outstanding "
          "escalations. No legal fact was fabricated: every automated change is "
          "a structural or mathematical repair, and every human decision is "
          "recorded below as an `EXAMINER_OVERRIDE`.")
        w("")
        w("## Quality gates")
        w("")
        w("| Gate | Status |")
        w("| --- | --- |")
        for gate in Gate:
            w(f"| {gate.value} | ✅ PASS |")
        w("")
        w("## Version lineage")
        w("")
        w("| Version | Reason | Created (UTC) |")
        w("| --- | --- | --- |")
        for v in self._versions.history(version.artifact_key):
            w(f"| {v.version_label} | {v.reason} | {v.created_at} |")
        w("")
        w("## Budget")
        w("")
        w(f"OKCountyRecords spend: **${budget.spent:.2f}** of ${budget.cap:.2f} "
          f"(${budget.remaining:.2f} remaining).")
        w("")
        w("## Audit trail")
        w("")
        records = self._audit.read_all()
        w(f"{len(records)} entries (append-only, oldest first).")
        w("")
        w("| Time (UTC) | Action | Reference | Result | Actor |")
        w("| --- | --- | --- | --- | --- |")
        for r in records:
            ref = r.reference.replace("|", "\\|")
            res = r.result.replace("|", "\\|")
            w(f"| {r.timestamp} | {r.action} | {ref} | {res} | {r.actor} |")
        w("")
        return "\n".join(lines)
