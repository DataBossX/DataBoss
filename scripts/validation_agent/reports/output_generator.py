"""Final export generator.

Produces the examiner-ready export bundle: markdown audit report, PDF packet,
JSON manifest, a copy of the append-only SQLite DB, a source-verification
packet, a missing-document list, a human escalation matrix, certified/repaired
workbook copies, and a zip package. Nothing is ever overwritten — colliding
names are numbered.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.run_manager import sha256_file


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class OutputGenerator:
    def __init__(self, run_manager, db=None, run_id: str = ""):
        self.rm = run_manager
        self.db = db
        self.run_id = run_id
        self.exports_dir = run_manager.run_dir / "exports"
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self._written: list[Path] = []

    def _record(self, export_type: str, path: Path, note: str = "") -> None:
        self._written.append(path)
        if self.db:
            try:
                self.db.record_report_export(
                    self.run_id, export_type, path.name, str(path),
                    sha256_file(path), note=note,
                )
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    def write_markdown(self, content: str, name: str = "audit_report.md") -> Path:
        path = self.rm.unique_export_path(name)
        path.write_text(content, encoding="utf-8")
        self._record("markdown", path, "audit report")
        return path

    def write_json_manifest(self, manifest: dict, name: str = "manifest.json") -> Path:
        path = self.rm.unique_export_path(name)
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True),
                        encoding="utf-8")
        self._record("json", path, "workbook manifest")
        return path

    def write_missing_documents(self, source_documents: list[dict]) -> Path:
        missing = [d for d in source_documents
                   if d.get("status") not in {"found_local", "retrieved"}]
        payload = {"generated": _now(), "count": len(missing),
                   "missing_documents": missing}
        path = self.rm.unique_export_path("missing_documents.json")
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._record("json", path, "missing document list")
        return path

    def write_source_packet(self, source_documents: list[dict]) -> Path:
        payload = {"generated": _now(), "source_documents": source_documents}
        path = self.rm.unique_export_path("source_verification_packet.json")
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._record("json", path, "source verification packet")
        return path

    def write_escalation_matrix(self, escalations: list[dict]) -> Path:
        lines = ["# Human Escalation Matrix", "",
                 f"_Generated {_now()}_", "",
                 "| # | Category | Severity | Subject | Reason | Recommended |",
                 "|---|----------|----------|---------|--------|-------------|"]
        for i, e in enumerate(escalations, 1):
            lines.append(
                f"| {i} | {e.get('category','')} | {e.get('severity','')} | "
                f"{e.get('subject','')} | {str(e.get('reason','')).replace('|','/')} "
                f"| {str(e.get('recommended_action','')).replace('|','/')} |"
            )
        if not escalations:
            lines.append("| - | (none) | | | No escalations. | |")
        path = self.rm.unique_export_path("escalation_matrix.md")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._record("markdown", path, "escalation matrix")
        return path

    def copy_database(self) -> Path | None:
        if not self.db:
            return None
        src = Path(self.db.db_path)
        if not src.exists():
            return None
        path = self.rm.unique_export_path("audit_copy.db")
        shutil.copy2(src, path)
        self._record("db_copy", path, "append-only DB snapshot")
        return path

    def copy_workbook(self, version_path: Path, certified: bool) -> Path | None:
        if not version_path or not Path(version_path).exists():
            return None
        prefix = "certified" if certified else "repaired"
        suffix = Path(version_path).suffix
        path = self.rm.unique_export_path(f"{prefix}_workbook{suffix}")
        shutil.copy2(version_path, path)
        self._record("workbook", path,
                     "certified copy" if certified else "latest repaired version")
        return path

    def write_pdf_packet(self, title: str, sections: list[tuple[str, str]],
                         name: str = "certification_packet.pdf") -> Path | None:
        """Render a simple PDF certification/escalation packet via reportlab."""
        try:
            from reportlab.lib.pagesizes import LETTER
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                            Spacer)
        except Exception:
            return None
        path = self.rm.unique_export_path(name)
        doc = SimpleDocTemplate(str(path), pagesize=LETTER,
                                topMargin=0.75 * inch, bottomMargin=0.75 * inch)
        styles = getSampleStyleSheet()
        flow = [Paragraph(title, styles["Title"]),
                Paragraph(f"Generated {_now()}", styles["Normal"]),
                Spacer(1, 12)]
        for heading, body in sections:
            flow.append(Paragraph(heading, styles["Heading2"]))
            for line in body.splitlines() or [""]:
                safe = (line.replace("&", "&amp;").replace("<", "&lt;")
                        .replace(">", "&gt;"))
                flow.append(Paragraph(safe or "&nbsp;", styles["Normal"]))
            flow.append(Spacer(1, 10))
        doc.build(flow)
        self._record("pdf", path, "certification/escalation packet")
        return path

    def build_zip(self, name: str = "examiner_package.zip") -> Path:
        """Zip everything written so far into an examiner-ready bundle."""
        path = self.rm.unique_export_path(name)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in self._written:
                if f.exists() and f.resolve() != path.resolve():
                    zf.write(f, f.name)
        # Record after the fact (not inside its own zip).
        if self.db:
            try:
                self.db.record_report_export(
                    self.run_id, "zip", path.name, str(path),
                    sha256_file(path), note="examiner package")
            except Exception:
                pass
        return path
