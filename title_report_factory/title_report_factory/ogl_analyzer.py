"""Analyze oil & gas leases and their assignments into OGL rows.

Produces the rows for the OGL sheet. HBP (held-by-production) status is only
asserted when supporting well/production data is supplied -- otherwise it is
explicitly flagged as undetermined.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from .models import Document
from .utils import NEEDS_REVIEW, NOT_FOUND, UNKNOWN


def build_ogl_rows(docs: List[Document], well_rows: List[dict]) -> List[dict]:
    leases = [d for d in docs if "lease" in d.document_type.lower()
              and "assignment" not in d.document_type.lower()]
    assignments = [d for d in docs if "assignment" in d.document_type.lower()]

    have_production = any(
        str(w.get("Status", "")).lower() in ("active", "producing")
        or w.get("Last Production Found") not in (None, "", NOT_FOUND, UNKNOWN)
        for w in well_rows
    )

    rows: List[dict] = []
    for i, d in enumerate(leases, start=1):
        related_assign = [a for a in assignments
                          if _shares_party(a, d)]
        hbp = ("Possible HBP -- production found in section; verify lease/unit"
               if have_production else
               "HBP undetermined -- no production data; do NOT assume held by production")
        rows.append({
            "Lease No.": i,
            "Lessor": "; ".join(d.grantors) or NOT_FOUND,
            "Lessee": "; ".join(d.grantees) or NOT_FOUND,
            "Lease Date": d.execution_date or NOT_FOUND,
            "Effective Date": d.effective_date or NOT_FOUND,
            "Recording Date": d.recording_date or NOT_FOUND,
            "Instrument No.": d.instrument_no or NOT_FOUND,
            "Book/Page": d.book_page or NOT_FOUND,
            "Legal Description": d.legal.raw or NOT_FOUND,
            "Gross Acres": d.gross_acres or UNKNOWN,
            "Net Acres": d.net_acres or UNKNOWN,
            "Royalty": d.royalty or UNKNOWN,
            "Primary Term": _extract_term(d) or UNKNOWN,
            "Extension/Option": NEEDS_REVIEW,
            "Assignments": "; ".join(
                f"{Path(a.source_file).name} ({a.instrument_no or 'no inst#'})"
                for a in related_assign) or "None found",
            "Current Lessee/Operator if Determinable": _current_lessee(d, related_assign, well_rows),
            "HBP Notes": hbp,
            "Source": Path(d.source_file).name,
            "Confidence": _conf(d),
        })
    return rows


def _shares_party(a: Document, lease: Document) -> bool:
    names = {n.lower() for n in (lease.grantees + lease.grantors)}
    other = {n.lower() for n in (a.grantors + a.grantees)}
    return bool(names & other)


def _extract_term(d: Document) -> str:
    if d.lease_terms and "primary term" in d.lease_terms.lower():
        for part in d.lease_terms.split(";"):
            if "primary term" in part.lower():
                return part.strip()
    return ""


def _current_lessee(lease: Document, assignments: List[Document],
                    well_rows: List[dict]) -> str:
    # If an operator is known from well data, surface it but flag the assumption.
    operators = [w.get("Operator") for w in well_rows
                 if w.get("Operator") not in (None, "", UNKNOWN, NOT_FOUND)]
    if assignments:
        last = assignments[-1]
        return (f"{'; '.join(last.grantees) or UNKNOWN} (per last assignment; verify)")
    if operators:
        return f"{operators[0]} (per well data; lessee linkage unverified)"
    return NEEDS_REVIEW


def _conf(d: Document) -> int:
    base = 40
    if d.instrument_no:
        base += 15
    if d.grantors and d.grantees:
        base += 20
    if d.legal.section:
        base += 15
    return min(base, 90)
