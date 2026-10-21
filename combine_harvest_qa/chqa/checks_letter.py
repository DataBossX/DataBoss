"""Certification letter: wording vs donor template, geometry, preparation dates, workbook agreement."""
from __future__ import annotations

import datetime as dt
import re
from typing import Optional

from docx import Document
from docx.shared import Emu

from .findings import Report

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_RE = re.compile(rf"\b(?:{MONTHS})\s+\d{{1,2}},\s+\d{{4}}\b|\b\d{{1,2}}/\d{{1,2}}/\d{{4}}\b")


def _parse(s: str) -> Optional[dt.date]:
    for fmt in ("%B %d, %Y", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def docx_facts(path: str) -> dict:
    d = Document(path)
    s = d.sections[0]
    paras = [p.text for p in d.paragraphs]
    fonts = {(r.font.name, r.font.size.pt if r.font.size else None) for p in d.paragraphs for r in p.runs}
    return {"paragraphs": paras, "nonblank": [p for p in paras if p.strip()],
            "page_w_in": round(Emu(s.page_width).inches, 3), "page_h_in": round(Emu(s.page_height).inches, 3),
            "margins_in": [round(Emu(x).inches, 3) for x in (s.top_margin, s.bottom_margin, s.left_margin, s.right_margin)],
            "fonts": sorted(map(str, fonts)), "tables": len(d.tables)}


def _template(text: str) -> str:
    t = DATE_RE.sub("<DATE>", text)
    t = re.sub(r"\bT\d+N-R\d+W\b", "<STR>", t)
    t = re.sub(r"\bSection \d+\b", "Section <N>", t)
    t = re.sub(r"\bWYW-?\d{5,6}\b", "<WYW>", t)
    t = re.sub(r"<WYW>(?:\s*(?:,\s*and|,|and)\s*<WYW>)*", "<WYWS>", t)     # one serial or a list of serials
    t = re.sub(r"\b\d+ entries\b", "<N> entries", t)
    t = re.sub(r"\b(Campbell|Johnson|Converse|Natrona|Weston|Crook)\b", "<COUNTY>", t)
    return re.sub(r"\s+", " ", t).strip()


def check_letter(path: str, donor_path: str, rep: Report, *, prepared: Optional[dt.date] = None,
                 posted_thru: Optional[dt.date] = None) -> None:
    rep.inputs.setdefault("files", []).append(path)
    cand, donor = docx_facts(path), docx_facts(donor_path)
    for k in ("page_w_in", "page_h_in", "margins_in", "tables"):
        if cand[k] != donor[k]:
            rep.add("letter_geometry", "error", path, f"{k} differs from donor letter", expected=str(donor[k]), actual=str(cand[k]))
    if cand["fonts"] != donor["fonts"]:
        rep.add("letter_fonts", "warn", path, "font/size set differs from donor letter", expected=str(donor["fonts"]), actual=str(cand["fonts"]))
    if len(cand["nonblank"]) != len(donor["nonblank"]):
        rep.add("letter_paragraph_count", "error", path, "paragraph count differs from donor", expected=str(len(donor["nonblank"])), actual=str(len(cand["nonblank"])))
    for i, (c, d) in enumerate(zip(cand["nonblank"], donor["nonblank"]), 1):
        if _template(c) != _template(d):
            rep.add("letter_wording", "error", path, "wording differs from donor template (after masking dates/STR/serials/counts)",
                    cell=f"paragraph {i}", expected=_template(d)[:160], actual=_template(c)[:160])
    dates = [(_parse(m.group(0)), m.group(0)) for p in cand["nonblank"] for m in DATE_RE.finditer(p)]
    if prepared:
        top = " ".join(cand["nonblank"][:6])
        got = [d for d, _ in ((_parse(m.group(0)), m.group(0)) for m in DATE_RE.finditer(top)) if d]
        if prepared not in got:
            rep.add("letter_prep_date", "error", path, "preparation date in letter header differs from expected", expected=str(prepared), actual=", ".join(map(str, got)) or "none")
    if posted_thru and not any(d == posted_thru for d, _ in dates):
        rep.add("letter_posted_thru", "error", path, "county posted-thru date not stated in letter", expected=str(posted_thru))
    for d, raw in dates:
        if d is None:
            rep.add("letter_date_unparsed", "warn", path, "date text could not be parsed", actual=raw)
    for must in ("Gille Energy, LLC", "Penterra Services, LLC"):
        if must not in " ".join(cand["nonblank"]):
            rep.add("letter_signature_block", "error", path, "required signature-block text missing", expected=must)
