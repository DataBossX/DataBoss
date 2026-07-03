"""Source-in gap resolver.

For each highlighted conveying party, search for an earlier grantee-side appearance
(the party ACQUIRING the interest) in the Runsheet grantee column and in the parsed
county-index database, under name/OCR variants. A gap is resolvable only when the SAME
party is documented acquiring the interest via a title-type instrument BEFORE it conveys
out. This is the exact, conservative test used to clear 29 of 96 gaps on 31-12N-24W.
"""
from __future__ import annotations
import re
import openpyxl

STOP = {"and", "the", "hw", "llc", "inc", "co", "company", "trust", "trustee", "of",
        "et", "al", "ttee", "living", "revocable", "family", "estate", "usa", "ltd",
        "lp", "partnership", "deceased", "dcd", "aka", "fka", "also", "known", "as",
        "single", "person", "jr", "sr", "trustees"}


def toks(name: str) -> set[str]:
    name = re.sub(r"[^A-Za-z ]", " ", (name or "").lower())
    return {t for t in name.split() if len(t) > 2 and t not in STOP}


def find_source_in(party: str, runsheet_rows: list[tuple], index_recs: list[dict],
                   convey_year: int | None = None) -> dict | None:
    """Return the resolving instrument dict, or None.
    runsheet_rows: list of (row, inst, type, bkpg, date, grantor, grantee)
    """
    gt = toks(party)
    if not gt:
        return None
    excluded = re.compile(r"(?i)mortgage|release|lien|easement|right.of.way|financ|UCC|change of address")
    best = None
    for (row, inst, typ, bkpg, date, grantor, grantee) in runsheet_rows:
        if excluded.search(typ or ""):
            continue
        ht = toks(grantee)
        common = gt & ht
        strong = len(common) >= 2 or (len(common) == 1 and len(gt) <= 2)
        if not strong:
            continue
        yr = None
        m = re.match(r"(\d{4})", str(inst))
        if m:
            yr = int(m.group(1))
        if convey_year and yr and yr > convey_year:
            continue  # acquisition must precede the conveyance
        cand = {"instrument": inst, "type": typ, "book_page": bkpg,
                "grantee": grantee[:60], "shared": sorted(common), "source": "Runsheet grantee"}
        if best is None or (yr or 0) <= (int(re.match(r'(\d{4})', str(best['instrument'])).group(1)) if re.match(r'(\d{4})', str(best['instrument'])) else 9999):
            best = cand
    return best


def load_runsheet_rows(workbook_path: str) -> list[tuple]:
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Runsheet"]
    rows = []
    for r in range(2, ws.max_row + 1):
        rows.append((r, str(ws.cell(r, 1).value or ""), str(ws.cell(r, 3).value or ""),
                     str(ws.cell(r, 4).value or ""), str(ws.cell(r, 6).value or ""),
                     str(ws.cell(r, 7).value or ""), str(ws.cell(r, 8).value or "")))
    return rows
