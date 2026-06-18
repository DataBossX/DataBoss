"""
domain.py
=========
Title/runsheet domain intelligence. The generic AI extraction doesn't know that
this project is about tract 31-12N-24W in Roger Mills County, that a section
number must be 1-36, or that a "filed date" in the year 2099 is nonsense. This
module adds that knowledge as cheap, deterministic sanity checks that flag
suspicious extractions for human review WITHOUT ever rewriting data.

It also parses the Public Land Survey System (PLSS) location out of a legal
description (Section / Township / Range / quarter calls) and cross-checks it
against the tract implied by the workbook filename and the row's own S/T/R
columns. Mismatches are exactly the kind of error a human reviewer wants surfaced.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field

# e.g. "31-12N-24W"  (Section - Township - Range). Trailing lookahead rather
# than \b so it still matches when followed by "_" (a word char), as in
# "31-12N-24W_Roger_Mills.xlsx".
_TRACT_RE = re.compile(
    r"(?<![A-Za-z0-9])(\d{1,2})\s*[-_ ]\s*(\d{1,3}[NS])\s*[-_ ]\s*(\d{1,3}[EW])"
    r"(?![A-Za-z0-9])", re.I)
_SECTION_RE = re.compile(r"\bsec(?:tion)?\.?\s*(\d{1,2})\b", re.I)
_TOWNSHIP_RE = re.compile(r"\bt(?:wp|ownship)?\.?\s*(\d{1,3})\s*([NS])\b", re.I)
_RANGE_RE = re.compile(r"\br(?:ge|ng|ange)?\.?\s*(\d{1,3})\s*([EW])\b", re.I)
# bare "12N" / "24W" tokens (common in headers/short legals)
_TWP_BARE = re.compile(r"\b(\d{1,3})\s*([NS])\b", re.I)
_RNG_BARE = re.compile(r"\b(\d{1,3})\s*([EW])\b", re.I)
_QUARTER_RE = re.compile(r"\b([NS][EW]/?4|[NSEW]/?2)\b", re.I)

# Document types we recognize (used only to note unfamiliar types, never to edit).
KNOWN_DOC_TYPES = {
    "deed", "warranty deed", "quitclaim deed", "quit claim deed", "mineral deed",
    "oil and gas lease", "lease", "mortgage", "release", "assignment",
    "easement", "right of way", "affidavit", "probate", "will", "judgment",
    "lien", "memorandum", "ratification", "correction", "power of attorney",
    "death certificate", "patent",
}


@dataclass
class Plss:
    sections: list[str] = field(default_factory=list)
    township: str | None = None
    range: str | None = None
    quarters: list[str] = field(default_factory=list)

    def as_tract(self) -> str | None:
        if self.sections and self.township and self.range:
            return f"{self.sections[0]}-{self.township}-{self.range}".upper()
        return None


def parse_tract(text: str | None) -> str | None:
    """Pull a 'SS-TTTd-RRRd' tract id from text (e.g. a workbook filename)."""
    if not text:
        return None
    m = _TRACT_RE.search(text)
    if not m:
        return None
    return f"{int(m.group(1))}-{m.group(2).upper()}-{m.group(3).upper()}"


def parse_legal(text: str | None) -> Plss:
    """Best-effort parse of Section/Township/Range/quarter calls from a legal."""
    p = Plss()
    if not text:
        return p
    s = str(text)
    p.sections = [str(int(x)) for x in _SECTION_RE.findall(s)]
    tm = _TOWNSHIP_RE.search(s) or _TWP_BARE.search(s)
    if tm:
        p.township = f"{int(tm.group(1))}{tm.group(2).upper()}"
    rm = _RANGE_RE.search(s) or _RNG_BARE.search(s)
    if rm:
        p.range = f"{int(rm.group(1))}{rm.group(2).upper()}"
    p.quarters = [q.upper().replace("/", "") for q in _QUARTER_RE.findall(s)]
    return p


def _norm_twp(v) -> str | None:
    if v in (None, ""):
        return None
    m = re.search(r"(\d{1,3})\s*([NS])", str(v), re.I)
    return f"{int(m.group(1))}{m.group(2).upper()}" if m else str(v).strip().upper()


def _norm_rng(v) -> str | None:
    if v in (None, ""):
        return None
    m = re.search(r"(\d{1,3})\s*([EW])", str(v), re.I)
    return f"{int(m.group(1))}{m.group(2).upper()}" if m else str(v).strip().upper()


def audit(extracted: dict, existing: dict, tract: str | None = None,
          today: _dt.date | None = None) -> list[str]:
    """
    Return a list of human-readable warning strings about the extracted record.
    Never mutates anything. An empty list means "no domain concerns".
    """
    today = today or _dt.date.today()
    warns: list[str] = []

    # --- section range -----------------------------------------------------
    sec = extracted.get("section")
    if sec not in (None, ""):
        try:
            n = int(re.sub(r"\D", "", str(sec)) or 0)
            if not (1 <= n <= 36):
                warns.append(f"section {sec} out of range 1-36")
        except ValueError:
            warns.append(f"section '{sec}' not numeric")

    # --- dates: not future, not absurd ------------------------------------
    for dfield in ("filed_date", "recorded_date", "effective_date"):
        val = extracted.get(dfield)
        if not val:
            continue
        try:
            d = _dt.date.fromisoformat(str(val)[:10])
        except ValueError:
            continue  # non-ISO already handled upstream
        if d > today:
            warns.append(f"{dfield} {val} is in the future")
        elif d.year < 1800:
            warns.append(f"{dfield} {val} is implausibly old")

    # --- document type recognition ----------------------------------------
    dt = (extracted.get("document_type") or "").strip().lower()
    if dt and dt not in KNOWN_DOC_TYPES and not any(
            k in dt for k in KNOWN_DOC_TYPES):
        warns.append(f"unfamiliar document type '{extracted.get('document_type')}'")

    # --- PLSS cross-checks -------------------------------------------------
    legal = parse_legal(extracted.get("legal_description"))
    ex_sec = extracted.get("section")
    if legal.sections and ex_sec not in (None, ""):
        try:
            if str(int(re.sub(r"\D", "", str(ex_sec)))) not in legal.sections:
                warns.append(
                    f"section column ({ex_sec}) not found in legal description "
                    f"sections {legal.sections}")
        except ValueError:
            pass

    ex_twp = _norm_twp(extracted.get("township"))
    if legal.township and ex_twp and legal.township != ex_twp:
        warns.append(f"township column ({ex_twp}) != legal township "
                     f"({legal.township})")
    ex_rng = _norm_rng(extracted.get("range"))
    if legal.range and ex_rng and legal.range != ex_rng:
        warns.append(f"range column ({ex_rng}) != legal range ({legal.range})")

    # --- tract consistency (filename implies the project tract) -----------
    if tract:
        parts = tract.split("-")
        if len(parts) == 3:
            _, t_twp, t_rng = parts
            lt = legal.township or ex_twp
            lr = legal.range or ex_rng
            if lt and lt != t_twp.upper():
                warns.append(
                    f"township {lt} differs from project tract {t_twp}")
            if lr and lr != t_rng.upper():
                warns.append(f"range {lr} differs from project tract {t_rng}")

    return warns
