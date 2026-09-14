"""House stable keys for county instruments.

Form: ``<docno>|<book>-<page>``. Either half may be empty for genuine
doc-number-only or book/page-only filings. Missing halves are empty strings,
never placeholders. This module does not read Drive or mutate a workbook.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MODERN_DOC = re.compile(r"^\s*(\d{4})-(\d{4,5})\s*$")
_LEGACY_DOC = re.compile(r"^\s*#?\s*(\d{1,7})\s*$")
_BOOKPAGE = re.compile(
    r"^\s*([0-9]{1,4}[A-Z]{0,2})\s*[-/]\s*([0-9]{1,4})\s*$",
    re.I,
)
_ABSENT = frozenset({"", "NA", "N/A", "NONE", "UNKNOWN", "-", "--"})


class StableKeyError(ValueError):
    """Raised when a document number or book/page cannot be normalized."""


def normalize_docno(raw: str | None) -> str:
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text or text.upper() in _ABSENT:
        return ""
    modern = _MODERN_DOC.match(text)
    if modern:
        return f"{modern.group(1)}-{modern.group(2)}"
    legacy = _LEGACY_DOC.match(text)
    if legacy:
        return str(int(legacy.group(1)))
    raise StableKeyError(f"unparseable document number: {raw!r}")


def normalize_bookpage(raw: str | None) -> str:
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text or text.upper() in _ABSENT:
        return ""
    match = _BOOKPAGE.match(text)
    if match is None:
        raise StableKeyError(f"unparseable book-page: {raw!r}")
    book, page = match.group(1).upper(), match.group(2)
    digits = re.match(r"^(\d+)([A-Z]*)$", book)
    if digits:
        number, suffix = digits.group(1), digits.group(2)
        width = max(1, 4 - len(suffix))
        book = f"{int(number):0{width}d}{suffix}"
    return f"{book}-{int(page):04d}"


def stable_key(docno: str | None, bookpage: str | None) -> str:
    document = normalize_docno(docno)
    locator = normalize_bookpage(bookpage)
    if not document and not locator:
        raise StableKeyError(
            "cannot build a stable key with neither doc no nor book-page"
        )
    return f"{document}|{locator}"


@dataclass(frozen=True)
class TractEntry:
    page: int
    row: int
    docno: str = ""
    bookpage: str = ""
    source: str = "handwritten"

    @property
    def key(self) -> str:
        return stable_key(self.docno or None, self.bookpage or None)

    @property
    def locator(self) -> str:
        return f"p{self.page}r{self.row}"


def dedupe(entries: list[TractEntry]) -> tuple[dict[str, list[TractEntry]], list[str]]:
    by_key: dict[str, list[TractEntry]] = {}
    for entry in entries:
        by_key.setdefault(entry.key, []).append(entry)
    overlaps = sorted(key for key, group in by_key.items() if len(group) > 1)
    return by_key, overlaps
