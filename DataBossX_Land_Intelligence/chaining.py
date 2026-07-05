"""Deterministic ingestion + title-chaining engine.

This module does the work the spec assigns conceptually to the Ingestion and
Title-Auditor agents, but in plain Python so the pipeline runs and balances
*with or without* an LLM. The CrewAI agents (see :mod:`agents`) reason over and
refine what this engine produces; :mod:`verifier` is the final arbiter of the
math.

Chaining model
--------------
* A **conveyance** (WD, MD, QCD, DEED, ...) moves net mineral acres from a
  grantor to a grantee. Acres are deducted from the grantor and added to the
  grantee (rules 11 & 12 forbid over-conveyance / negative holdings).
* An **OGL** (oil & gas lease) does not move mineral acres -- it *burdens* the
  granting owner. Its OGL number is recorded and carried down beside every
  owner whose acres are subject to that lease (rules 7 & 10, the "Tract 1"
  pattern).
* An **ASSN** (assignment) transfers the leasehold/OGL between operators. It
  moves no mineral acres; it only re-associates the OGL number, and its
  conveyance type is normalized to ``ASSN`` (rules 9 & 8 -- never a book/page
  in the OGL field).

Only owners still holding acres at the end reach the Title Sheet (rules 4 & 5).
"""

from __future__ import annotations

import re
from collections import OrderedDict
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from schemas import (
    ACRE_QUANT,
    Conveyance,
    OwnerInterest,
    RunsheetInstrument,
    TractChainResult,
    quantize_acres,
)

# Conveyance-type tokens that actually move mineral acres.
_ACRE_MOVING = {"WD", "MD", "QCD", "DEED", "GWD", "SWD", "PROB", "DC", "CONVEY", "GIFT"}
# Lease token (burdens acres, carries an OGL number).
_LEASE_TOKENS = {"OGL", "LEASE", "OIL AND GAS LEASE", "O&G LEASE"}
# Assignment token (carries the OGL between operators; no acre movement).
_ASSIGN_TOKENS = {"ASSN", "ASSIGNMENT", "ASSIGN", "AOGL"}


# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------

# Flexible header -> canonical field mapping. Each canonical field lists the
# substrings we accept in a runsheet header (case-insensitive, non-alnum
# stripped) so we tolerate the many ways a runsheet labels its columns.
_HEADER_ALIASES: Dict[str, Tuple[str, ...]] = {
    "tract": ("tract", "trct"),
    "instrument_no": ("instrumentno", "instrument", "instno", "docno", "document"),
    "legal": ("legal", "legaldescription", "description", "land"),
    "grantor": ("grantor", "from", "assignor", "lessor"),
    "grantee": ("grantee", "to", "assignee", "lessee"),
    "conveyance": ("conveyance", "type", "instrumenttype", "doctype", "convtype"),
    "bk_pg": ("bkpg", "bookpage", "book", "recording", "bookpg", "volpage"),
    "date": ("date", "instrumentdate", "recorded", "recordeddate", "dated"),
    "gross_acres": ("grossacres", "acres", "gross", "netacres", "mineralacres"),
    "conveyed_interest": ("conveyedinterest", "interest", "fraction", "wi"),
    "ogl_ref": ("ogl", "oglno", "oglnumber", "leaseno", "leasenumber"),
    "notes": ("notes", "note", "remarks", "comment", "comments"),
}


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(h).lower())


def _map_columns(headers: List[str]) -> Dict[str, int]:
    """Map canonical field -> column index using the alias table.

    First exact-ish alias wins per field; a header is consumed by at most one
    field so ``book`` and ``bookpage`` do not both grab the same column.
    """
    normed = [_norm_header(h) for h in headers]
    used: set[int] = set()
    mapping: Dict[str, int] = {}
    for field, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            for i, nh in enumerate(normed):
                if i in used:
                    continue
                if nh == alias or (len(alias) >= 4 and alias in nh):
                    mapping[field] = i
                    used.add(i)
                    break
            if field in mapping:
                break
    return mapping


def ingest_runsheet(path: str | Path) -> List[RunsheetInstrument]:
    """Read a runsheet XLSX (or best-effort PDF) into RunsheetInstruments.

    XLSX is parsed with pandas. PDF support extracts text with pdfplumber /
    PyPDF2 if installed and looks for pipe/tab-delimited rows; if no PDF reader
    is available a clear ImportError is raised rather than returning garbage.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm", ".xls"):
        return _ingest_xlsx(path)
    if suffix == ".pdf":
        return _ingest_pdf(path)
    raise ValueError(f"Unsupported runsheet type: {suffix!r} ({path})")


def _ingest_xlsx(path: Path) -> List[RunsheetInstrument]:
    import pandas as pd

    # Read every sheet; concatenate rows that carry a tract value.
    sheets = pd.read_excel(path, sheet_name=None, dtype=str, header=0)
    out: List[RunsheetInstrument] = []
    row_counter = 0
    for _sheet_name, df in sheets.items():
        if df.empty:
            continue
        df = df.fillna("")
        mapping = _map_columns(list(df.columns))
        if "tract" not in mapping and "grantor" not in mapping:
            continue  # not a runsheet-shaped sheet
        for _, r in df.iterrows():
            def get(field: str) -> str:
                idx = mapping.get(field)
                if idx is None:
                    return ""
                return str(r.iloc[idx]).strip()

            tract = get("tract")
            grantor = get("grantor")
            grantee = get("grantee")
            if not (tract or grantor or grantee):
                continue
            inst = RunsheetInstrument(
                row=row_counter,
                tract=tract or "1",
                instrument_no=get("instrument_no"),
                legal=get("legal"),
                grantor=grantor,
                grantee=grantee,
                conveyance=get("conveyance"),
                bk_pg=get("bk_pg"),
                date=get("date"),
                gross_acres=get("gross_acres") or None,
                conveyed_interest=get("conveyed_interest") or None,
                ogl_ref=get("ogl_ref") or None,
                notes=get("notes"),
            )
            out.append(inst)
            row_counter += 1
    return out


def _ingest_pdf(path: Path) -> List[RunsheetInstrument]:
    try:
        import pdfplumber  # type: ignore
    except ImportError:  # pragma: no cover - optional dependency
        raise ImportError(
            "Reading a PDF runsheet requires 'pdfplumber'. Install it "
            "(pip install pdfplumber) or convert the runsheet to XLSX."
        )
    rows: List[List[str]] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                rows.extend(table)
    if not rows:
        raise ValueError(f"No tabular data found in PDF runsheet: {path}")
    headers = [str(c or "") for c in rows[0]]
    mapping = _map_columns(headers)
    out: List[RunsheetInstrument] = []
    for i, raw in enumerate(rows[1:]):
        cells = [str(c or "").strip() for c in raw]

        def get(field: str) -> str:
            idx = mapping.get(field)
            if idx is None or idx >= len(cells):
                return ""
            return cells[idx]

        if not any(cells):
            continue
        out.append(
            RunsheetInstrument(
                row=i,
                tract=get("tract") or "1",
                instrument_no=get("instrument_no"),
                legal=get("legal"),
                grantor=get("grantor"),
                grantee=get("grantee"),
                conveyance=get("conveyance"),
                bk_pg=get("bk_pg"),
                date=get("date"),
                gross_acres=get("gross_acres") or None,
                conveyed_interest=get("conveyed_interest") or None,
                ogl_ref=get("ogl_ref") or None,
                notes=get("notes"),
            )
        )
    return out


# --------------------------------------------------------------------------
# Conveyance normalization
# --------------------------------------------------------------------------


def classify(conv: str) -> str:
    """Bucket a raw conveyance token into MOVE / LEASE / ASSN / OTHER."""
    c = (conv or "").strip().upper()
    if c in _ASSIGN_TOKENS or "ASSIGN" in c:
        return "ASSN"
    if c in _LEASE_TOKENS or "LEASE" in c or c == "OGL":
        return "LEASE"
    if c in _ACRE_MOVING:
        return "MOVE"
    return "OTHER"


def to_conveyances(instruments: List[RunsheetInstrument]) -> List[Conveyance]:
    """Normalize runsheet instruments into ordered Conveyance objects.

    Assignments are forced to ``conv_type == "ASSN"`` (rule 9). Book/page is
    never promoted into the OGL field -- the OGL number comes only from a clean
    ``ogl_ref`` (rules 7 & 8).
    """
    out: List[Conveyance] = []
    for inst in instruments:
        kind = classify(inst.conveyance)
        conv_type = inst.conveyance.strip().upper()
        if kind == "ASSN":
            conv_type = "ASSN"
        out.append(
            Conveyance(
                tract=inst.tract,
                grantor=inst.grantor,
                grantee=inst.grantee,
                conv_type=conv_type,
                acres=inst.gross_acres if kind == "MOVE" else None,
                fraction=inst.conveyed_interest,
                ogl=inst.ogl_ref,
                instrument_no=inst.instrument_no,
                bk_pg=inst.bk_pg,
                date=inst.date,
                note=inst.notes,
            )
        )
    return out


# --------------------------------------------------------------------------
# Chaining
# --------------------------------------------------------------------------


def _sort_key(c: Conveyance) -> Tuple[int, str]:
    """Order conveyances by parsed date, falling back to original order."""
    d = _parse_date(c.date)
    return (0, d) if d else (1, "")


def _parse_date(s: str) -> str:
    """Return a sortable ISO-ish string for a date, or '' if unparseable."""
    if not s:
        return ""
    s = s.strip()
    m = re.match(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})", s)
    if m:
        mm, dd, yy = m.groups()
        yy = ("20" + yy) if len(yy) == 2 and int(yy) < 50 else ("19" + yy) if len(yy) == 2 else yy
        return f"{int(yy):04d}-{int(mm):02d}-{int(dd):02d}"
    m = re.match(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", s)
    if m:
        yy, mm, dd = m.groups()
        return f"{int(yy):04d}-{int(mm):02d}-{int(dd):02d}"
    return ""


def _resolve_tract_acres(
    tract: str,
    conveyances: List[Conveyance],
    tract_acres: Optional[Decimal],
) -> Tuple[Decimal, Optional[str]]:
    """Determine controlling tract acreage; note if it had to be assumed."""
    if tract_acres is not None:
        return quantize_acres(tract_acres), None
    # Fall back to the largest acre-moving conveyance as the tract gross.
    candidates = [c.acres for c in conveyances if c.acres is not None]
    if candidates:
        return max(candidates), None
    return (
        quantize_acres("0"),
        f"Tract {tract}: gross acreage not stated in runsheet; assumed 0 "
        "pending examiner input.",
    )


def chain_tract(
    tract: str,
    instruments: List[RunsheetInstrument],
    tract_acres: Optional[Decimal] = None,
) -> Tuple[TractChainResult, List[Conveyance]]:
    """Chain one tract to its final owners, carrying OGL numbers.

    Returns the :class:`TractChainResult` (final owners only) plus the ordered
    conveyance list so the verifier can independently detect over-conveyance.
    """
    tract_instruments = [i for i in instruments if str(i.tract) == str(tract)]
    conveyances = sorted(to_conveyances(tract_instruments), key=_sort_key)

    acres, acre_assumption = _resolve_tract_acres(tract, conveyances, tract_acres)
    review_flags: List[str] = []
    assumption_notes: List[str] = []
    if acre_assumption:
        assumption_notes.append(acre_assumption)
        review_flags.append(acre_assumption)

    # holdings: owner -> net acres. lease_of: owner -> set of OGL numbers that
    # currently burden that owner's interest. operator_of: OGL -> current
    # operator (updated by assignments).
    holdings: "OrderedDict[str, Decimal]" = OrderedDict()
    lease_of: Dict[str, "OrderedDict[str, None]"] = {}
    ogl_current_operator: Dict[str, str] = {}
    # Owners burdened by a lease whose OGL number the runsheet never stated.
    unknown_ogl_owners: set[str] = set()

    def credit(owner: str, amt: Decimal) -> None:
        owner = owner.strip()
        if not owner:
            return
        holdings[owner] = holdings.get(owner, Decimal("0")) + amt

    # Seed the root owner (earliest grantor) with the full tract acreage.
    if conveyances:
        root = conveyances[0].grantor.strip()
        if root:
            holdings[root] = acres
    if not holdings and acres > 0:
        holdings["UNDETERMINED ROOT OWNER"] = acres
        note = (
            f"Tract {tract}: no root conveyance found; seeded full "
            f"{acres} ac to an UNDETERMINED ROOT OWNER (assumption)."
        )
        assumption_notes.append(note)
        review_flags.append(note)

    for c in conveyances:
        kind = classify(c.conv_type)
        grantor = c.grantor.strip()
        grantee = c.grantee.strip()
        if kind == "MOVE" and c.acres is not None:
            have = holdings.get(grantor, Decimal("0"))
            move = c.acres
            if move - have > ACRE_QUANT:
                # Over-conveyance: cap at what's held and flag (rule 11). The
                # verifier will also independently catch this.
                flag = (
                    f"Tract {tract}: {grantor or '?'} conveyed {move} ac but "
                    f"held {have} ac -- capped to prevent negative ownership."
                )
                review_flags.append(flag)
                move = have
            holdings[grantor] = have - move
            credit(grantee, move)
            # Any lease burdening the grantor follows the acres to the grantee.
            if grantor in lease_of:
                lease_of.setdefault(grantee, OrderedDict()).update(lease_of[grantor])
            if grantor in unknown_ogl_owners and grantee:
                unknown_ogl_owners.add(grantee)
        elif kind == "LEASE":
            if c.ogl:
                lessor = grantor or grantee
                lease_of.setdefault(lessor, OrderedDict())[c.ogl] = None
                ogl_current_operator[c.ogl] = grantee
            else:
                lessor = grantor or grantee
                unknown_ogl_owners.add(lessor)
                flag = (
                    f"Tract {tract}: lease from {grantor or '?'} recorded at "
                    f"{c.bk_pg or 'unknown'} but no OGL number given -- OGL "
                    "left blank pending examiner (assumption)."
                )
                review_flags.append(flag)
                assumption_notes.append(flag)
        elif kind == "ASSN":
            # Assignment re-associates the OGL's operator; no acre movement and
            # never a book/page in the OGL field (rules 8 & 9).
            if c.ogl:
                ogl_current_operator[c.ogl] = grantee or ogl_current_operator.get(c.ogl, "")
        # OTHER: recorded for provenance but moves nothing.

    # Build final owners: only positive holdings survive (rules 4 & 5).
    final_owners: List[OwnerInterest] = []
    total_positive = sum((v for v in holdings.values() if v > 0), Decimal("0"))
    for owner, net in holdings.items():
        net_q = net.quantize(ACRE_QUANT)
        if net_q <= 0:
            continue
        ogls = list(lease_of.get(owner, {}).keys())
        ogl_str = ", ".join(ogls) if ogls else None
        wi = (net_q / total_positive) if total_positive > 0 else Decimal("0")
        unknown_lease = owner in unknown_ogl_owners and not ogls
        owner_note = ""
        if unknown_lease:
            owner_note = (
                f"{owner} is under a recorded lease whose OGL number was not "
                "stated in the runsheet; OGL left blank for examiner review."
            )
        final_owners.append(
            OwnerInterest(
                owner=owner,
                tract=tract,
                acres=net_q,
                wi=wi,
                ogl=ogl_str,
                conveyance="ASSN" if ogls and owner in ogl_current_operator.values() else "",
                leased=bool(ogls) or unknown_lease,
                is_assumption=unknown_lease,
                assumption_note=owner_note,
            )
        )

    result = TractChainResult(
        tract=tract,
        tract_acres=acres,
        final_owners=final_owners,
        balanced=False,  # set by the verifier in tasks.run_pipeline
        review_flags=review_flags,
        assumption_notes=assumption_notes,
        attempts=1,
    )
    return result, conveyances


def discover_tracts(instruments: List[RunsheetInstrument]) -> List[str]:
    """Return the distinct tract ids present, in first-seen order."""
    seen: "OrderedDict[str, None]" = OrderedDict()
    for i in instruments:
        seen.setdefault(str(i.tract), None)
    return list(seen.keys())
