"""Content rules: blanks/Unknown, dates, comments, source links, duplicates, BLM ordering, federal File No."""
from __future__ import annotations

import csv
import datetime as dt
import os
import re
from typing import Optional

from .findings import Report
from .model import Sheet, col_letter

PLACEHOLDER = re.compile(r"^\s*(unknown|unk|tbd|tba|n/?a|none|\?+|-+|see (record|image)|\[.*\])\s*$", re.I)
PLACEHOLDER_ANYWHERE = re.compile(r"\bunknown\b|\bTBD\b|\billegible\b", re.I)
FED_FILE = re.compile(r"^WYW\d{5,6}$")
ALLOWED_COMMENT = "missing image"


def _d(v):
    """datetime -> date so comparisons never mix the two."""
    return v.date() if isinstance(v, dt.datetime) else v


def _cols(prof: dict) -> dict[str, int]:
    return {c["header"]: c["index"] for c in prof["columns"]}


def check_content(path: str, sh: Sheet, prof: dict, rep: Report, *, kind: str = "index",
                  allow_blank: Optional[set[str]] = None, posted_thru: Optional[dt.date] = None,
                  links_csv: Optional[str] = None, expected_file_no: Optional[str] = None) -> None:
    cols = _cols(prof)
    hr = prof["header_row"]
    # donor-derived tolerance: a column blank in the donor (Book-Page, Date of Doc) may be blank; Comments must be blank
    donor_allows = {h for h, n in prof["donor_blank_counts"].items() if n and h != "Comments"}
    allowed = allow_blank if allow_blank is not None else donor_allows
    rows = [r for r in range(hr + 1, sh.max_row + 1)]
    for r in rows:
        for h, c in cols.items():
            cell = sh.get(r, c)
            if h == "Comments":
                continue
            txt = (cell.text or "").strip()
            if cell.kind == "empty":
                if h not in allowed:
                    rep.add("blank_substantive", "error", path, f"blank {h}", sheet=sh.name, cell=cell.ref, expected="non-blank")
            elif PLACEHOLDER.match(txt) or (cell.kind == "string" and PLACEHOLDER_ANYWHERE.search(txt)):
                rep.add("unknown_placeholder", "error", path, f"placeholder text in {h}", sheet=sh.name, cell=cell.ref, actual=txt[:80])
    # metadata block (rows above the header)
    for m in prof["metadata_rows"]:
        if not m["label"]:
            continue
        v = sh.get(m["row"], 2)
        txt = (v.text or "").strip()
        limit = max(60, 2 * int(m.get("value_len") or 0))
        if len(txt) > limit:
            rep.add("metadata_value_too_long", "error", path, f"{m['label']} value is {len(txt)} chars; donor style is short (wraps and overprints in the fixed-height row)",
                    sheet=sh.name, cell=v.ref, expected=f"<= {limit} chars", actual=txt[:80])
        if m["value_kind"] == "date" and v.kind != "date":
            rep.add("metadata_date_invalid", "error", path, f"{m['label']} must be a real date", sheet=sh.name, cell=v.ref, expected="date m/d/yyyy", actual=txt or "blank")
        elif v.kind != "empty" and (PLACEHOLDER.match(txt) or re.search(r"unknown|to be established|do not invent", txt, re.I)):
            rep.add("unknown_placeholder", "error", path, f"placeholder in {m['label']}", sheet=sh.name, cell=v.ref, actual=txt[:80])
    # dates
    for h in ("Date of Doc", "Rec Date"):
        c = cols.get(h)
        if not c:
            continue
        for r in rows:
            cell = sh.get(r, c)
            if cell.kind == "empty":
                continue
            if cell.kind != "date":
                rep.add("invalid_date", "error", path, f"{h} is {cell.kind}, not a real date", sheet=sh.name, cell=cell.ref, actual=cell.text, expected="date m/d/yyyy")
                continue
            if cell.style.number_format != "m/d/yyyy":
                rep.add("date_format", "error", path, "date number format differs", sheet=sh.name, cell=cell.ref, expected="m/d/yyyy", actual=str(cell.style.number_format))
            if posted_thru and _d(cell.value) > posted_thru and h == "Rec Date":
                rep.add("date_after_posted_thru", "error", path, "Rec Date later than Date Posted Thru", sheet=sh.name, cell=cell.ref, expected=f"<= {posted_thru}", actual=str(cell.value))
            if cell.value.year < 1860 or _d(cell.value) > dt.date.today():
                rep.add("implausible_date", "error", path, "date out of plausible range", sheet=sh.name, cell=cell.ref, actual=str(cell.value))
    if "Date of Doc" in cols and "Rec Date" in cols:
        for r in rows:
            d, rc = sh.get(r, cols["Date of Doc"]), sh.get(r, cols["Rec Date"])
            if d.kind == "date" and rc.kind == "date" and _d(rc.value) < _d(d.value):
                rep.add("rec_before_doc", "warn", path, "Rec Date earlier than Date of Doc", sheet=sh.name, cell=rc.ref, expected=f">= {d.value}", actual=str(rc.value))
    # Doc No numeric where purely digits
    if "Doc No" in cols:
        for r in rows:
            cell = sh.get(r, cols["Doc No"])
            if cell.kind == "string" and cell.text.strip().isdigit():
                rep.add("docno_stored_as_text", "error", path, "Doc No digits stored as text", sheet=sh.name, cell=cell.ref, expected="integer")
    # Comments / cell notes
    ccol = cols.get("Comments")
    for (r, c), cell in sh.cells.items():
        if cell.comment:
            rep.add("unexpected_cell_note", "error", path, "cell note present", sheet=sh.name, cell=cell.ref, actual=cell.comment[:80])
        if ccol and c == ccol and r > hr and cell.kind != "empty" and cell.text.strip() != ALLOWED_COMMENT:
            rep.add("unexpected_comment", "error", path, "Comments must be blank or exactly 'missing image'", sheet=sh.name, cell=cell.ref, actual=cell.text[:80])
    # duplicate instrument identities
    seen: dict[tuple, int] = {}
    for r in rows:
        key = (str(sh.get(r, cols.get("Doc No", 0)).value or ""), str(sh.get(r, cols.get("Book-Page", 0)).value or ""))
        if key == ("", ""):
            continue
        if key in seen:
            rep.add("duplicate_identity", "error", path, f"duplicate Doc No/Book-Page of row {seen[key]}", sheet=sh.name, cell=f"row {r}", actual="|".join(key))
        else:
            seen[key] = r
    # Book-Page shape vs donor shapes
    if "Book-Page" in cols and prof.get("book_page_shapes"):
        ok = set(prof["book_page_shapes"])
        for r in rows:
            cell = sh.get(r, cols["Book-Page"])
            t = cell.text.strip()
            if t and re.sub(r"[A-Za-z]", "A", re.sub(r"\d", "9", t)) not in ok:
                rep.add("book_page_shape", "warn", path, "Book-Page shape not seen in donor", sheet=sh.name, cell=cell.ref, expected=", ".join(sorted(ok)), actual=t)
    # BLM specifics
    if kind == "blm":
        fcol, pcol, partcol = cols.get("File No"), cols.get("Page"), cols.get("Part")
        if fcol:
            for r in rows:
                cell = sh.get(r, fcol)
                t = cell.text.strip()
                if expected_file_no and t != expected_file_no:
                    rep.add("federal_file_no", "error", path, "File No differs from the serial for this index", sheet=sh.name, cell=cell.ref, expected=expected_file_no, actual=t)
                elif not expected_file_no and t and not FED_FILE.match(t):
                    rep.add("federal_file_no", "error", path, "File No is not a WYW serial", sheet=sh.name, cell=cell.ref, expected="WYW######", actual=t)
        if partcol and pcol:
            last = (0, 0)
            for r in rows:
                part, page = sh.get(r, partcol), sh.get(r, pcol)
                if part.kind == "empty" and page.kind == "empty":
                    continue
                if part.kind != "int" or page.kind != "int":
                    rep.add("blm_part_page_type", "error", path, "Part/Page must be integers", sheet=sh.name, cell=f"{part.ref}/{page.ref}", actual=f"{part.text}/{page.text}")
                    continue
                cur = (part.value, page.value)
                if cur < last:
                    rep.add("blm_part_page_order", "error", path, "Part/Page not in ascending order", sheet=sh.name, cell=f"row {r}", expected=f">= {last}", actual=str(cur))
                last = max(last, cur)
    # source links manifest (CSV columns: row_key,source)
    if links_csv and os.path.exists(links_csv):
        with open(links_csv, newline="", encoding="utf8") as fh:
            have = {row["row_key"].strip(): row.get("source", "").strip() for row in csv.DictReader(fh)}
        for r in rows:
            if all(sh.get(r, c).kind == "empty" for c in cols.values()):
                continue
            bp, dn = str(sh.get(r, cols.get("Book-Page", 0)).value or "").strip(), str(sh.get(r, cols.get("Doc No", 0)).value or "").strip()
            key = bp or dn
            if not have.get(key) and not have.get(dn):
                rep.add("missing_source_link", "error", path, "no source image/link for instrument", sheet=sh.name, cell=f"row {r}", actual=key)
    elif links_csv:
        rep.skipped.append(f"source-link check: manifest not found ({links_csv})")
    else:
        rep.skipped.append("source-link check: no --links manifest supplied")
