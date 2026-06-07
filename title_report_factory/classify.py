"""Heuristic document-type classification and field extraction from raw text.

These are deliberately conservative regex/keyword heuristics meant as a first
pass behind (or instead of) an LLM extractor. Every value they return is
traceable to a literal text match; ambiguous cases return Unknown.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .models import Document, UNKNOWN

# Ordered most-specific first so e.g. "Assignment of Overriding Royalty" wins
# over a bare "Assignment".
DOC_TYPE_PATTERNS = [
    ("Assignment of Overriding Royalty", r"assignment of overriding royalty"),
    ("Assignment of Oil and Gas Lease", r"assignment of oil and gas lease|assignment of lease"),
    ("Oil and Gas Lease", r"oil and gas lease|oil & gas lease"),
    ("Partial Release", r"partial release"),
    ("Release", r"\brelease\b"),
    ("Ratification", r"ratification"),
    ("Mineral Deed", r"mineral deed"),
    ("Royalty Deed", r"royalty deed"),
    ("Warranty Deed", r"warranty deed"),
    ("Quitclaim Deed", r"quit ?claim deed"),
    ("Correction Instrument", r"correction (deed|instrument|assignment)"),
    ("Pooling Order", r"pooling order"),
    ("Spacing Order", r"spacing order"),
    ("Final Decree", r"final decree"),
    ("Journal Entry", r"journal entry"),
    ("Probate", r"\bprobate\b|order admitting"),
    ("Subordination", r"subordination"),
    ("Mortgage", r"\bmortgage\b|deed of trust"),
    ("Merger", r"\bmerger\b|articles of merger"),
    ("Memorandum", r"memorandum of"),
    ("Lis Pendens", r"lis pendens"),
    ("Tax Deed", r"tax deed"),
    ("Easement", r"\beasement\b"),
    ("Right of Way", r"right[- ]of[- ]way|right of way"),
    ("Affidavit", r"affidavit"),
]

INSTRUMENT_RE = re.compile(r"(?:instrument|document|reception|file)\s*(?:no\.?|#|number)\s*[:\-]?\s*([A-Z]?\d[\d\-]{3,})", re.I)
BOOK_PAGE_RE = re.compile(r"\b(?:book|vol(?:ume)?|bk)\.?\s*(\d+)[,\s]+(?:page|pg)\.?\s*(\d+)", re.I)
DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4}|[A-Z][a-z]+ \d{1,2},? \d{4})\b")


def classify_document(text: str) -> str:
    low = (text or "").lower()
    for label, pat in DOC_TYPE_PATTERNS:
        if re.search(pat, low):
            return label
    return UNKNOWN


def find_instrument_no(text: str) -> str:
    m = INSTRUMENT_RE.search(text or "")
    return m.group(1) if m else UNKNOWN


def find_book_page(text: str) -> str:
    m = BOOK_PAGE_RE.search(text or "")
    return f"{m.group(1)}/{m.group(2)}" if m else UNKNOWN


def find_dates(text: str) -> List[str]:
    return DATE_RE.findall(text or "")


def hits_tract(text: str, section: str, township: str, range_: str) -> bool:
    """True if the text plausibly references the subject Sec/Twp/Rng."""
    if not text:
        return False
    s = re.sub(r"[.,]", "", text.upper())
    sec_ok = bool(re.search(rf"\bSEC(?:TION)?\.?\s*0*{re.escape(section)}\b", s))
    twp = township.upper().replace(" ", "")
    rng = range_.upper().replace(" ", "")
    twp_ok = twp in s.replace(" ", "")
    rng_ok = rng in s.replace(" ", "")
    return sec_ok and twp_ok and rng_ok


def extract_document(text: str, source_ref: str, ocr_confidence: int,
                     section: str, township: str, range_: str) -> Document:
    """Build a Document from raw text using the heuristics above."""
    doc = Document(source_ref=source_ref, raw_text=text, ocr_confidence=ocr_confidence)
    doc.doc_type = classify_document(text)
    doc.instrument_no = find_instrument_no(text)
    doc.book_page = find_book_page(text)
    dates = find_dates(text)
    if dates:
        doc.execution_date = dates[0]
        doc.recording_date = dates[-1]
    relevant = hits_tract(text, section, township, range_)
    doc.relevance_confidence = 70 if relevant else 20
    doc.match_confidence = 55 if doc.doc_type != UNKNOWN else 15
    if not relevant:
        doc.notes = "Tract reference not detected in text; relevance to subject unconfirmed."
    return doc
