"""Shared parsing helpers for the domain validators.

These keep the validators focused on *policy* (what a gate means) rather than
*mechanics* (how to find a column or normalize a fraction).  All math that
touches ownership interest goes through :func:`parse_fraction` /
:class:`Fraction` so there is never floating-point drift on a legal fraction.
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Optional

from ..ingestion.workbook_ingestor import CellData

_COL_RE = re.compile(r"([A-Za-z]+)(\d+)")


def col_of(coord: str) -> str:
    m = _COL_RE.match(coord)
    return m.group(1).upper() if m else ""


def row_of(coord: str) -> int:
    m = _COL_RE.match(coord)
    return int(m.group(2)) if m else 0


def col_to_index(col: str) -> int:
    idx = 0
    for ch in col.upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx


def index_to_col(idx: int) -> str:
    letters = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def find_header_column(sheet, *keywords: str) -> Optional[str]:
    """Return the column letter whose header cell matches any keyword.

    ``sheet`` is a SheetInfo.  Headers are matched case-insensitively; earlier
    keywords win so callers can express preference order (e.g. "net" before
    "gross").
    """
    if not sheet.headers:
        return None
    lowered = [h.lower() for h in sheet.headers]
    for kw in keywords:
        for col_idx, header in enumerate(lowered, start=1):
            if kw in header:
                return index_to_col(col_idx)
    return None


def label_column(sheet) -> str:
    """Best-guess the descriptive label column (usually the first)."""
    col = find_header_column(sheet, "tract", "description", "label", "row", "item")
    return col or "A"


def data_cells_in_column(sheet, col: str, *, header_row: int = 1) -> list[CellData]:
    """Numeric-or-text cells in ``col`` below the header row, in row order."""
    cells = [c for c in sheet.cells.values()
             if col_of(c.coord) == col and c.row > header_row]
    return sorted(cells, key=lambda c: c.row)


def is_total_row(sheet, row: int) -> bool:
    """True when any cell in ``row`` reads like a totals/footing label."""
    tokens = ("total", "sum", "grand total", "footing", "subtotal")
    for c in sheet.cells.values():
        if c.row == row and isinstance(c.value, str):
            v = c.value.strip().lower()
            if any(tok == v or v.startswith(tok) for tok in tokens):
                return True
    return False


def numeric(value) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        try:
            return float(s)
        except ValueError:
            return None
    return None


_FRACTION_RE = re.compile(r"^\s*(-?\d+)\s*/\s*(\d+)\s*$")
_MIXED_RE = re.compile(r"^\s*(-?\d+)\s+(\d+)\s*/\s*(\d+)\s*$")


def parse_fraction(value) -> Optional[Fraction]:
    """Parse a mineral-interest value into an exact :class:`Fraction`.

    Accepts ``"1/8"``, ``"3 1/2"``, ``0.125``, ``"12.5%"`` and plain numbers.
    Percent strings are divided by 100.  Returns ``None`` if unparseable so the
    caller can escalate rather than invent a value.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(value).limit_denominator(1_000_000)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        pct = s.endswith("%")
        if pct:
            s = s[:-1].strip()
        m = _MIXED_RE.match(s)
        if m:
            whole, num, den = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            frac = Fraction(whole) + Fraction(num, den)
        else:
            m = _FRACTION_RE.match(s)
            if m:
                frac = Fraction(int(m.group(1)), int(m.group(2)))
            else:
                try:
                    frac = Fraction(s)
                except (ValueError, ZeroDivisionError):
                    return None
        if pct:
            frac = frac / 100
        return frac
    return None
