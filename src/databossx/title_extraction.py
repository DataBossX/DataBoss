"""Extract conveyance facts from raw title-document text.

The chain stage normally reads a pre-structured OGL register. This module lets
the pipeline also work on **loose documents** -- deeds, assignments, leases,
patents as text (or, with OCR backends, PDFs/scans) -- by pulling the
conveyance facts an examiner needs: grantor, grantee, instrument number,
conveyed interest, legal description, doc type, and gross acres.

It is a deterministic, **cursory** first pass in the no-fabrication tradition of
the rest of the system: every field is nullable, unfound ⇒ blank, and the legal
description is normalized through :mod:`databossx.legal` so the same tract reads
consistently across documents. Nothing is guessed to complete a record.

Aligns with the #56 bounded-port slice S2 (document intelligence), built
natively on the canonical package.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .legal import canonical_key

# grantor-side and grantee-side role synonyms (assignor→grantor, lessee→grantee…)
_GRANTOR_ROLES = ("grantor", "assignor", "lessor")
_GRANTEE_ROLES = ("grantee", "assignee", "lessee")

_DOC_TYPES = [
    (r"mineral\s+deed", "Mineral Deed"),
    (r"warranty\s+deed", "Warranty Deed"),
    (r"quit\s*claim\s+deed", "Quitclaim Deed"),
    (r"deed", "Deed"),
    (r"assignment", "Assignment"),
    (r"oil\s+and\s+gas\s+lease|o&g\s+lease|lease", "Lease"),
    (r"patent", "Patent"),
    (r"probate|last\s+will|estate\s+of", "Probate"),
]

_INSTR = re.compile(
    r"(?:instrument|inst\.?|document|doc\.?|reception|entry)\s*"
    r"(?:no\.?|number|#)?\s*[:#]?\s*([0-9][0-9\-]{2,20})", re.I)
_BOOKPAGE = re.compile(r"\bbook\s*([0-9]+)\s*page\s*([0-9]+)", re.I)
_ACRES = re.compile(r"containing\s+([\d,]+(?:\.\d+)?)\s*acres?", re.I)
# "undivided 1/2", "an undivided 1/2 mineral interest", "1/2 interest"
_INT_UNDIV = re.compile(r"undivided\s+(\d+\s*/\s*\d+|\d+(?:\.\d+)?\s*%)", re.I)
_INT_BARE = re.compile(r"(\d+\s*/\s*\d+)\s+(?:mineral\s+|royalty\s+|working\s+)?interest", re.I)
_DATE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2})\b|\b(\d{1,2}/\d{1,2}/\d{2,4})\b", re.I)


def _party(text: str, roles) -> Optional[str]:
    """Find 'ROLE: Name' near a role keyword (deterministic; no guessing)."""
    for role in roles:
        m = re.search(rf"\b{role}\b\s*[:\-]\s*([^\n]{{2,90}})", text, re.I)
        if not m:
            m = re.search(rf"\b{role}\b\s+(?:is|are|shall\s+be)\s+([A-Z][^\n]{{2,90}})",
                          text, re.I)
        if m:
            cand = re.sub(r"\s+", " ", m.group(1)).strip()
            cand = re.split(
                r"\b(?:grantee|assignee|lessee|hereinafter|whose\s+address|,?\s+and\s+)\b",
                cand, flags=re.I)[0]
            cand = cand.strip(" ,:-.")
            if 2 <= len(cand) <= 90:
                return cand
    return None


@dataclass
class ConveyanceFact:
    source: str = ""
    doc_type: str = ""
    grantor: str = ""
    grantee: str = ""
    instrument_number: str = ""
    conveyed_interest: str = ""
    legal_description: str = ""
    gross_acres: str = ""
    instrument_date: str = ""
    review_flags: List[str] = field(default_factory=list)

    @property
    def has_min_fields(self) -> bool:
        return bool((self.grantor or self.grantee)
                    and (self.instrument_number or self.legal_description))


def extract_conveyance(text: str, source: str = "") -> ConveyanceFact:
    """Extract a single conveyance's facts from ``text`` (best-effort, cursory)."""
    t = str(text or "")
    fact = ConveyanceFact(source=source)

    for pat, label in _DOC_TYPES:
        if re.search(pat, t, re.I):
            fact.doc_type = label
            break

    fact.grantor = _party(t, _GRANTOR_ROLES) or ""
    fact.grantee = _party(t, _GRANTEE_ROLES) or ""

    m = _INSTR.search(t)
    if m:
        fact.instrument_number = m.group(1).strip()
    elif (bp := _BOOKPAGE.search(t)):
        fact.instrument_number = f"BK{bp.group(1)}-PG{bp.group(2)}"

    mi = _INT_UNDIV.search(t) or _INT_BARE.search(t)
    if mi:
        fact.conveyed_interest = re.sub(r"\s+", "", mi.group(1))

    # Legal: normalize to a canonical S/T/R key when parseable (consistent tract).
    key = canonical_key(t)
    if key:
        fact.legal_description = key
    else:
        # keep a raw legal span if one is obviously present
        lm = re.search(r"(section\b[^\n.]{0,80})", t, re.I)
        if lm:
            fact.legal_description = re.sub(r"\s+", " ", lm.group(1)).strip(" ,.")

    am = _ACRES.search(t)
    if am:
        fact.gross_acres = am.group(1).replace(",", "")

    dm = _DATE.search(t)
    if dm:
        fact.instrument_date = dm.group(1) or dm.group(2)

    # Review flags for the high-value fields the pass could not read.
    if not fact.conveyed_interest:
        fact.review_flags.append("conveyed interest not found")
    if not fact.legal_description:
        fact.review_flags.append("legal description not found")
    if not fact.instrument_number:
        fact.review_flags.append("instrument number not found")
    return fact


def conveyance_to_ogl(fact: ConveyanceFact):
    """Convert a :class:`ConveyanceFact` into a horizon ``OGLRecord``."""
    from horizon.chaining import OGLRecord
    return OGLRecord(
        instrument_number=fact.instrument_number,
        grantor=fact.grantor,
        grantee=fact.grantee,
        conveyed_interest=fact.conveyed_interest,
        legal_description=fact.legal_description,
        doc_type=fact.doc_type,
        instrument_date=fact.instrument_date,
        gross_acres=fact.gross_acres,
    )


def extract_conveyances(texts: Dict[str, str]) -> List:
    """Extract OGL records from a ``{source: text}`` map of documents.

    Records are ordered by instrument date then instrument number so the chain
    walks in a stable order. Documents with too few fields are skipped (their
    text stays available as evidence; nothing is fabricated to include them).
    """
    facts = [extract_conveyance(text, source=src) for src, text in texts.items()]
    usable = [f for f in facts if f.has_min_fields]
    usable.sort(key=lambda f: (f.instrument_date or "", f.instrument_number or ""))
    return [conveyance_to_ogl(f) for f in usable]


def conveyance_notes(ogl_records: List) -> List:
    """Self-referencing runsheet notes for document-extracted conveyances.

    In the document path each instrument *is* its own evidence, so it references
    itself in the runsheet -- otherwise horizon's OGL↔runsheet cross-reference
    would (correctly, for a workbook) flag every unreferenced instrument as a
    chain break.
    """
    from horizon.chaining import RunsheetNote
    notes = []
    for r in ogl_records:
        if r.instrument_number:
            notes.append(RunsheetNote(
                instrument_number=r.instrument_number,
                note="conveyance extracted from source document",
                legal_description=r.legal_description))
    return notes
