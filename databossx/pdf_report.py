"""Client-ready PDF report builder (reportlab).

Renders a completed run into a paginated, professional PDF with a cover page,
run summary, the reconciled runsheet, mineral ownership, division of interest,
a defect list, and the evidence index -- with page numbers and a persistent
draft/synthetic footer. Long text wraps inside table cells; nothing is
truncated silently.

This is a *presentation* of what the engines produced; it introduces no new
numbers. Blank stays blank.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .ownership import TractOwnership

_NAVY = "#1F3A5F"
_DARK = "#13233B"
_REVIEW_BG = "#FBE4D5"


def _styles():
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("DBXTitle", parent=ss["Title"], textColor=_DARK,
                          fontSize=24, spaceAfter=6))
    ss.add(ParagraphStyle("DBXSub", parent=ss["Normal"], fontSize=12,
                          textColor=_NAVY, alignment=TA_CENTER, spaceAfter=2))
    ss.add(ParagraphStyle("DBXH2", parent=ss["Heading2"], textColor=_NAVY,
                          spaceBefore=12, spaceAfter=6))
    ss.add(ParagraphStyle("DBXCell", parent=ss["Normal"], fontSize=7.5,
                          leading=9))
    ss.add(ParagraphStyle("DBXCellHdr", parent=ss["Normal"], fontSize=7.5,
                          leading=9, textColor="#FFFFFF", fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("DBXNote", parent=ss["Normal"], fontSize=8,
                          textColor="#666666"))
    return ss


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor("#888888")
    canvas.drawString(
        54, 24,
        "DataBossX draft work product -- not a certified abstract or title "
        "opinion. Human release gate required.")
    canvas.drawRightString(558, 24, f"Page {doc.page}")
    canvas.restoreState()


def _cell(text, style) -> "object":
    from reportlab.platypus import Paragraph
    return Paragraph("" if text is None else str(text), style)


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]],
           col_widths: Sequence[float], ss,
           review_col: Optional[int] = None) -> "object":
    """Build a styled table; shade any row whose ``review_col`` isn't 'ok'."""
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    hdr = ss["DBXCellHdr"]
    body = ss["DBXCell"]
    data = [[_cell(h, hdr) for h in headers]]
    for r in rows:
        data.append([_cell(v, body) for v in r])

    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_NAVY)),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B9C4D2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5F9")]),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    if review_col is not None:
        for i, r in enumerate(rows, start=1):
            val = str(r[review_col] if review_col < len(r) else "").lower()
            if val and val != "ok" and val != "info":
                style.append(("BACKGROUND", (0, i), (-1, i),
                              colors.HexColor(_REVIEW_BG)))
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle(style))
    return t


def build_client_pdf(
    path: Path,
    *,
    meta: Dict[str, object],
    counts: Dict[str, int],
    rag: str,
    runsheet_rows: Sequence[object],
    tracts: List[TractOwnership],
    defects: Sequence[Dict[str, object]],
    evidence: Sequence[Dict[str, object]],
    synthetic: bool = False,
) -> Path:
    """Write the client PDF to ``path`` and return it."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    ss = _styles()
    story: List[object] = []

    # -- cover ---------------------------------------------------------------
    story.append(Spacer(1, 90))
    story.append(Paragraph("DataBossX", ss["DBXTitle"]))
    story.append(Paragraph("Land &amp; Title Intelligence Report", ss["DBXSub"]))
    story.append(Spacer(1, 24))
    for label, key in [("Project", "project"), ("Section", "section"),
                       ("Generated (UTC)", "generated")]:
        story.append(Paragraph(f"<b>{label}:</b> {meta.get(key, '')}", ss["DBXSub"]))
    story.append(Spacer(1, 18))
    story.append(Paragraph(f"<b>Overall status:</b> {rag}", ss["DBXSub"]))
    if synthetic:
        story.append(Spacer(1, 30))
        story.append(Paragraph(
            "SYNTHETIC DEMONSTRATION DATA -- NOT A REAL TITLE RECORD",
            ss["DBXSub"]))
    story.append(PageBreak())

    # -- summary -------------------------------------------------------------
    story.append(Paragraph("Run summary", ss["DBXH2"]))
    summary_rows = [
        ("Runsheet rows", counts.get("runsheet_rows", 0)),
        ("Tracts", counts.get("tracts", 0)),
        ("Mineral owners", counts.get("mineral_owners", 0)),
        ("Division-of-interest rows", counts.get("doi_rows", 0)),
        ("Chain breaks", counts.get("chain_breaks", 0)),
        ("Examiner-review items", counts.get("review_items", 0)),
        ("Defects", counts.get("defects", 0)),
        ("Evidence records", counts.get("evidence", 0)),
    ]
    story.append(_table(["Metric", "Value"],
                        [[k, v] for k, v in summary_rows],
                        [220, 90], ss))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Source root: {meta.get('source_root', '')}", ss["DBXNote"]))

    # -- runsheet ------------------------------------------------------------
    story.append(Paragraph("Runsheet -- reconciled chain of title", ss["DBXH2"]))
    rs_headers = ["Instrument", "Grantor", "Grantee", "Conveyed", "Retained",
                  "Net Ac", "Status", "Remarks"]
    rs_rows = [[
        _get(r, "instrument_number"), _get(r, "grantor"), _get(r, "grantee"),
        _get(r, "conveyed_interest"), _get(r, "retained_interest"),
        _get(r, "net_mineral_acres"), _get(r, "status"), _get(r, "remarks"),
    ] for r in runsheet_rows]
    story.append(_table(rs_headers, rs_rows,
                        [58, 92, 92, 42, 42, 38, 55, 85], ss, review_col=6))

    # -- mineral ownership ---------------------------------------------------
    story.append(Paragraph("Mineral ownership", ss["DBXH2"]))
    mo_headers = ["Tract", "Owner", "Mineral", "Net Ac", "Lessee", "Status"]
    mo_rows: List[List[object]] = []
    for t in tracts:
        for r in t.mineral_rows:
            d = r.display()
            mo_rows.append([t.tract, d["name"], d["mineral_interest"],
                            d["net_mineral_acres"], d["lessee"], d["status"]])
        mo_rows.append([t.tract, "TOTAL", _fmt_frac(t.total_mineral),
                        "", "8/8 check", ""])
    story.append(_table(mo_headers, mo_rows, [96, 150, 60, 55, 96, 50], ss,
                        review_col=5))

    # -- division of interest ------------------------------------------------
    story.append(Paragraph("Division of interest -- WI &amp; NRI", ss["DBXH2"]))
    doi_headers = ["Tract", "Party", "Role", "WI", "Royalty", "NRI", "Status"]
    doi_rows: List[List[object]] = []
    for t in tracts:
        for r in t.doi_rows:
            d = r.display()
            doi_rows.append([t.tract, d["name"], d["role"], d["working_interest"],
                             d["royalty_rate"], d["nri"], d["status"]])
        doi_rows.append([t.tract, "TOTAL", "", _fmt_dec(t.total_working_interest),
                         "", _fmt_dec(t.total_nri), ""])
    story.append(_table(doi_headers, doi_rows, [90, 120, 66, 62, 50, 62, 50], ss,
                        review_col=6))

    # -- defects -------------------------------------------------------------
    story.append(Paragraph("Defects &amp; missing evidence", ss["DBXH2"]))
    if defects:
        df_rows = [[d.get("severity", ""), d.get("category", ""),
                    d.get("subject", ""), d.get("detail", "")] for d in defects]
    else:
        df_rows = [["info", "none", "", "No defects detected in this run."]]
    story.append(_table(["Severity", "Category", "Subject", "Detail"],
                        df_rows, [55, 80, 120, 255], ss, review_col=0))

    # -- evidence ------------------------------------------------------------
    story.append(Paragraph("Evidence &amp; audit trail", ss["DBXH2"]))
    if evidence:
        ev_rows = [[e.get("file", ""), e.get("type", ""),
                    str(e.get("sha256", ""))[:16], e.get("method", "")]
                   for e in evidence]
    else:
        ev_rows = [["(none)", "", "", ""]]
    story.append(_table(["File", "Type", "SHA-256 (short)", "Method"],
                        ev_rows, [220, 90, 120, 80], ss))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            topMargin=48, bottomMargin=48,
                            leftMargin=54, rightMargin=54,
                            title="DataBossX Land & Title Report",
                            author="DataBossX")
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return path


# -- helpers ----------------------------------------------------------------
def _get(row: object, key: str) -> object:
    if isinstance(row, dict):
        return row.get(key, "") or ""
    return getattr(row, key, "") or ""


def _fmt_frac(frac) -> str:
    from horizon.interest import format_fraction
    return format_fraction(frac) if frac is not None else ""


def _fmt_dec(frac, places: int = 8) -> str:
    from horizon.interest import format_acres
    return format_acres(frac, places) if frac is not None else ""
