"""Tract-index stable-key parsing.

A stable key identifies a county instrument independently of row order, so the
same instrument found in a handwritten tract-index page, a typed supplement and
a source PDF collapses to one identity.

Key form:  "<docno>|<book>-<page>"   e.g. "1063795|3269-0038"
Either half may be absent (modern Campbell filings are doc-number-only; some old
filings are book/page-only). Missing halves render as the empty string, never as
a zero or a placeholder.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Modern Campbell doc numbers are YYYY-NNNNN; legacy are bare integers.
_MODERN_DOC = re.compile(r"^\s*(\d{4})-(\d{4,5})\s*$")
_LEGACY_DOC = re.compile(r"^\s*#?\s*(\d{1,7})\s*$")
# Book-page appears as 3269-0038, 0098-0131, 25MR-0347, 005M-0119, 02PM-0099.
_BOOKPAGE = re.compile(r"^\s*([0-9]{1,4}[A-Z]{0,2})\s*[-/]\s*([0-9]{1,4})\s*$", re.I)


class StableKeyError(ValueError):
    pass


def normalize_docno(raw: str | None) -> str:
    """Return a canonical document number, or '' when genuinely absent."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s or s.upper() in {"NA", "N/A", "NONE", "UNKNOWN", "-", "--"}:
        return ""
    m = _MODERN_DOC.match(s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = _LEGACY_DOC.match(s)
    if m:
        return str(int(m.group(1)))  # strip leading zeros / '#'
    raise StableKeyError(f"unparseable document number: {raw!r}")


def normalize_bookpage(raw: str | None) -> str:
    """Return a canonical BOOK-PAGE, zero-padded to the house 4+4 form, or ''."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s or s.upper() in {"NA", "N/A", "NONE", "UNKNOWN", "-", "--"}:
        return ""
    m = _BOOKPAGE.match(s)
    if not m:
        raise StableKeyError(f"unparseable book-page: {raw!r}")
    book, page = m.group(1).upper(), m.group(2)
    digits = re.match(r"^(\d+)([A-Z]*)$", book)
    if digits:
        num, suffix = digits.group(1), digits.group(2)
        book = f"{int(num):0{4 - len(suffix)}d}{suffix}" if len(suffix) < 4 else f"{num}{suffix}"
    return f"{book}-{int(page):04d}"


def stable_key(docno: str | None, bookpage: str | None) -> str:
    """Build the canonical '<docno>|<book>-<page>' identity."""
    d, b = normalize_docno(docno), normalize_bookpage(bookpage)
    if not d and not b:
        raise StableKeyError("cannot build a stable key with neither doc no nor book-page")
    return f"{d}|{b}"


@dataclass(frozen=True)
class TractEntry:
    """One row of the authenticated tract index."""
    page: int          # tract-index PDF page (1-11 handwritten, 12-14 typed)
    row: int           # 1-based occupied-row ordinal within that page
    docno: str = ""
    bookpage: str = ""
    source: str = "handwritten"   # or "typed"

    @property
    def key(self) -> str:
        return stable_key(self.docno or None, self.bookpage or None)

    @property
    def locator(self) -> str:
        return f"p{self.page}r{self.row}"


def dedupe(entries: list[TractEntry]) -> tuple[dict[str, list[TractEntry]], list[str]]:
    """Collapse raw tract rows to unique stable keys.

    Returns (key -> contributing entries, overlap_keys). An overlap is any key
    contributed by more than one raw row -- that is the handwritten/typed
    overlap the 461-key ledger has to name explicitly.
    """
    by_key: dict[str, list[TractEntry]] = {}
    for e in entries:
        by_key.setdefault(e.key, []).append(e)
    overlaps = sorted(k for k, v in by_key.items() if len(v) > 1)
    return by_key, overlaps
