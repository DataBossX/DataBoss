"""
Output generator — builds the examiner-ready export bundle.

Produces: markdown audit report, PDF certification/escalation packet, JSON
manifest, a copy of the SQLite DB, a missing-document list, a human escalation
matrix, and a zip of everything. Never overwrites: if a target exists a new
numbered filename is used. A certified workbook copy is emitted only when the
run certified; otherwise the latest repaired version is included if any.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    i = 1
    while True:
        cand = path.with_name(f"{path.stem}_{i:02d}{path.suffix}")
        if not cand.exists():
            return cand
        i += 1


class OutputGenerator:
    def __init__(self, exports_dir: str | Path):
        self.exports_dir = Path(exports_dir)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    # ---- individual artifacts ----
    def write_markdown(self, text: str, name: str = "audit_report.md") -> Path:
        out = _unique(self.exports_dir / name)
        out.write_text(text, encoding="utf-8")
        return out

    def write_json(self, obj: Dict[str, Any], name: str = "manifest.json") -> Path:
        out = _unique(self.exports_dir / name)
        out.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
        return out

    def copy_db(self, db_path: str | Path, name: str = "audit_db_copy.sqlite3") -> Optional[Path]:
        src = Path(db_path)
        if not src.exists():
            return None
        out = _unique(self.exports_dir / name)
        shutil.copy2(src, out)
        return out

    def write_missing_docs(self, missing: List[Dict[str, Any]], name: str = "missing_documents.csv") -> Path:
        out = _unique(self.exports_dir / name)
        lines = ["reference,kind,sheet,cell,status"]
        for m in missing:
            lines.append(",".join(str(m.get(k, "")) for k in ("reference", "kind", "sheet", "cell", "status")))
        out.write_text("\n".join(lines), encoding="utf-8")
        return out

    def write_escalation_matrix(self, escalations: List[Dict[str, Any]],
                                name: str = "escalation_matrix.md") -> Path:
        out = _unique(self.exports_dir / name)
        lines = ["# Human Escalation Matrix", "",
                 "| # | Category | Subject | Detail | Recommended Action |",
                 "|---|---|---|---|---|"]
        for i, e in enumerate(escalations, 1):
            lines.append(f"| {i} | {e.get('category','')} | {str(e.get('subject',''))[:40]} | "
                         f"{str(e.get('detail',''))[:100].replace('|','/')} | "
                         f"{str(e.get('recommended_action',''))[:100].replace('|','/')} |")
        if not escalations:
            lines.append("| — | — | none | — | — |")
        out.write_text("\n".join(lines), encoding="utf-8")
        return out

    def write_pdf_packet(self, title: str, sections: List[tuple], name: str = "certification_packet.pdf") -> Optional[Path]:
        """sections = list of (heading, list_of_lines). Uses reportlab if available."""
        out = _unique(self.exports_dir / name)
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        except Exception:
            # Fallback: write a text packet so we never fake a PDF.
            alt = out.with_suffix(".txt")
            alt = _unique(alt)
            body = [title, "="*len(title), ""]
            for h, lines in sections:
                body += [h, "-"*len(h)] + list(lines) + [""]
            alt.write_text("\n".join(body), encoding="utf-8")
            return alt
        ss = getSampleStyleSheet()
        NAVY = colors.HexColor("#1F4E79")
        H = ParagraphStyle("H", parent=ss["Title"], fontSize=15, textColor=NAVY)
        SH = ParagraphStyle("SH", parent=ss["Heading2"], textColor=NAVY, fontSize=12)
        BODY = ParagraphStyle("B", parent=ss["Normal"], fontSize=9, leading=12)
        doc = SimpleDocTemplate(str(out), pagesize=letter,
                                leftMargin=0.7*inch, rightMargin=0.7*inch,
                                topMargin=0.6*inch, bottomMargin=0.6*inch, title=title)
        el = [Paragraph(title, H), HRFlowable(width="100%", color=NAVY), Spacer(1, 8)]
        for h, lines in sections:
            el.append(Paragraph(h, SH))
            for ln in lines:
                el.append(Paragraph(str(ln).replace("&", "&amp;").replace("<", "&lt;"), BODY))
            el.append(Spacer(1, 8))
        doc.build(el)
        return out

    def bundle_zip(self, files: List[Path], name: str = "examiner_package.zip") -> Path:
        out = _unique(self.exports_dir / name)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files:
                if f and Path(f).exists():
                    z.write(f, Path(f).name)
        return out
