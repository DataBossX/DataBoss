"""Shared helpers for validators: sheet lookup, column mapping, safe numeric
parsing using Decimal and Fraction (never unsafe float comparisons)."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any, Dict, List, Optional

from ingestion.sheet_classifier import ClassificationReport
from ingestion.workbook_ingestor import SheetView, WorkbookStructure


def find_sheets_by_category(context: Dict[str, Any], category: str) -> List[SheetView]:
    structure: WorkbookStructure = context["structure"]
    classification: ClassificationReport = context["classification"]
    names = {c.sheet_name for c in classification.by_category(category)}
    return [s for s in structure.sheets if s.name in names]


def column_index(headers: List[str], *aliases: str) -> Optional[int]:
    """Return the 0-based column index whose header matches any alias.

    Matching is case-insensitive and tolerant of surrounding punctuation.
    """
    norm_headers = [re.sub(r"[^a-z0-9]+", " ", h.lower()).strip() for h in headers]
    for alias in aliases:
        target = re.sub(r"[^a-z0-9]+", " ", alias.lower()).strip()
        for i, h in enumerate(norm_headers):
            if h == target:
                return i
        # containment fallback
        for i, h in enumerate(norm_headers):
            if target and target in h:
                return i
    return None


def parse_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text:
        return None
    m = re.search(r"-?\d+(\.\d+)?", text)
    if not m:
        return None
    try:
        return Decimal(m.group(0))
    except InvalidOperation:
        return None


def parse_fraction(value: Any) -> Optional[Fraction]:
    """Parse interest as an exact Fraction. Handles '1/2', '0.5', '50%', '.25'."""
    if value is None:
        return None
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        return Fraction(Decimal(str(value)))
    if isinstance(value, Decimal):
        return Fraction(value)
    text = str(value).strip()
    if not text:
        return None
    percent = text.endswith("%")
    text = text.rstrip("%").strip()
    try:
        if "/" in text:
            frac = Fraction(text)
        else:
            frac = Fraction(Decimal(text))
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return None
    if percent:
        frac = frac / 100
    return frac


def row_to_dict(headers: List[str], row: List[Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for i, h in enumerate(headers):
        if not h:
            continue
        out[h] = row[i] if i < len(row) else None
    return out


def non_empty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""
