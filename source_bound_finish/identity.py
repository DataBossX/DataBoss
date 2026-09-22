"""Stable identities for instruments. Missing halves stay blank, never zero."""

from __future__ import annotations

import re
from dataclasses import dataclass

_MODERN_DOC = re.compile(r"^\s*(\d{4})-(\d{4,6})\s*$")
_LEGACY_DOC = re.compile(r"^\s*#?\s*(\d{1,8})\s*$")
_BOOKPAGE = re.compile(
    r"^\s*([0-9]{1,5}[A-Za-z]{0,3})\s*[-/]\s*([0-9]{1,5})\s*$"
)
_EMPTY = frozenset({"", "na", "n/a", "none", "unknown", "-", "--"})


class StableKeyError(ValueError):
    pass


@dataclass(frozen=True)
class StableKey:
    doc_no: str
    book_page: str
    physical_start: str = ""

    @property
    def key(self) -> str:
        return f"{self.doc_no}|{self.book_page}"

    @property
    def present(self) -> bool:
        return bool(self.doc_no or self.book_page)

    def with_page(self, physical_start: str) -> "StableKey":
        return StableKey(self.doc_no, self.book_page, str(physical_start or ""))


def _blank(raw: str | None) -> str:
    if raw is None:
        return ""
    text = str(raw).strip()
    return "" if text.lower() in _EMPTY else text


def normalize_doc_no(raw: str | None) -> str:
    text = _blank(raw)
    if not text:
        return ""
    modern = _MODERN_DOC.match(text)
    if modern:
        return f"{modern.group(1)}-{modern.group(2)}"
    legacy = _LEGACY_DOC.match(text)
    if legacy:
        return str(int(legacy.group(1)))
    raise StableKeyError(f"unparseable document number: {raw!r}")


def normalize_book_page(raw: str | None) -> str:
    text = _blank(raw)
    if not text:
        return ""
    match = _BOOKPAGE.match(text)
    if not match:
        raise StableKeyError(f"unparseable book-page: {raw!r}")
    book, page = match.group(1).upper(), match.group(2)
    digits = re.match(r"^(\d+)([A-Z]*)$", book)
    if digits:
        number, suffix = digits.group(1), digits.group(2)
        width = max(4 - len(suffix), 1)
        book = f"{int(number):0{width}d}{suffix}"
    return f"{book}-{int(page):04d}"


def stable_key(
    doc_no: str | None = None,
    book_page: str | None = None,
    physical_start: str | None = None,
) -> StableKey:
    return StableKey(
        doc_no=normalize_doc_no(doc_no),
        book_page=normalize_book_page(book_page),
        physical_start=str(physical_start or "").strip(),
    )


def reconcile_populations(existing: list[str], candidates: list[str]) -> dict:
    """Identity-union two populations. Never add the raw counts."""
    left = {item for item in existing if item}
    right = {item for item in candidates if item}
    return {
        "existing": len(left),
        "candidates": len(right),
        "overlap": len(left & right),
        "predecessor_only": len(left - right),
        "expanded_only": len(right - left),
        "union": len(left | right),
        "arithmetic_sum": len(left) + len(right),
        "arithmetic_sum_valid": False,
    }


def find_duplicate_keys(keys: list[StableKey]) -> list[str]:
    seen: dict[str, int] = {}
    for item in keys:
        if not item.present:
            continue
        identity = item.key
        if item.physical_start:
            identity = f"{identity}|p{item.physical_start}"
        seen[identity] = seen.get(identity, 0) + 1
    return sorted(identity for identity, count in seen.items() if count > 1)
