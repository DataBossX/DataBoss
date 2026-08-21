"""Normalize arbitrary Python values before assigning them to Excel cells.

This module fixes the QA-matrix failure where a list (notably ``[]``) reached
an Excel cell writer and raised ``ValueError: Cannot convert [] to Excel``.
It is deliberately independent of any spreadsheet library: call
``excel_safe_value`` at the boundary immediately before assigning a cell, or
normalize complete row collections with ``excel_safe_rows``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, TypeAlias

ExcelNative: TypeAlias = str | int | float | bool | None | date | datetime | time | timedelta
ExcelSafe: TypeAlias = ExcelNative

_NATIVE_TYPES = (str, int, bool, date, datetime, time, timedelta)


def _json_compatible(value: Any, seen: set[int]) -> Any:
    """Return a deterministic JSON-compatible representation of ``value``."""
    if value is None or isinstance(value, _NATIVE_TYPES):
        return value

    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    object_id = id(value)
    if object_id in seen:
        return "<CYCLE>"

    if isinstance(value, Mapping):
        seen.add(object_id)
        try:
            return {
                str(key): _json_compatible(item, seen)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            }
        finally:
            seen.remove(object_id)

    if isinstance(value, (set, frozenset)):
        seen.add(object_id)
        try:
            normalized = [_json_compatible(item, seen) for item in value]
            return sorted(
                normalized,
                key=lambda item: json.dumps(
                    item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ),
            )
        finally:
            seen.remove(object_id)

    if isinstance(value, (list, tuple)):
        seen.add(object_id)
        try:
            return [_json_compatible(item, seen) for item in value]
        finally:
            seen.remove(object_id)

    return str(value)


def excel_safe_value(value: Any) -> ExcelSafe:
    """Convert ``value`` into a scalar accepted by common Excel writers.

    Native Excel scalar types are preserved. Collections become compact,
    deterministic JSON text. Empty lists therefore become the literal ``[]``
    rather than triggering a cell-conversion exception.
    """
    if value is None or isinstance(value, _NATIVE_TYPES):
        return value

    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    if isinstance(value, (Mapping, list, tuple, set, frozenset)):
        normalized = _json_compatible(value, set())
        return json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    return str(value)


def excel_safe_row(row: Iterable[Any]) -> list[ExcelSafe]:
    """Normalize one row for safe spreadsheet output."""
    return [excel_safe_value(value) for value in row]


def excel_safe_rows(rows: Iterable[Iterable[Any]]) -> list[list[ExcelSafe]]:
    """Normalize a row iterable for safe spreadsheet output."""
    return [excel_safe_row(row) for row in rows]
