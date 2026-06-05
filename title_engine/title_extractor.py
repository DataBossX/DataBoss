"""
Title Extractor — parses raw OCR text into structured instrument fields.

Strategy:
  1. Regex patterns for all standard Oklahoma instrument fields.
  2. Optional AI extraction (Claude) for ambiguous/complex documents.
  3. Always: Section 27 detection, AOL detection, confidence scoring.
  4. NEVER fabricates values — uses UNKNOWN for anything unreadable.
"""

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)


# ── Target section ────────────────────────────────────────────────────────────

SECTION    = "27"
TOWNSHIP   = "11N"
RANGE      = "25W"
LEGAL_KEY  = "27-11N-25W"


# ── Instrument type normalisation ─────────────────────────────────────────────

ITYPE_MAP = {
    # Oil & gas
    "oil and gas lease": "Oil and Gas Lease",
    "oil & gas lease": "Oil and Gas Lease",
    "o&g lease": "Oil and Gas Lease",
    "memorandum of oil and gas lease": "Memorandum of Oil and Gas Lease",
    "memo of oil": "Memorandum of Oil and Gas Lease",
    # Assignments
    "assignment of oil and gas lease": "Assignment of Oil and Gas Lease",
    "assignment of oil": "Assignment of Oil and Gas Lease",
    "assignment": "Assignment",
    "partial assignment": "Partial Assignment",
    # Releases
    "release of oil and gas lease": "Release",
    "partial release": "Partial Release",
    "release": "Release",
    # Deeds
    "warranty deed": "Warranty Deed",
    "special warranty deed": "Warranty Deed",
    "mineral deed": "Mineral Deed",
    "quit claim deed": "Quit Claim Deed",
    "quitclaim deed": "Quit Claim Deed",
    "quit-claim deed": "Quit Claim Deed",
    # Probate / heirship
    "affidavit of heirship": "Affidavit of Heirship",
    "heirship affidavit": "Affidavit of Heirship",
    "administrator deed": "Administrator's Deed",
    "executor deed": "Executor's Deed",
    # OCC
    "pooling order": "Pooling Order",
    "unitization order": "Unitization Order",
    "spacing order": "Spacing Order",
    # Ratification / correction
    "ratification": "Ratification",
    "correction deed": "Correction Deed",
    "correction assignment": "Correction Assignment",
    # Finance
    "mortgage": "Mortgage",
    "deed of trust": "Deed of Trust",
    "ucc": "UCC Financing Statement",
}


def normalize_itype(raw: str) -> str:
    if not raw:
        return "UNKNOWN"
    key = raw.strip().lower()
    for k, v in ITYPE_MAP.items():
        if k in key:
            return v
    return raw.strip().title()


# ── Structured output ─────────────────────────────────────────────────────────

@dataclass
class ExtractedInstrument:
    # Identification
    instrument_type: str   = "UNKNOWN"
    instrument_number: str = "UNKNOWN"
    book: str              = "UNKNOWN"
    page: str              = "UNKNOWN"
    # Dates
    doc_date: str          = "UNKNOWN"
    effective_date: str    = "UNKNOWN"
    recording_date: str    = "UNKNOWN"
    # Parties
    grantor: List[str]     = field(default_factory=list)
    grantee: List[str]     = field(default_factory=list)
    lessor: List[str]      = field(default_factory=list)
    lessee: List[str]      = field(default_factory=list)
    assignor: List[str]    = field(default_factory=list)
    assignee: List[str]    = field(default_factory=list)
    # Legal
    legal_description: str = "UNKNOWN"
    section: str           = "UNKNOWN"
    township: str          = "UNKNOWN"
    range_: str            = "UNKNOWN"
    quarter_call: str      = "UNKNOWN"
    section_27: bool       = False
    aol_flag: bool         = False
    # Economics
    gross_acres: str       = "UNKNOWN"
    net_mineral_acres: str = "UNKNOWN"
    net_leasehold_acres: str = "UNKNOWN"
    royalty: str           = "UNKNOWN"
    primary_term: str      = "UNKNOWN"
    depth_clause: str      = "UNKNOWN"
    pugh_clause: str       = "UNKNOWN"
    working_interest: str  = "UNKNOWN"
    nri: str               = "UNKNOWN"
    # Chain
    lease_name: str        = "UNKNOWN"
    chain_from: str        = "UNKNOWN"
    chain_to: str          = "UNKNOWN"
    # Meta
    confidence: float      = 0.0
    needs_review: bool     = False
    notes: str             = ""
    extraction_method: str = "regex"

    def to_dict(self) -> dict:
        return asdict(self)


# ── Regex helpers ─────────────────────────────────────────────────────────────

_DATE_P = (
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"           # 01/15/2024
    r"|(\w+ \d{1,2},?\s*\d{4})"                      # January 15, 2024
    r"|(\d{4}-\d{2}-\d{2})"                          # 2024-01-15
)

_FRAC_P  = r"\b(\d{1,2}/\d{1,2}|\d+\.\d+\s*%)\b"
_ACRES_P = r"\b(\d[\d,\.]*)\s*(?:acres?|nma|nra|net mineral acres?|gross acres?)\b"
_BOOK_P  = r"[Bb]ook\s*([A-Z0-9\-]+)"
_PAGE_P  = r"[Pp]age\s*([0-9\-]+)"
_INST_P  = (r"(?:instrument\s*(?:no\.?|number|#)?\s*:?\s*)([A-Z0-9\-]+)"
            r"|(?:doc(?:ument)?\s*(?:no\.?|number|#)?\s*:?\s*)([A-Z0-9\-]+)")
_TERM_P  = r"\b(\d+(?:\s*-\s*year|\s*year)s?(?:\s+primary\s+term)?)"

_DEPTH_PATTERNS = [
    r"all depths",
    r"from the surface to",
    r"from .*? to .*? feet",
    r"wolfe(?:camp)?",
    r"mississippian",
    r"morrow",
    r"atoka",
    r"chester",
    r"meramec",
    r"deese",
    r"above\s+\d+\s*feet",
    r"below\s+\d+\s*feet",
]

_PUGH_PATTERNS = [
    r"pugh clause",
    r"horizontal pugh",
    r"vertical pugh",
    r"pugh-type",
    r"herein communitized",
    r"shall be released",
]

_AOL_PATTERNS = [
    r"and other lands",
    r"and other property",
    r"other lands",
    r"other acreage",
    r"additional lands",
    r"lands described in",
    r"all lands owned",
    r"all other interest",
]

_LEGAL_S27 = [
    r"\bsec(?:tion)?\s*27\b",
    r"\b27[-–]\s*11\s*[Nn][-–]\s*25\s*[Ww]\b",
    r"\bs\.?\s*27\b",
    r"\bsection\s+27\b",
    r"\b27\s+township\s+11",
]


def _re_find(pattern: str, text: str, group: int = 1, flags=re.IGNORECASE) -> Optional[str]:
    m = re.search(pattern, text, flags)
    if m:
        try:
            return m.group(group).strip()
        except IndexError:
            return m.group(0).strip()
    return None


def _re_find_all(pattern: str, text: str, flags=re.IGNORECASE) -> List[str]:
    return [m.strip() for m in re.findall(pattern, text, flags) if m.strip()]


# ── Legal description ─────────────────────────────────────────────────────────

def _extract_legal(text: str) -> str:
    """Grab the legal description block from the document text."""
    # Look for a block that starts with common legal desc markers
    patterns = [
        r"legal\s+description\s*:?\s*\n(.+?)(?:\n\n|\Z)",
        r"property\s+description\s*:?\s*\n(.+?)(?:\n\n|\Z)",
        r"(?:situate|located\s+in|lying\s+in)\s+(.+?)(?:\n\n|\Z)",
        r"((?:(?:N/?2|S/?2|E/?2|W/?2|NE/?4|NW/?4|SE/?4|SW/?4)[,\s]*)+(?:of\s+)?[Ss]ection\s+\d+.{0,200})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.DOTALL)
        if m:
            block = m.group(1).strip()
            # Clean up and limit to ~300 chars
            block = re.sub(r"\s+", " ", block)[:300]
            return block
    return "UNKNOWN"


def _detect_section_27(text: str) -> bool:
    for p in _LEGAL_S27:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def _detect_aol(text: str) -> bool:
    for p in _AOL_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def _extract_quarter(text: str) -> str:
    """Extract quarter/quarter-quarter calls."""
    pattern = r"\b((?:N/?2|S/?2|E/?2|W/?2|NE/?4|NW/?4|SE/?4|SW/?4)(?:\s+(?:N/?2|S/?2|E/?2|W/?2|NE/?4|NW/?4|SE/?4|SW/?4))?)\b"
    matches = re.findall(pattern, text, re.IGNORECASE)
    if matches:
        return ", ".join(dict.fromkeys(m.upper() for m in matches[:4]))
    return "UNKNOWN"


# ── Party extraction ──────────────────────────────────────────────────────────

def _extract_parties(text: str) -> dict:
    """Best-effort extraction of all party types from instrument text."""
    parties: dict = {k: [] for k in ("grantor", "grantee", "lessor", "lessee", "assignor", "assignee")}

    label_map = [
        (r"[Gg]rantor[s]?\s*:?\s*([^\n]{3,80})", "grantor"),
        (r"[Gg]rantee[s]?\s*:?\s*([^\n]{3,80})", "grantee"),
        (r"[Ll]essor[s]?\s*:?\s*([^\n]{3,80})", "lessor"),
        (r"[Ll]essee[s]?\s*:?\s*([^\n]{3,80})", "lessee"),
        (r"[Aa]ssignor[s]?\s*:?\s*([^\n]{3,80})", "assignor"),
        (r"[Aa]ssignee[s]?\s*:?\s*([^\n]{3,80})", "assignee"),
    ]
    for pat, key in label_map:
        for m in re.finditer(pat, text):
            name = m.group(1).strip().rstrip(",;")
            if name and name.lower() not in ("hereinafter", "referred", "called"):
                parties[key].append(name)

    # Cross-populate: lessor→grantor, lessee→grantee
    if parties["lessor"] and not parties["grantor"]:
        parties["grantor"] = parties["lessor"]
    if parties["lessee"] and not parties["grantee"]:
        parties["grantee"] = parties["lessee"]
    if parties["assignor"] and not parties["grantor"]:
        parties["grantor"] = parties["assignor"]
    if parties["assignee"] and not parties["grantee"]:
        parties["grantee"] = parties["assignee"]

    return parties


# ── Main extraction ───────────────────────────────────────────────────────────

def extract_from_text(
    text: str,
    *,
    known_book: str = None,
    known_page: str = None,
    known_itype: str = None,
    known_inst_num: str = None,
    known_recording_date: str = None,
    known_grantor: List[str] = None,
    known_grantee: List[str] = None,
) -> ExtractedInstrument:
    """
    Extract all fields from OCR text.
    Pre-populated values from the search index take priority.
    """
    e = ExtractedInstrument()
    text_lc = text.lower()

    # ── Instrument type ───────────────────────────────────────────────────────
    itype_raw = known_itype or _re_find(
        r"^((?:Oil and Gas Lease|Assignment|Release|Warranty Deed|Mineral Deed|"
        r"Quit Claim Deed|Affidavit|Ratification|Correction|Mortgage|Pooling Order|"
        r"Memorandum of Oil and Gas|Partial Release)[^\.]*)",
        text, flags=re.IGNORECASE | re.MULTILINE) or ""
    e.instrument_type = normalize_itype(itype_raw)

    # ── Book / Page ───────────────────────────────────────────────────────────
    e.book = known_book or _re_find(_BOOK_P, text) or "UNKNOWN"
    e.page = known_page or _re_find(_PAGE_P, text) or "UNKNOWN"

    # ── Instrument number ─────────────────────────────────────────────────────
    raw_inst = _re_find(_INST_P, text)
    if isinstance(raw_inst, tuple):
        raw_inst = next((x for x in raw_inst if x), None)
    e.instrument_number = known_inst_num or raw_inst or "UNKNOWN"

    # ── Dates ─────────────────────────────────────────────────────────────────
    all_dates = re.findall(_DATE_P, text, re.IGNORECASE)
    flat_dates = [x for group in all_dates for x in group if x]
    e.doc_date       = flat_dates[0] if flat_dates else "UNKNOWN"
    e.recording_date = known_recording_date or (flat_dates[1] if len(flat_dates) > 1 else "UNKNOWN")

    eff_m = re.search(r"effective\s+(?:date\s*:?\s*)?(.{4,30}?)(?:\n|,)", text, re.IGNORECASE)
    e.effective_date = eff_m.group(1).strip() if eff_m else "UNKNOWN"

    # ── Parties ───────────────────────────────────────────────────────────────
    parties = _extract_parties(text)
    e.grantor   = known_grantor or parties["grantor"]
    e.grantee   = known_grantee or parties["grantee"]
    e.lessor    = parties["lessor"]
    e.lessee    = parties["lessee"]
    e.assignor  = parties["assignor"]
    e.assignee  = parties["assignee"]

    # ── Legal description ─────────────────────────────────────────────────────
    e.legal_description = _extract_legal(text)
    e.quarter_call      = _extract_quarter(text)
    e.section_27        = _detect_section_27(text)
    e.aol_flag          = _detect_aol(text)
    e.section           = SECTION  if e.section_27 else "UNKNOWN"
    e.township          = TOWNSHIP if e.section_27 else "UNKNOWN"
    e.range_            = RANGE    if e.section_27 else "UNKNOWN"

    # ── Economics ─────────────────────────────────────────────────────────────
    # Royalty
    royalties = _re_find_all(_FRAC_P, text)
    e.royalty = royalties[0] if royalties else "UNKNOWN"

    # Acres
    acres_m = re.search(_ACRES_P, text, re.IGNORECASE)
    e.gross_acres = acres_m.group(1).replace(",", "") if acres_m else "UNKNOWN"

    # Primary term
    term_m = re.search(_TERM_P, text, re.IGNORECASE)
    e.primary_term = term_m.group(1) if term_m else "UNKNOWN"

    # Depth clause
    depth_found = any(re.search(p, text, re.IGNORECASE) for p in _DEPTH_PATTERNS)
    if depth_found:
        dm = next((re.search(p, text, re.IGNORECASE) for p in _DEPTH_PATTERNS
                   if re.search(p, text, re.IGNORECASE)), None)
        e.depth_clause = dm.group(0).strip() if dm else "depth restriction present"
    else:
        e.depth_clause = "UNKNOWN"

    # Pugh clause
    pugh_found = any(re.search(p, text, re.IGNORECASE) for p in _PUGH_PATTERNS)
    e.pugh_clause = "YES — see document" if pugh_found else "UNKNOWN"

    # ── Confidence ────────────────────────────────────────────────────────────
    known_fields = [
        e.instrument_type != "UNKNOWN",
        e.instrument_number != "UNKNOWN",
        e.book != "UNKNOWN" or e.page != "UNKNOWN",
        bool(e.grantor),
        bool(e.grantee),
        e.section_27,
        e.doc_date != "UNKNOWN",
    ]
    e.confidence = round(sum(known_fields) / len(known_fields), 2)
    e.needs_review = (e.confidence < 0.5 or "[OCR FAILED" in text)
    e.extraction_method = "regex"

    return e


# ── AI-enhanced extraction (Claude) ──────────────────────────────────────────

AI_PROMPT = """You are an expert Oklahoma land title examiner. Analyze this instrument text and extract ALL fields.

SECTION OF INTEREST: Section {section}, Township {township}, Range {range_}.

Return ONLY valid JSON with exactly these keys:
{{
  "instrument_type": "string",
  "instrument_number": "string or UNKNOWN",
  "book": "string or UNKNOWN",
  "page": "string or UNKNOWN",
  "doc_date": "YYYY-MM-DD or UNKNOWN",
  "effective_date": "YYYY-MM-DD or UNKNOWN",
  "recording_date": "YYYY-MM-DD or UNKNOWN",
  "grantor": ["array of names"],
  "grantee": ["array of names"],
  "lessor": ["array"],
  "lessee": ["array"],
  "assignor": ["array"],
  "assignee": ["array"],
  "legal_description": "full legal desc or UNKNOWN",
  "section": "string or UNKNOWN",
  "township": "string or UNKNOWN",
  "range_": "string or UNKNOWN",
  "quarter_call": "string or UNKNOWN",
  "section_27": true/false,
  "aol_flag": true/false,
  "gross_acres": "string or UNKNOWN",
  "net_mineral_acres": "string or UNKNOWN",
  "royalty": "fraction like 3/16 or UNKNOWN",
  "primary_term": "e.g. 3 years or UNKNOWN",
  "depth_clause": "description or UNKNOWN",
  "pugh_clause": "YES/NO/UNKNOWN",
  "lease_name": "string or UNKNOWN",
  "notes": "any unusual clauses or concerns",
  "confidence": 0.0-1.0,
  "needs_review": true/false
}}

CRITICAL RULES:
- Never invent data. If unsupported, write UNKNOWN.
- section_27 = true ONLY if Section {section} T{township} R{range_} is expressly described.
- aol_flag = true if "other lands" or similar language includes acreage beyond Section {section}.

Document text:
{text}
"""


def extract_with_claude(
    text: str,
    api_key: str,
    *,
    known_book: str = None,
    known_page: str = None,
    known_itype: str = None,
    known_inst_num: str = None,
    known_recording_date: str = None,
    known_grantor: List[str] = None,
    known_grantee: List[str] = None,
) -> ExtractedInstrument:
    """AI-enhanced extraction using Claude."""
    import anthropic, json as _json

    client = anthropic.Anthropic(api_key=api_key)
    prompt = AI_PROMPT.format(
        section=SECTION, township=TOWNSHIP, range_=RANGE,
        text=text[:8000]  # token budget
    )
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = _json.loads(raw)
    except Exception:
        log.warning("Claude JSON parse failed, falling back to regex")
        return extract_from_text(
            text, known_book=known_book, known_page=known_page,
            known_itype=known_itype, known_inst_num=known_inst_num,
            known_recording_date=known_recording_date,
            known_grantor=known_grantor, known_grantee=known_grantee,
        )

    def _s(k): return str(data.get(k) or "UNKNOWN").strip()
    def _l(k):
        v = data.get(k, [])
        return v if isinstance(v, list) else [str(v)] if v else []

    e = ExtractedInstrument(
        instrument_type    = normalize_itype(_s("instrument_type")),
        instrument_number  = known_inst_num or _s("instrument_number"),
        book               = known_book     or _s("book"),
        page               = known_page     or _s("page"),
        doc_date           = _s("doc_date"),
        effective_date     = _s("effective_date"),
        recording_date     = known_recording_date or _s("recording_date"),
        grantor            = known_grantor or _l("grantor"),
        grantee            = known_grantee or _l("grantee"),
        lessor             = _l("lessor"),
        lessee             = _l("lessee"),
        assignor           = _l("assignor"),
        assignee           = _l("assignee"),
        legal_description  = _s("legal_description"),
        section            = _s("section"),
        township           = _s("township"),
        range_             = _s("range_"),
        quarter_call       = _s("quarter_call"),
        section_27         = bool(data.get("section_27", False)),
        aol_flag           = bool(data.get("aol_flag",    False)),
        gross_acres        = _s("gross_acres"),
        net_mineral_acres  = _s("net_mineral_acres"),
        royalty            = _s("royalty"),
        primary_term       = _s("primary_term"),
        depth_clause       = _s("depth_clause"),
        pugh_clause        = _s("pugh_clause"),
        lease_name         = _s("lease_name"),
        notes              = _s("notes"),
        confidence         = float(data.get("confidence", 0.5)),
        needs_review       = bool(data.get("needs_review", False)),
        extraction_method  = "claude",
    )
    return e
