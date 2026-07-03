"""Parse an instrument (from OCR text) or a county Unplatted-Legal-Index page into
structured records: grantor, grantee, doc type, dates, book/page, legal, and — when the
granting language is present — the conveyed or reserved fraction.

Two entry points:
  parse_index_page(text)   -> [record, ...]   (the typed county index; strong, reliable)
  parse_instrument(text)   -> record          (a single recorded document image)
"""
from __future__ import annotations
import re
from fractions import Fraction

TYPE_TOKENS = ["REL MTG", "O/L", "OIL", "ASGT", "QCD", "MD", "AFF", "WD", "SWD",
               "ROW", "EAS", "PR", "AOH", "MTG", "REL", "SUB", "RAT", "CORR",
               "GWD", "ORD", "DEED", "PROB", "CONV", "ASSGN", "DECREE"]

TITLE_TYPES = {"O/L", "OIL", "ASGT", "MD", "QCD", "WD", "SWD", "GWD", "DEED",
               "PROB", "CONV", "ASSGN", "DECREE", "AFF", "AOH", "PR", "RAT", "CORR", "ORD"}
EXCLUDED_TYPES = {"REL MTG", "MTG", "REL", "ROW", "EAS", "SUB"}


def parse_index_page(text: str) -> list[dict]:
    recs = []
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r"\s*31\s+(\d{6})\s+(.*)", ln)
        if not m:
            continue
        doc, rest = m.group(1), m.group(2)
        typ, tpos = "", None
        for t in TYPE_TOKENS:
            idx = rest.find(" " + t + " ")
            if idx > 0 and (tpos is None or idx < tpos):
                tpos, typ = idx, t
        parties = rest[:tpos].strip() if tpos else rest.strip()
        bk = (re.search(r"(\d{6})\s*$", ln) or [None, ""])
        book = bk.group(1) if hasattr(bk, "group") else ""
        page = legal = ""
        if i + 1 < len(lines):
            nl = lines[i + 1]
            pm = re.search(r"(\d{4})\s*$", nl)
            page = pm.group(1) if pm else ""
            lm = re.search(r"R24W\s*(.*)", nl)
            legal = lm.group(1).strip() if lm else ""
        recs.append(dict(doc=doc, type=typ, parties=parties, book=book,
                         page=page, legal=legal, excluded=typ in EXCLUDED_TYPES))
    return recs


_FRAC_RX = re.compile(
    r"(?:an?\s+)?(?:undivided\s+)?"
    r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*"
    r"(?:interest|of|\(|in|mineral)", re.I)
_NMA_RX = re.compile(r"(\d+(?:\.\d+)?)\s*(?:net\s+)?(?:mineral\s+)?acres", re.I)
_RESERVE_RX = re.compile(r"(reserv|except|retain)", re.I)


def parse_instrument(text: str) -> dict:
    """Best-effort extraction of the conveyed interest from a single recorded document.
    Returns {type, grantors, grantees, fraction, nma, reserved, royalty, raw_hits}.
    Conservative: returns None fields when language is not unambiguous."""
    rec: dict = {"fraction": None, "nma": None, "reserved": False,
                 "royalty": None, "raw_hits": []}
    up = text.upper()
    for t, label in [("QUIT CLAIM", "QCD"), ("MINERAL DEED", "MD"),
                     ("WARRANTY DEED", "WD"), ("OIL AND GAS LEASE", "O/L"),
                     ("ASSIGNMENT", "ASGT"), ("MORTGAGE", "MTG"),
                     ("RELEASE", "REL"), ("EASEMENT", "EAS"),
                     ("RIGHT OF WAY", "ROW"), ("RIGHT-OF-WAY", "ROW")]:
        if t in up:
            rec["type"] = label
            break
    m = _FRAC_RX.search(text)
    if m:
        try:
            fr = Fraction(str(m.group(1))).limit_denominator() / Fraction(str(m.group(2))).limit_denominator()
            rec["fraction"] = float(fr)
            rec["raw_hits"].append(m.group(0).strip())
        except (ZeroDivisionError, ValueError):
            pass
    m = _NMA_RX.search(text)
    if m:
        rec["nma"] = float(m.group(1))
        rec["raw_hits"].append(m.group(0).strip())
    rec["reserved"] = bool(_RESERVE_RX.search(text))
    rm = re.search(r"(\d+/\d+)\s*(?:th|nd|rd)?\s*royalty", text, re.I)
    if rm:
        try:
            rec["royalty"] = float(Fraction(rm.group(1)))
        except (ZeroDivisionError, ValueError):
            pass
    return rec
