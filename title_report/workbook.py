"""Excel workbook generation for the cursory title report.

Produces one ``.xlsx`` with every required tab. The NRI/WI matrix uses live
Excel formulas (built in :mod:`title_report.fractions`) so derived interests
recompute in the spreadsheet and remain auditable. All data tables get an
auto-filter and a frozen header row.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import List, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .models import TitleReport, UNKNOWN
from . import fractions as fr

# ── styling ────────────────────────────────────────────────────────────────
HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(color="FFFFFF", bold=True)
TITLE_FONT = Font(size=16, bold=True, color="1F4E79")
WARN_FILL = PatternFill("solid", fgColor="FFC7CE")
WARN_FONT = Font(bold=True, color="9C0006")
REVIEW_FILL = PatternFill("solid", fgColor="FFE699")
HIGH_FILL = PatternFill("solid", fgColor="FF9999")
MED_FILL = PatternFill("solid", fgColor="FFD580")
LOW_FILL = PatternFill("solid", fgColor="C6EFCE")
UNKNOWN_FONT = Font(italic=True, color="808080")
_THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _join(values) -> str:
    if not values:
        return ""
    if isinstance(values, list):
        return "; ".join(str(v) for v in values)
    return str(values)


def _cell(value):
    """Render a model value for a cell: fractions -> decimal float, lists -> joined."""
    if isinstance(value, Fraction):
        return float(value)
    if isinstance(value, list):
        return _join(value)
    return value


def _style_table(ws: Worksheet, header_row: int = 1) -> None:
    for cell in ws[header_row]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    # mark UNKNOWN cells in grey italics for at-a-glance scanning
    for row in ws.iter_rows(min_row=header_row + 1):
        for cell in row:
            if cell.value == UNKNOWN:
                cell.font = UNKNOWN_FONT
    if ws.max_row >= header_row and ws.max_column >= 1:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(ws.max_column)}{ws.max_row}"
        ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    _autofit(ws)


def _autofit(ws: Worksheet) -> None:
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        max_len = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[letter].width = min(max(max_len + 3, 10), 58)


def _append(ws: Worksheet, values) -> None:
    ws.append([_cell(v) for v in values])


# ── sheets ──────────────────────────────────────────────────────────────────

def _sheet_cover(wb: Workbook, rpt: TitleReport) -> None:
    ws = wb.create_sheet("Cover")
    cfg = rpt.config
    ws["A1"] = f"{cfg.report_type} — {cfg.tract_label}"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:D1")

    if cfg.is_placeholder:
        ws["A3"] = ("DATA STATUS: PLACEHOLDER — illustrative data only; "
                    "no live records examined.")
        ws["A3"].fill = WARN_FILL
        ws["A3"].font = WARN_FONT
        ws.merge_cells("A3:D3")

    rows = [
        ("Section-Township-Range", f"{cfg.section}-{cfg.township}-{cfg.range_}"),
        ("County / State", f"{cfg.county} / {cfg.state}"),
        ("Report Type", cfg.report_type),
        ("Report Date", cfg.report_date),
        ("Source Cutoff Date", cfg.source_cutoff_date),
        ("Gross Acres (assumed)", fr.frac_str(cfg.gross_acres)),
        ("Net Mineral Acres (assumed)", fr.frac_str(cfg.net_mineral_acres)),
        ("Acreage Basis", cfg.acreage_basis),
        ("Prepared For", cfg.prepared_for),
        ("Preparer", cfg.preparer),
    ]
    r = 5
    for label, value in rows:
        ws.cell(row=r, column=1, value=label).font = Font(bold=True)
        ws.cell(row=r, column=2, value=value)
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Assumptions & Scope").font = Font(bold=True, size=12)
    r += 1
    for a in cfg.assumptions:
        ws.cell(row=r, column=1, value=f"• {a}")
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        r += 1

    r += 1
    counts = [
        ("Sources", len(rpt.sources)),
        ("Instruments (runsheet)", len(rpt.instruments)),
        ("Abstractions", len(rpt.abstractions)),
        ("Chain links", len(rpt.chain_links)),
        ("Wells", len(rpt.wells)),
        ("Curative items", len(rpt.curative)),
        ("Ownership entries", len(rpt.ownership)),
    ]
    ws.cell(row=r, column=1, value="Schedule Counts").font = Font(bold=True, size=12)
    r += 1
    for label, n in counts:
        ws.cell(row=r, column=1, value=label).font = Font(bold=True)
        ws.cell(row=r, column=2, value=n)
        r += 1

    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 40


def _sheet_source_log(wb: Workbook, rpt: TitleReport) -> None:
    ws = wb.create_sheet("Source Log")
    ws.append(["Source ID", "Category", "Name", "Location", "Accessed",
               "Doc Count", "Credential Req'd", "Page Ref", "Notes"])
    for s in rpt.sources:
        _append(ws, [s.source_id, s.category, s.name, s.location, s.accessed_date,
                     s.doc_count, "YES" if s.credential_required else "no",
                     s.page_ref, s.notes])
    _style_table(ws)


def _sheet_runsheet(wb: Workbook, rpt: TitleReport) -> None:
    ws = wb.create_sheet("Runsheet")
    ws.append(["Instrument #", "Type", "Book", "Page", "Instrument Date",
               "Recording Date", "Grantors", "Grantees", "Legal (raw)",
               "Legal (normalized)", "Consideration", "Classification",
               "Citation", "Notes"])
    for i in rpt.instruments:
        _append(ws, [i.instrument_no, i.instrument_type, i.book, i.page,
                     i.instrument_date, i.recording_date, i.grantors, i.grantees,
                     i.legal_raw, i.legal_normalized, i.consideration,
                     i.classification, i.citation, i.notes])
    _style_table(ws)


def _sheet_abstractions(wb: Workbook, rpt: TitleReport) -> None:
    ws = wb.create_sheet("Abstractions")
    ws.append(["Instrument #", "Grant Clause", "Reservations", "Royalty/WI Language",
               "Exceptions", "Pugh/Shut-in", "Depth Limits", "Pooling Refs",
               "Liens", "Probate", "Tags", "Confidence", "Needs Review", "Citation"])
    for a in rpt.abstractions:
        _append(ws, [a.instrument_no, a.grant_clause, a.reservations,
                     a.royalty_wi_language, a.exceptions, a.pugh_shutin,
                     a.depth_limits, a.pooling_refs, a.liens, a.probate,
                     a.tags, a.confidence, "YES" if a.needs_review else "no",
                     a.citation])
        if a.needs_review:
            for cell in ws[ws.max_row]:
                if cell.value != UNKNOWN:
                    cell.fill = REVIEW_FILL
    _style_table(ws)


def _sheet_chain(wb: Workbook, rpt: TitleReport, chain_type: str, title: str) -> None:
    ws = wb.create_sheet(title)
    ws.append(["Seq", "Instrument #", "Date", "Conveyance", "From", "To",
               "Interest", "Gap Note", "Citation"])
    links = [c for c in rpt.chain_links if c.chain_type == chain_type]
    for c in sorted(links, key=lambda x: x.seq):
        _append(ws, [c.seq, c.instrument_no, c.date, c.conveyance, c.from_party,
                     c.to_party, c.interest, c.gap_note, c.citation])
        if c.gap_note:
            ws[ws.max_row][7].fill = REVIEW_FILL
    _style_table(ws)


def _sheet_wells(wb: Workbook, rpt: TitleReport) -> None:
    ws = wb.create_sheet("Wells & HBP")
    ws.append(["API #", "Well Name", "Operator", "Formation", "Spacing Order",
               "Pooling Order", "First Production", "Status", "HBP Support", "Citation"])
    for w in rpt.wells:
        _append(ws, [w.api_number, w.well_name, w.operator, w.formation,
                     w.spacing_order, w.pooling_order, w.first_production,
                     w.status, w.hbp_support, w.citation])
    _style_table(ws)


def _sheet_curative(wb: Workbook, rpt: TitleReport) -> None:
    ws = wb.create_sheet("Curative")
    ws.append(["Issue ID", "Type", "Instrument #", "Description", "Materiality",
               "Priority", "Status", "Recommended Action", "Citation"])
    for c in rpt.curative:
        _append(ws, [c.issue_id, c.issue_type, c.instrument_no, c.description,
                     c.materiality, c.priority, c.status, c.recommended_action,
                     c.citation])
        fill = {"High": HIGH_FILL, "Medium": MED_FILL, "Low": LOW_FILL}.get(c.materiality)
        if fill:
            ws[ws.max_row][4].fill = fill
    _style_table(ws)


def _sheet_ownership(wb: Workbook, rpt: TitleReport) -> None:
    """NRI/WI matrix with live, auditable Excel formulas for derived columns."""
    ws = wb.create_sheet("NRI-WI Matrix")
    headers = ["Owner", "Role", "Mineral Interest", "Lease Royalty",
               "Working Interest", "Burdens", "NRI (computed)",
               "NMA (computed)", "Basis Language", "Citation"]
    ws.append(headers)
    # Gross acres assumption drives NMA; expose it as a named anchor cell.
    gross = rpt.config.gross_acres
    gross_decimal = float(gross) if isinstance(gross, Fraction) else None

    for o in rpt.ownership:
        row = ws.max_row + 1
        mineral = _cell(o.mineral_interest)
        royalty = _cell(o.lease_royalty)
        wi = _cell(o.working_interest)
        burdens = _cell(o.burdens)
        ws.cell(row=row, column=1, value=o.owner)
        ws.cell(row=row, column=2, value=o.role)
        ws.cell(row=row, column=3, value="" if mineral == UNKNOWN else mineral)
        ws.cell(row=row, column=4, value="" if royalty == UNKNOWN else royalty)
        ws.cell(row=row, column=5, value="" if wi == UNKNOWN else wi)
        ws.cell(row=row, column=6, value="" if burdens == UNKNOWN else burdens)

        # NRI: royalty owners use mineral*royalty; WI owners use WI*(1-burdens).
        if o.role == "working_interest":
            ws.cell(row=row, column=7,
                    value=fr.excel_wi_nri_formula(f"E{row}", f"F{row}"))
        else:
            ws.cell(row=row, column=7,
                    value=fr.excel_nri_formula(f"C{row}", f"D{row}"))

        # NMA = mineral interest * gross acres assumption.
        if gross_decimal is not None:
            ws.cell(row=row, column=8,
                    value=(f'=IF(C{row}="","UNKNOWN",C{row}*{gross_decimal})'))
        else:
            ws.cell(row=row, column=8, value=UNKNOWN)

        ws.cell(row=row, column=9, value=o.basis_language)
        ws.cell(row=row, column=10, value=o.citation)

    note_row = ws.max_row + 2
    ws.cell(row=note_row, column=1,
            value=("Derived columns are live formulas: royalty NRI = Mineral×Royalty; "
                   "WI NRI = WI×(1−Burdens); NMA = Mineral×{:s} gross acres. "
                   "Blank inputs render UNKNOWN — never 0.").format(fr.frac_str(gross)))
    ws.cell(row=note_row, column=1).font = Font(italic=True, size=9)
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=10)
    _style_table(ws)


def _sheet_qa_dashboard(wb: Workbook, rpt: TitleReport, qa_summary: Optional[dict]) -> None:
    ws = wb.create_sheet("QA Dashboard")
    ws["A1"] = "QA Dashboard"
    ws["A1"].font = TITLE_FONT
    ws.append([])
    ws.append(["Check", "Result", "Detail"])
    hdr = ws.max_row
    if qa_summary:
        for chk in qa_summary.get("checks", []):
            ws.append([chk["name"], chk["status"], chk["detail"]])
            res_cell = ws[ws.max_row][1]
            res_cell.fill = LOW_FILL if chk["status"] == "PASS" else (
                WARN_FILL if chk["status"] == "FAIL" else MED_FILL)
    else:
        ws.append(["(QA not yet run)", "", ""])
    _style_table(ws, header_row=hdr)


def _sheet_missing(wb: Workbook, rpt: TitleReport, missing: List[dict]) -> None:
    ws = wb.create_sheet("Missing-Unverified")
    ws.append(["Item", "Type", "Reason", "Citation/Source"])
    for m in missing:
        _append(ws, [m.get("item", UNKNOWN), m.get("type", UNKNOWN),
                     m.get("reason", UNKNOWN), m.get("source", UNKNOWN)])
    if not missing:
        ws.append(["(none flagged)", "", "", ""])
    _style_table(ws)


# ── public entry point ───────────────────────────────────────────────────────

def build_workbook(
    rpt: TitleReport,
    output_path: str,
    qa_summary: Optional[dict] = None,
    missing: Optional[List[dict]] = None,
) -> str:
    wb = Workbook()
    wb.remove(wb.active)

    _sheet_cover(wb, rpt)
    _sheet_source_log(wb, rpt)
    _sheet_runsheet(wb, rpt)
    _sheet_abstractions(wb, rpt)
    _sheet_chain(wb, rpt, "mineral_surface", "Chain — Mineral-Surface")
    _sheet_chain(wb, rpt, "leasehold_wi_burdens", "Chain — Leasehold-WI")
    _sheet_wells(wb, rpt)
    _sheet_curative(wb, rpt)
    _sheet_ownership(wb, rpt)
    _sheet_qa_dashboard(wb, rpt, qa_summary)
    _sheet_missing(wb, rpt, missing or [])

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
