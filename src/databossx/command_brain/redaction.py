"""Redaction applied to everything that leaves the trusted local boundary.

Two classes of leak are handled:

* **Secrets** — anything living under a credential-shaped key, plus values that
  look like known token formats. Never partially echoed: a suffix is still a
  secret.
* **Absolute local paths** — ``C:\\DataBoss\\...`` and POSIX absolute paths are
  operator-machine detail. Phone-facing payloads get a stable placeholder plus
  the basename, which is enough to recognise a file without disclosing layout.
"""

from __future__ import annotations

import re

SECRET_KEY_PATTERN = re.compile(
    r"(secret|token|password|passwd|credential|api[_-]?key|access[_-]?key|private[_-]?key|"
    r"authorization|cookie|session[_-]?id|bearer)",
    re.IGNORECASE,
)

SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bey[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)

WINDOWS_PATH_PATTERN = re.compile(r"[A-Za-z]:\\[^\s\"'<>|]*")
POSIX_PATH_PATTERN = re.compile(r"(?<![\w.])/(?:home|root|Users|mnt|srv|var|etc|opt)/[^\s\"'<>|]*")
UNC_PATH_PATTERN = re.compile(r"\\\\[^\s\"'<>|]+")

SECRET_PLACEHOLDER = "[REDACTED_SECRET]"


def _basename(path: str) -> str:
    cleaned = path.rstrip("\\/")
    for separator in ("\\", "/"):
        if separator in cleaned:
            cleaned = cleaned.rsplit(separator, 1)[-1]
    return cleaned or "path"


def _replace_path(match: re.Match) -> str:
    return f"[LOCAL_PATH:{_basename(match.group(0))}]"


def redact_text(text: str) -> str:
    """Strip secrets and absolute local paths from a single string."""
    if not isinstance(text, str) or not text:
        return text
    for pattern in SECRET_VALUE_PATTERNS:
        text = pattern.sub(SECRET_PLACEHOLDER, text)
    text = UNC_PATH_PATTERN.sub(_replace_path, text)
    text = WINDOWS_PATH_PATTERN.sub(_replace_path, text)
    text = POSIX_PATH_PATTERN.sub(_replace_path, text)
    return text


def redact(payload, _key: str | None = None):
    """Recursively redact a JSON-shaped payload.

    A value under a credential-shaped key is replaced wholesale — never
    truncated to a "safe" suffix.
    """
    if _key is not None and SECRET_KEY_PATTERN.search(str(_key)):
        return SECRET_PLACEHOLDER
    if isinstance(payload, dict):
        return {key: redact(value, key) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [redact(item) for item in payload]
    if isinstance(payload, str):
        return redact_text(payload)
    return payload


def contains_secret(payload) -> bool:
    """True if a payload still carries anything secret-shaped after redaction."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if SECRET_KEY_PATTERN.search(str(key)) and value not in (SECRET_PLACEHOLDER, None, ""):
                return True
            if contains_secret(value):
                return True
        return False
    if isinstance(payload, (list, tuple)):
        return any(contains_secret(item) for item in payload)
    if isinstance(payload, str):
        return any(pattern.search(payload) for pattern in SECRET_VALUE_PATTERNS)
    return False


def contains_absolute_path(payload) -> bool:
    if isinstance(payload, dict):
        return any(contains_absolute_path(value) for value in payload.values())
    if isinstance(payload, (list, tuple)):
        return any(contains_absolute_path(item) for item in payload)
    if isinstance(payload, str):
        return bool(
            WINDOWS_PATH_PATTERN.search(payload)
            or UNC_PATH_PATTERN.search(payload)
            or POSIX_PATH_PATTERN.search(payload)
        )
    return False
