"""Final export generation.

Produces the examiner-ready export set under the run's ``exports`` folder. Every
artifact is versioned/timestamped (never overwritten), SHA-256 hashed, and
recorded in the append-only ``report_exports`` table.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.enums import GateStatus
from core.hashing import sha256_file
from db.audit_logger import AuditLogger
from validators.base_validator import Escalation, ValidationResult

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas as _pdf_canvas
    _HAVE_REPORTLAB = True
except Exception:  # pragma: no cover
    _HAVE_REPORTLAB = False


FACT_LABELS = (
    "VERIFIED",
    "UNVERIFIED",
    "ESCALATED",
    "BLOCKED BY SPEND CAP",
    "BLOCKED BY MISSING CREDENTIALS",
    "NEEDS EXAMINER REVIEW",
)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


@dataclass
class ExportBundle:
    files: List[Dict[str, str]] = field(default_factory=list)
    zip_path: Optional[str] = None

    def add(self, export_type: str, path: Path, sha256: str) -> None:
        self.files.append(
            {"export_type": export_type, "path": str(path), "sha256": sha256}
        )


class OutputGenerator:
    def __init__(self, audit: AuditLogger, run_id: str, exports_dir: Path) -> None:
        self.audit = audit
        self.run_id = run_id
        self.exports_dir = Path(exports_dir)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def _write(self, export_type: str, filename: str, body: str, bundle: ExportBundle) -> Path:
        path = self.exports_dir / filename
        if path.exists():
            path = self.exports_dir / f"{path.stem}_{_stamp()}{path.suffix}"
        path.write_text(body, encoding="utf-8")
        sha = sha256_file(path)
        self.audit.log_report_export(export_type, str(path), sha, run_id=self.run_id)
        bundle.add(export_type, path, sha)
        return path

    def _copy(self, export_type: str, src: Path, filename: str, bundle: ExportBundle) -> Optional[Path]:
        if not src or not Path(src).exists():
            return None
        dest = self.exports_dir / filename
        if dest.exists():
            dest = self.exports_dir / f"{dest.stem}_{_stamp()}{dest.suffix}"
        shutil.copy2(src, dest)
        sha = sha256_file(dest)
        self.audit.log_report_export(export_type, str(dest), sha, run_id=self.run_id)
        bundle.add(export_type, dest, sha)
        return dest

    # ------------------------------------------------------------------ #
    def _markdown_audit(self, ctx: Dict[str, Any]) -> str:
        results: List[ValidationResult] = ctx.get("results", [])
        final_state = ctx.get("final_state", "UNKNOWN")
        certified = ctx.get("certified", False)
        lines = [
            f"# DataBossX Validation Audit Report",
            "",
            f"- Run ID: `{self.run_id}`",
            f"- Generated: {datetime.now(timezone.utc).isoformat()}",
            f"- Final state: **{final_state}**",
            f"- Certified: **{'YES' if certified else 'NO'}**",
            "",
            "## Validation Scorecard",
            "",
            "| Gate | Status | Severity | Repairable | Subject | Reason |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for r in results:
            lines.append(
                f"| {r.gate_name} | {r.status.value} | {r.severity.value} | "
                f"{'yes' if r.repairable else 'no'} | {r.affected_subject or ''} | "
                f"{(r.reason or '').replace('|', '/')} |"
            )
        lines += ["", "## Fact Label Legend", ""]
        lines += [f"- **{label}**" for label in FACT_LABELS]
        return "\n".join(lines) + "\n"

    def _missing_docs(self, ctx: Dict[str, Any]) -> str:
        index = ctx.get("source_index", {})
        lines = ["# Missing / Unretrieved Source Documents", ""]
        for bucket, label in (
            ("missing", "MISSING"),
            ("blocked", "BLOCKED BY SPEND CAP"),
            ("failed", "BLOCKED BY MISSING CREDENTIALS"),
        ):
            items = index.get(bucket, [])
            lines.append(f"## {label} ({len(items)})")
            for it in items:
                key = it.get("reference_key", str(it))
                detail = it.get("detail", "")
                lines.append(f"- `{key}` {('— ' + detail) if detail else ''}")
            lines.append("")
        return "\n".join(lines) + "\n"

    def _escalation_matrix(self, ctx: Dict[str, Any]) -> str:
        escalations: List[Escalation] = ctx.get("escalations", [])
        lines = [
            "# Human Escalation Matrix",
            "",
            "| Urgency | Gate | Subject | Category | Recommended Examiner Action |",
            "| --- | --- | --- | --- | --- |",
        ]
        for e in escalations:
            lines.append(
                f"| {e.urgency.value} | {e.failed_gate} | {e.subject or ''} | "
                f"{e.failure_category.value if e.failure_category else ''} | "
                f"{(e.recommended_examiner_action or '').replace('|', '/')} |"
            )
        return "\n".join(lines) + "\n"

    def _source_packet(self, ctx: Dict[str, Any]) -> str:
        return json.dumps(ctx.get("source_index", {}), indent=2, sort_keys=True, default=str)

    def _pdf_packet(self, ctx: Dict[str, Any], filename: str, bundle: ExportBundle) -> Optional[Path]:
        if not _HAVE_REPORTLAB:
            return None
        path = self.exports_dir / filename
        if path.exists():
            path = self.exports_dir / f"{path.stem}_{_stamp()}{path.suffix}"
        certified = ctx.get("certified", False)
        title = "CERTIFICATION PACKET" if certified else "ESCALATION PACKET"
        results: List[ValidationResult] = ctx.get("results", [])
        c = _pdf_canvas.Canvas(str(path), pagesize=letter)
        width, height = letter
        y = height - inch
        c.setFont("Helvetica-Bold", 16)
        c.drawString(inch, y, f"DataBossX {title}")
        y -= 0.4 * inch
        c.setFont("Helvetica", 10)
        c.drawString(inch, y, f"Run: {self.run_id}")
        y -= 0.25 * inch
        c.drawString(inch, y, f"Certified: {'YES' if certified else 'NO'}")
        y -= 0.35 * inch
        c.setFont("Helvetica-Bold", 12)
        c.drawString(inch, y, "Gate Results")
        y -= 0.25 * inch
        c.setFont("Helvetica", 9)
        for r in results:
            if y < inch:
                c.showPage()
                y = height - inch
                c.setFont("Helvetica", 9)
            c.drawString(inch, y, f"[{r.status.value}] {r.gate_name} — {(r.reason or '')[:90]}")
            y -= 0.2 * inch
        c.showPage()
        c.save()
        sha = sha256_file(path)
        self.audit.log_report_export(
            "pdf_packet", str(path), sha, run_id=self.run_id
        )
        bundle.add("pdf_packet", path, sha)
        return path

    # ------------------------------------------------------------------ #
    def generate(self, ctx: Dict[str, Any]) -> ExportBundle:
        """ctx keys: results, escalations, source_index, manifest_path, db_path,
        certified, final_state, latest_version_path, repaired (bool)."""
        bundle = ExportBundle()

        self._write("markdown_audit", "audit_report.md", self._markdown_audit(ctx), bundle)
        self._write("missing_documents", "missing_documents.md", self._missing_docs(ctx), bundle)
        self._write("escalation_matrix", "escalation_matrix.md", self._escalation_matrix(ctx), bundle)
        self._write("source_packet", "source_verification.json", self._source_packet(ctx), bundle)
        self._pdf_packet(ctx, "certification_or_escalation.pdf", bundle)

        if ctx.get("manifest_path"):
            self._copy("json_manifest", Path(ctx["manifest_path"]), "manifest.json", bundle)
        if ctx.get("db_path"):
            self._copy("sqlite_db", Path(ctx["db_path"]), "audit_db.sqlite3", bundle)

        latest = ctx.get("latest_version_path")
        if latest and Path(latest).exists():
            if ctx.get("repaired"):
                self._copy("repaired_workbook", Path(latest), Path(latest).name, bundle)
            if ctx.get("certified"):
                self._copy("certified_workbook", Path(latest), "CERTIFIED_" + Path(latest).name, bundle)

        # examiner-ready ZIP of everything produced above
        zip_name = f"examiner_package_{_stamp()}.zip"
        zip_path = self.exports_dir / zip_name
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for entry in bundle.files:
                p = Path(entry["path"])
                if p.exists() and p != zip_path:
                    zf.write(p, p.name)
        zsha = sha256_file(zip_path)
        self.audit.log_report_export("examiner_zip", str(zip_path), zsha, run_id=self.run_id)
        bundle.zip_path = str(zip_path)
        return bundle
