#!/usr/bin/env python3
"""Parse iDoc Market search-result pages by word coordinates."""
import re
from statistics import median

import pymupdf

DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
HASH_RE = re.compile(r"^#(\d+)$")
HEADER_WORDS = {
    "Search", "Results", "iDoc", "|", "AM", "PM", "Showing:", "of", "results",
    "Township:", "Range:", "Section:", "Land", "Validated", "Through:",
    "Results", "Johnson,", "WY", "©", "Tyler", "Technologies,", "Inc.",
}


def book_page(book, page):
    if not book or not page:
        return "Unknown"
    book = re.sub(r"\s+", "", book.upper()).replace("R/W", "RW")
    page = page.strip().upper()
    if re.fullmatch(r"\d+", book):
        book_s = f"{int(book):04d}"
    else:
        book_s = book.replace("-", "")
    if re.fullmatch(r"\d+", page):
        page_s = f"{int(page):04d}"
    else:
        m = re.fullmatch(r"(\d+)([A-Z]+)", page)
        page_s = f"{int(m.group(1)):04d}{m.group(2)}" if m else page
    return f"{book_s}-{page_s}"


def doc_number(raw, rec):
    raw = raw.lstrip("#")
    m = re.match(r"(19\d{2})(\d{3,6})$", raw)
    if m and rec:
        year = m.group(1)
        rec_m = re.search(r"(\d{4})$", rec)
        if rec_m and rec_m.group(1) == year and int(year) < 2000:
            return m.group(2)
    return raw


def _trim_party_run(words, anchor_gy):
    """Keep the party lines that stay within one card. Drop the copyright block."""
    if not words:
        return words
    lines = {}
    for w in words:
        key = round(w["gy"])
        # merge words within 3pt into one line key
        placed = False
        for k in list(lines):
            if abs(k - w["gy"]) <= 3.2:
                lines[k].append(w)
                placed = True
                break
        if not placed:
            lines[key] = [w]
    ordered = sorted(lines)
    keep = []
    prev = anchor_gy
    for gy in ordered:
        line = lines[gy]
        texts = {w["text"] for w in line}
        if texts & {"Version", "Privacy", "Policy", "©"} or any(re.fullmatch(r"\d+\.\d+\.\d+\.\d+", t) for t in texts):
            break
        gap = gy - prev
        # A split card continues at the top of the next page. Page stride is 2000.
        if gap > 500:
            if (gy % 2000) > 90:
                break
        elif gap > 26:
            break
        keep.extend(line)
        prev = gy
    return keep


def clean_join(words):
    words = sorted(words, key=lambda w: (w["gy"], w["x"]))
    parts = []
    prev = None
    for w in words:
        if prev is not None and abs(w["gy"] - prev) > 3.2:
            parts.append(" ")
        elif parts:
            parts.append(" ")
        parts.append(w["text"])
        prev = w["gy"]
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def page_words(page, page_i):
    out = []
    for w in page.get_text("words"):
        x0, y0, x1, y1, text = w[:5]
        # Chrome is the 10/8/26 "Search Results | iDoc" line near y=15.
        # A split card's date and parties sit just under it, near y=29.
        if y0 < 24 or y0 > 762:
            continue
        if text.startswith("http"):
            continue
        out.append({
            "x": x0,
            "y": y0,
            "gy": page_i * 2000 + y0,
            "text": text,
            "page": page_i,
        })
    return out


def column_xs(words):
    """Return (date_x, party_x) or (None, None)."""
    dates = [w for w in words if DATE_RE.match(w["text"]) and 160 < w["x"] < 330]
    if len(dates) < 1:
        return None, None
    # mode bucket
    buckets = {}
    for w in dates:
        b = round(w["x"] / 8) * 8
        buckets.setdefault(b, []).append(w["x"])
    mode = max(buckets, key=lambda k: len(buckets[k]))
    date_x = median(buckets[mode])
    return date_x, date_x + 48


def meta_from_text(text):
    showing = re.search(r"Showing:\s*(\d+)\s+of\s+(\d+)", text)
    validated = re.search(r"Land Validated Through:\s*(\d{1,2}/\d{1,2}/\d{4})", text)
    section = re.search(r"Section:\s*(\d+)", text)
    twp = re.search(r"Township:\s*T?(\d+)", text)
    rng = re.search(r"Range:\s*R?(\d+)", text)
    printed = re.search(r"(\d{1,2}/\d{1,2}/\d{2}),\s*\d{1,2}:\d{2}", text)
    return {
        "n": int(showing.group(1)) if showing else None,
        "of": int(showing.group(2)) if showing else None,
        "validated": validated.group(1) if validated else None,
        "section": int(section.group(1)) if section else None,
        "twp": int(twp.group(1)) if twp else None,
        "rng": int(rng.group(1)) if rng else None,
        "printed": printed.group(1) if printed else None,
    }


def parse_pdf(path):
    doc = pymupdf.open(path)
    words = []
    texts = []
    page_date_x = {}
    for i, page in enumerate(doc):
        texts.append(page.get_text("text"))
        pw = page_words(page, i)
        dx, px = column_xs(pw)
        page_date_x[i] = dx
        words.extend(pw)
    full = "\n".join(texts)
    meta = meta_from_text(full)
    # fill missing page date columns from neighbors
    known = [v for v in page_date_x.values() if v]
    fallback = median(known) if known else 250
    for i in page_date_x:
        if page_date_x[i] is None:
            page_date_x[i] = fallback

    def date_x_of(w):
        return page_date_x[w["page"]]

    hashes = []
    for w in words:
        m = HASH_RE.match(w["text"])
        if m and w["x"] < date_x_of(w) - 20:
            hashes.append((w, m.group(1)))
    hashes.sort(key=lambda t: t[0]["gy"])

    dates = []
    for w in words:
        if not DATE_RE.match(w["text"]):
            continue
        dx = date_x_of(w)
        if abs(w["x"] - dx) <= 18:
            dates.append(w)
    dates.sort(key=lambda w: w["gy"])

    rows = []
    warnings = []
    for idx, (h, docno) in enumerate(hashes):
        prev_gy = hashes[idx - 1][0]["gy"] if idx else -1
        next_h_gy = hashes[idx + 1][0]["gy"] if idx + 1 < len(hashes) else 10**9
        cands = [d for d in dates if prev_gy < d["gy"] <= h["gy"] + 6]
        if not cands:
            warnings.append(f"no date for #{docno}")
            continue
        date = cands[-1]
        next_dates = [d for d in dates if d["gy"] > date["gy"] + 2]
        next_date_gy = next_dates[0]["gy"] if next_dates else 10**9
        # The page-count NUMBER sits in the date column. Grantor stays above it.
        # The word "Pages" often wraps below the grantee, so it is not the split.
        dx = date_x_of(date)
        counts = [
            w for w in words
            if re.fullmatch(r"\d{1,4}", w["text"])
            and abs(w["x"] - dx) <= 16
            and date["gy"] + 4 < w["gy"] < min(h["gy"] + 20, next_date_gy - 4)
        ]
        pages_gy = counts[0]["gy"] if counts else h["gy"]

        # book / page on the hash line
        same = [w for w in words if w["page"] == h["page"] and abs(w["gy"] - h["gy"]) <= 3.0]
        same.sort(key=lambda w: w["x"])
        texts_l = [w["text"] for w in same]
        book = page = None
        if "Book" in texts_l and "Page" in texts_l:
            bi = texts_l.index("Book")
            pi = texts_l.index("Page")
            book = " ".join(texts_l[bi + 1:pi])
            if pi + 1 < len(texts_l):
                page = texts_l[pi + 1]

        type_words = [
            w for w in words
            if w["x"] < dx - 22
            and date["gy"] - 8 <= w["gy"] < h["gy"] - 3.5
            and not HASH_RE.match(w["text"])
            and w["text"] not in HEADER_WORDS
            and not w["text"].startswith("http")
        ]
        grantor_words = [
            w for w in words
            if w["x"] >= dx + 36
            and date["gy"] - 8 <= w["gy"] < pages_gy - 1.2
        ]
        grantee_limit = min(next_date_gy - 3, next_h_gy + 80)
        # grantee must stay before the next card's type line. next date is the bound.
        grantee_words = [
            w for w in words
            if w["x"] >= dx + 36
            and pages_gy - 1.2 <= w["gy"] < next_date_gy - 3
            and w["gy"] < next_h_gy + 40
        ]
        # drop a grantee word that is actually the next card's grantor: those sit within 6pt of next date
        grantee_words = [w for w in grantee_words if w["gy"] < next_date_gy - 6]
        grantee_words = _trim_party_run(grantee_words, pages_gy)

        rec = date["text"]
        row = {
            "type": clean_join(type_words),
            "grantor": clean_join(grantor_words),
            "grantee": clean_join(grantee_words),
            "doc": doc_number(docno, rec),
            "doc_raw": docno,
            "bp": book_page(book, page),
            "rec": rec,
            "dod": "Unknown",
            "legal": "",
            "comments": "missing image",
            "source": "county electronic index printout",
            "page": h["page"],
        }
        if not row["type"]:
            warnings.append(f"empty type #{docno}")
        if not row["grantor"]:
            warnings.append(f"empty grantor #{docno}")
        rows.append(row)
    return meta, rows, warnings


if __name__ == "__main__":
    import sys
    from pathlib import Path
    paths = sys.argv[1:] or list(Path("/tmp").glob("s*_tract.pdf"))
    for p in paths:
        meta, rows, warnings = parse_pdf(str(p))
        print(f"{p}: section {meta['section']} showing {meta['n']} parsed {len(rows)} validated {meta['validated']} warnings {len(warnings)}")
        for w in warnings[:12]:
            print("   ", w)
        if rows:
            a, b = rows[0], rows[-1]
            print("   first", a["rec"], a["type"], a["doc"], a["bp"], a["grantor"], "->", a["grantee"])
            print("   last ", b["rec"], b["type"], b["doc"], b["bp"], b["grantor"], "->", b["grantee"])
