"""Redact secret-shaped keys before any R&D record is written."""

from __future__ import annotations

import re
from typing import Any

from .constants import UNKNOWN

_SECRET_KEY_RE = re.compile(
    r"(token|secret|password|passwd|api[_-]?key|authorization|credential|"
    r"cookie|session|private[_-]?key|encryption|webhook|bearer)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"^(sk-|rk-|ghp_|gho_|xox[baprs]-|Bearer\s+)",
    re.IGNORECASE,
)


def is_secret_key(key: str) -> bool:
    return bool(_SECRET_KEY_RE.search(str(key)))


def redact_value(key: str, value: Any) -> Any:
    if is_secret_key(key):
        return "REDACTED"
    if isinstance(value, str) and _SECRET_VALUE_RE.search(value.strip()):
        return "REDACTED"
    return value


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): redact(redact_value(str(k), v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(item) for item in obj]
    if obj is None:
        return UNKNOWN
    return obj
