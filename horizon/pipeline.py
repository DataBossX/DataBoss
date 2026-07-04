"""The Intelligence Layer, operationalized.

This is where the isolated engines are wired together into an actual title
build: read the OGL register and the runsheet from a workbook, cross-reference
them on ``Instrument_Number``, reconcile interest down each tract's chain with
exact math, and emit a :class:`ReportModel` whose rows carry the reconciled
retained interest / net acres -- or a ``Needs Examiner Review`` /
``ESCALATED`` tag when the files don't support a determination.

Nothing here fabricates a balance. A chain break, an over-conveyance, an
unknown starting interest, or a legal description that doesn't tie all produce
tags, not invented numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .chaining import (
    CrossRef,
    OGLRecord,
    RunsheetNote,
    build_cross_reference,
    find_chain_breaks,
    normalize_instrument,
    reconcile_chain,
)
from .interest import FULL, format_acres, format_fraction, net_acres, try_parse_acres
from .models import ESCALATED_TAG, REVIEW_TAG, ReportModel, TitleRow

# Sheet-name hints for auto-detecting the two registers inside one workbook.
# NB: no "runs"/"run" here -- those are substrings of "Runsheet" and would make
# a runsheet tab (which precedes the OGL tab) get parsed as the OGL register.
_OGL_SHEET_HINTS = ("ogl", "o&g", "lease", "conveyance", "instrument", "register")
_RUNSHEET_HINTS = ("runsheet", "run sheet", "notes")

# Header synonyms for the reference sheets (superset of report_io's map).
_OGL_HEADERS: Dict[str, str] = {
    "instrument": "instrument_number", "instrument_number": "instrument_number",
    "instrument_no": "instrument_number", "doc_no": "instrument_number",
    "document_number": "instrument_number", "reception": "instrument_number",
    "grantor": "grantor", "from": "grantor", "assignor": "grantor", "lessor": "grantor",
    "grantee": "grantee", "to": "grantee", "assignee": "grantee", "lessee": "grantee",
    "conveyed": "conveyed_interest", "conveyed_interest": "conveyed_interest",
    "interest": "conveyed_interest", "fraction": "conveyed_interest",
    "legal": "legal_description", "legal_description": "legal_description",
    "description": "legal_description", "tract": "legal_description",
    "type": "doc_type", "doc_type": "doc_type", "instrument_type": "doc_type",
    "date": "instrument_date", "instrument_date": "instrument_date", "dated": "instrument_date",
    "acres": "gross_acres", "gross_acres": "gross_acres", "gross": "gross_acres",
    "acreage": "gross_acres", "gross_acreage": "gross_acres",
}
_RUNSHEET_HEADERS: Dict[str, str] = {
    "instrument": "instrument_number", "instrument_number": "instrument_number",
    "instrument_no": "instrument_number", "doc_no": "instrument_number",
    "note": "note", "notes": "note", "comment": "note", "remarks": "note",
    "legal": "legal_description", "legal_description": "legal_description",
    "description": "legal_description",
}


def _canon(header, table) -> Optional[str]:
    key = str(header or "").strip().lower().replace(" ", "_")
    return table.get(key)


def _detect_header(ws, table) -> Tuple[int, Dict[int, str]]:
    """Find the header row and column->field map for a reference sheet."""
    best_row, best_map = -1, {}
    for r_idx, values in enumerate(ws.iter_rows(values_only=True)):
        mapped = {i: _canon(v, table) for i, v in enumerate(values)}
        mapped = {i: f for i, f in mapped.items() if f}
        if len(mapped) > len(best_map):
            best_row, best_map = r_idx, mapped
        if r_idx > 30:
            break
    return best_row, best_map


def read_ogl_records(path: Path, sheet: Optional[str] = None) -> List[OGLRecord]:
    """Read OGL / conveyance rows from a workbook sheet."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = _pick_sheet(wb, sheet, _OGL_SHEET_HINTS, avoid=_RUNSHEET_HINTS)
    header_row, header_map = _detect_header(ws, _OGL_HEADERS)
    records: List[OGLRecord] = []
    if header_row >= 0:
        for r_idx, values in enumerate(ws.iter_rows(values_only=True)):
            if r_idx <= header_row:
                continue
            data = {f: (str(values[i]).strip() if i < len(values) and values[i] is not None else "")
                    for i, f in header_map.items()}
            if data.get("instrument_number") or data.get("grantor") or data.get("grantee"):
                records.append(OGLRecord(
                    instrument_number=data.get("instrument_number", ""),
                    grantor=data.get("grantor", ""),
                    grantee=data.get("grantee", ""),
                    conveyed_interest=data.get("conveyed_interest", ""),
                    legal_description=data.get("legal_description", ""),
                    doc_type=data.get("doc_type", ""),
                    instrument_date=data.get("instrument_date", ""),
                    gross_acres=data.get("gross_acres", ""),
                ))
    wb.close()
    return records


def read_runsheet_notes(path: Path, sheet: Optional[str] = None) -> List[RunsheetNote]:
    """Read runsheet notes from a workbook sheet."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = _pick_sheet(wb, sheet, _RUNSHEET_HINTS)
    header_row, header_map = _detect_header(ws, _RUNSHEET_HEADERS)
    notes: List[RunsheetNote] = []
    if header_row >= 0:
        for r_idx, values in enumerate(ws.iter_rows(values_only=True)):
            if r_idx <= header_row:
                continue
            data = {f: (str(values[i]).strip() if i < len(values) and values[i] is not None else "")
                    for i, f in header_map.items()}
            if data.get("instrument_number"):
                notes.append(RunsheetNote(
                    instrument_number=data.get("instrument_number", ""),
                    note=data.get("note", ""),
                    legal_description=data.get("legal_description", ""),
                ))
    wb.close()
    return notes


def _pick_sheet(wb, name: Optional[str], hints, avoid=()):
    if name and name in wb.sheetnames:
        return wb[name]
    # Prefer a sheet that matches a hint and matches none of the `avoid` hints.
    for sn in wb.sheetnames:
        low = sn.lower()
        if any(h in low for h in hints) and not any(a in low for a in avoid):
            return wb[sn]
    # Fall back to any hint match (even if it also looked like an avoided kind).
    for sn in wb.sheetnames:
        low = sn.lower()
        if any(h in low for h in hints):
            return wb[sn]
    return wb.worksheets[0]


def score_reference_workbook(path: Path) -> int:
    """Score how well a workbook works as an OGL+runsheet reference source.

    Higher is better. A workbook that has *both* an OGL-like sheet and a
    runsheet-like sheet scores highest; the canonical NHE report name gets a
    bonus. Returns 0 (unusable) if it can't be opened or has neither register.
    """
    try:
        import openpyxl
    except ImportError:
        return 0
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return 0
    names = [s.lower() for s in wb.sheetnames]
    wb.close()

    has_ogl = any(any(h in n for h in _OGL_SHEET_HINTS) for n in names)
    has_run = any(any(h in n for h in _RUNSHEET_HINTS) for n in names)
    score = 0
    if has_ogl:
        score += 3
    if has_run:
        score += 3
    if has_ogl and has_run:
        score += 4  # a single workbook carrying both registers is ideal
    low_name = path.name.lower()
    if "cursory" in low_name or "nhe" in low_name or "title report" in low_name:
        score += 2
    if "roger" in low_name and "mills" in low_name:
        score += 1
    return score


def find_reference_workbook(paths) -> Optional[Path]:
    """Pick the best OGL+runsheet reference workbook from candidate paths."""
    best: Optional[Path] = None
    best_score = 0
    for p in paths:
        p = Path(p)
        if p.suffix.lower() not in (".xlsx", ".xlsm"):
            continue
        s = score_reference_workbook(p)
        if s > best_score:
            best, best_score = p, s
    return best


@dataclass
class ChainedBuild:
    report: ReportModel
    cross_reference: Dict[str, CrossRef] = field(default_factory=dict)
    chain_breaks: List[CrossRef] = field(default_factory=list)
    tracts_reviewed: List[str] = field(default_factory=list)


def chain_to_report(
    ogl_records: List[OGLRecord],
    runsheet_notes: List[RunsheetNote],
    section: str = "31-12N-24W",
    tract_legals: Optional[Dict[str, str]] = None,
    starting_interests: Optional[Dict[str, object]] = None,
) -> ChainedBuild:
    """Build a reconciled report from the OGL register + runsheet.

    Records are grouped into chains by their (normalized) legal description --
    that is the "tract". Within a tract they are walked in file order and the
    interest is reconciled exactly. Rows that cannot be tied out carry a
    ``Needs Examiner Review`` status; instruments that break the OGL<->runsheet
    link are marked in remarks. Nothing is balanced by fabrication.
    """
    tract_legals = tract_legals or {}
    starting_interests = starting_interests or {}

    xref = build_cross_reference(ogl_records, runsheet_notes)
    breaks = find_chain_breaks(xref)
    break_keys = {c.key for c in breaks}

    # group OGL records into tract chains keyed by normalized legal description
    tracts: Dict[str, List[OGLRecord]] = {}
    for rec in ogl_records:
        tract_key = _tract_key(rec.legal_description) or "UNSPECIFIED"
        tracts.setdefault(tract_key, []).append(rec)

    rows: List[TitleRow] = []
    reviewed: List[str] = []

    for tract_key, records in tracts.items():
        tract_legal = tract_legals.get(tract_key, records[0].legal_description if records else "")
        start = starting_interests.get(tract_key, FULL)
        result = reconcile_chain(tract_key, records, starting_interest=start,
                                 tract_legal=tract_legal)
        if result.needs_examiner_review:
            reviewed.append(tract_key)

        for link, rec in zip(result.links, records):
            remarks_bits: List[str] = []
            status = "ok"

            key = normalize_instrument(rec.instrument_number)
            if key and key in break_keys:
                xstatus = xref.get(key, CrossRef(key=key)).status
                detail = {
                    "orphan_note": "runsheet note references an instrument with no OGL record",
                    "unreferenced_ogl": "OGL instrument never referenced in the runsheet",
                    "duplicate_ogl": "instrument number appears on multiple OGL rows",
                }.get(xstatus, "instrument not matched across OGL/runsheet")
                remarks_bits.append(f"Chain break: {detail}")
                status = REVIEW_TAG
            if not link.tied_to_legal:
                remarks_bits.append("Legal description does not tie to tract")
                status = REVIEW_TAG
            if not link.grantor_continuity:
                remarks_bits.append(
                    f"Chain-of-title break: grantor does not match prior grantee")
                status = REVIEW_TAG
            rc = link.reconciliation
            if rc.status != "balanced":
                remarks_bits.append(rc.note)
                status = REVIEW_TAG
            if not key and (rec.grantor or rec.grantee):
                remarks_bits.append("Missing instrument number")
                status = REVIEW_TAG

            retained_txt = format_fraction(rc.retained) if rc.retained is not None else ""

            # Net mineral acres = conveyed interest x gross acres, exact. Blank
            # (never guessed) when gross acres or the conveyed interest is unknown.
            # Gross acres is a decimal/whole number -- a fraction form is rejected.
            nma_txt = ""
            gross = try_parse_acres(rec.gross_acres) \
                if str(rec.gross_acres).strip() else None
            if gross is not None and link.conveyed is not None:
                nma_txt = format_acres(net_acres(link.conveyed, gross))
            elif str(rec.gross_acres).strip() and link.conveyed is not None:
                remarks_bits.append("Gross acres unparseable; net acres not computed")
                status = REVIEW_TAG

            # attach runsheet notes into remarks (verification trail)
            for note in xref.get(key, CrossRef(key=key)).notes if key else []:
                if note.note:
                    remarks_bits.append(f"Runsheet: {note.note}")

            rows.append(TitleRow(
                doc_type=rec.doc_type or None,
                instrument_date=rec.instrument_date or None,
                grantor=rec.grantor,
                grantee=rec.grantee,
                instrument_number=rec.instrument_number,
                legal_description=rec.legal_description,
                conveyed_interest=(format_fraction(link.conveyed)
                                   if link.conveyed is not None else ""),
                retained_interest=retained_txt,
                net_mineral_acres=nma_txt,
                status=status,
                remarks="; ".join(b for b in remarks_bits if b),
            ))

    report = ReportModel(section=section, source="chain_to_report", rows=rows)
    return ChainedBuild(report=report, cross_reference=xref,
                        chain_breaks=breaks, tracts_reviewed=reviewed)


def _tract_key(legal: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9]+", "", str(legal or "")).upper()


def build_from_workbook(path: Path, section: str = "31-12N-24W",
                        ogl_sheet: Optional[str] = None,
                        runsheet_sheet: Optional[str] = None) -> ChainedBuild:
    """Convenience: read both registers from one workbook and chain them."""
    ogl = read_ogl_records(path, ogl_sheet)
    notes = read_runsheet_notes(path, runsheet_sheet)
    return chain_to_report(ogl, notes, section=section)
