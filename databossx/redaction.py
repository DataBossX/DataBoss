"""Recursive redaction of secret material from structured data and text.

Run parameters and error messages can incidentally capture credentials. Every
value is redacted before it is persisted to the immutable ledger, by key name
and by value shape. Redaction reports only that a secret was present, never the
secret itself.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

# Keys whose values are always redacted regardless of content.
_SENSITIVE_KEY = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|passwd|pwd|private[_-]?key|"
    r"authorization|auth[_-]?token|access[_-]?key|client[_-]?secret|"
    r"connection[_-]?string|mongo[_-]?url|dsn|credential)"
)

# Value shapes that look like secrets even under an innocuous key.
_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    # user:password@host style credentials in URIs (mongodb://, postgres://, ...)
    re.compile(r"(?i)\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:[^\s:/@]+@"),
    re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*\S+"),
)


def _redact_uri_credentials(text: str) -> str:
    return re.sub(
        r"(?i)\b([a-z][a-z0-9+.\-]*://)([^\s:/@]+):([^\s:/@]+)@",
        lambda m: f"{m.group(1)}{m.group(2)}:{REDACTED}@",
        text,
    )


def redact_text(value: str) -> str:
    redacted = _redact_uri_credentials(value)
    for pattern in _VALUE_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redact(value: Any, *, _key: str | None = None) -> Any:
    """Return a deep copy of ``value`` with secrets redacted."""
    if _key is not None and _SENSITIVE_KEY.search(_key):
        return REDACTED
    if isinstance(value, dict):
        return {key: redact(item, _key=str(key)) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_message(message: str) -> str:
    """Redact a single free-form string (e.g. an exception message)."""
    return redact_text(str(message))
