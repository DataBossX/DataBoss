"""Final export bundle generator.

Produces (never overwriting): Markdown audit report, PDF certification/escalation
packet, JSON manifest, a copy of the SQLite DB, a source-verification packet, a
missing-document list, a human escalation matrix, and an examiner-ready ZIP.
A certified workbook copy is emitted only if all gates passed.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.run_manager import sha256_file


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _pdf(path: Path, title: str, lines: List[str]) -> Optional[Path]:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 54
    c.setFont("Helvetica-Bold", 14)
    c.drawString(54, y, title[:90]); y -= 24
    c.setFont("Helvetica", 9)
    for line in lines:
        for chunk in [line[i:i+110] for i in range(0, max(len(line), 1), 110)]:
            if y < 54:
                c.showPage(); c.setFont("Helvetica", 9); y = height - 54
            c.drawString(54, y, chunk); y -= 12
    c.showPage(); c.save()
    return path


class OutputGenerator:
    def __init__(self, run_manager, audit, db):
        self.rm = run_manager
        self.audit = audit
        self.db = db

    def generate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        run_id = context.get("run_id")
        results = context.get("gate_results", [])
        sources = context.get("source_documents", [])
        escalations = context.get("escalations", [])
        final_status = context.get("final_status", "ESCALATE")
        exports: Dict[str, str] = {}

        def reg(kind: str, path: Path, source_report: Optional[str] = None):
            digest = sha256_file(path)
            self.audit.report_export(run_id, kind, str(path), digest, source_report)
            exports[kind] = str(path)

        # 1. Markdown audit report.
        md_lines = [f"# Audit report — {run_id}", f"Final status: **{final_status}**", "",
                    "## Gates"]
        for r in results:
            md_lines.append(f"- {r['gate_name']}: **{r['status']}** ({r['severity']}) "
                            f"— {r.get('reason','')}")
        md = self.rm.unique_path("exports", "audit_report.md")
        _write(md, "\n".join(md_lines)); reg("markdown", md)

        # 2. JSON manifest of the run context (sanitized — already redacted config).
        jpath = self.rm.unique_path("exports", "run_manifest.json")
        _write(jpath, json.dumps({k: v for k, v in context.items()
                                  if k not in ("db",)}, indent=2, default=str))
        reg("json", jpath)

        # 3. DB copy.
        dbcopy = self.rm.unique_path("exports", "audit_db_copy.sqlite3")
        self.db.raw_backup_to(dbcopy); reg("db_copy", dbcopy)

        # 4. Missing-document list.
        open_docs = [s for s in sources if s.get("status") in ("queued", "blocked", "unavailable")]
        mdoc = self.rm.unique_path("exports", "missing_documents.md")
        mlines = ["# Missing / unretrieved documents"]
        mlines += [f"- {s.get('book_page') or s.get('instrument_number')}: {s.get('status')} "
                   f"({s.get('detail','')})" for s in open_docs] or ["- none"]
        _write(mdoc, "\n".join(mlines)); reg("markdown", mdoc)

        # 5. Escalation matrix.
        ematrix = self.rm.unique_path("exports", "escalation_matrix.md")
        elines = ["# Human escalation matrix", "| Priority | Class | Subject | Needed | Action |",
                  "|---|---|---|---|---|"]
        for e in escalations:
            elines.append(f"| {e.get('priority','')} | {e.get('failure_class','')} | "
                          f"{e.get('subject','')} | {e.get('needed_document','')} | "
                          f"{e.get('recommended_action','')} |")
        if not escalations:
            elines.append("| - | - | none | - | - |")
        _write(ematrix, "\n".join(elines)); reg("markdown", ematrix)

        # 6. Source verification packet.
        spacket = self.rm.unique_path("exports", "source_verification.md")
        slines = ["# Source verification packet", "| Ref | Status | Origin | SHA256 |",
                  "|---|---|---|---|"]
        for s in sources:
            slines.append(f"| {s.get('book_page') or s.get('instrument_number')} | "
                          f"{s.get('status')} | {s.get('origin','')} | {s.get('sha256','') or ''} |")
        if not sources:
            slines.append("| - | none | - | - |")
        _write(spacket, "\n".join(slines)); reg("markdown", spacket)

        # 7. PDF certification/escalation packet.
        pdf = self.rm.unique_path("exports", "certification_packet.pdf")
        pdf_lines = [f"Run: {run_id}", f"Final status: {final_status}", "",
                     "Gate results:"] + \
                    [f"- {r['gate_name']}: {r['status']} ({r['severity']}) {r.get('reason','')}"
                     for r in results]
        made = _pdf(pdf, f"DataBossX Certification/Escalation Packet — {final_status}", pdf_lines)
        if made:
            reg("pdf", pdf)

        # 8. Certified workbook copy only if all gates pass.
        if final_status == "CERTIFY" and context.get("latest_workbook"):
            import shutil
            cw = self.rm.unique_path("exports", "certified_workbook.xlsx")
            shutil.copy2(context["latest_workbook"], cw)
            reg("certified_workbook", cw)

        # 9. Examiner-ready ZIP of the exports folder.
        zpath = self.rm.unique_path("exports", "examiner_bundle.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            for kind, p in list(exports.items()):
                zf.write(p, Path(p).name)
        reg("zip", zpath)

        return exports
